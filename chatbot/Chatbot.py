from __future__ import annotations

import os
import json
import pathlib
import logging
import re
import shutil
import pickle
import subprocess
import numpy as np
from typing import List, Tuple, Dict, Optional, Any

from dotenv import load_dotenv
from docx import Document

import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from rank_bm25 import BM25Okapi
from pyvi import ViTokenizer, ViPosTagger

from knowledge_graph import LegalKnowledgeGraph, extract_triplets_llm_batch

# Dùng try-except cho các package mới để không chết nếu chưa cài kip
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data_laws"
INDEX_DIR = BASE_DIR / "index_laws"
CONTRACT_DIR = BASE_DIR / "contracts"
TEMP_UPLOAD_DIR = BASE_DIR / "temp_uploads"

for p in [DATA_DIR, INDEX_DIR, CONTRACT_DIR, TEMP_UPLOAD_DIR]:
    p.mkdir(exist_ok=True)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") 
GCS_LAWS_PREFIX = os.getenv("GCS_LAWS_PREFIX", "law/")

EMBED_MODEL_NAME = "keepitreal/vietnamese-sbert"
_GEMINI_MODEL = None
_OCR_MODEL = None
_SEARCH_QUERY_CACHE = {}

def get_gemini_model():
    global _GEMINI_MODEL
    if _GEMINI_MODEL is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("❌ LỖI: Thiếu GEMINI_API_KEY")
        genai.configure(api_key=GEMINI_API_KEY)
        _GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")
    return _GEMINI_MODEL

def get_ocr_model():
    global _OCR_MODEL
    if _OCR_MODEL is None and PaddleOCR is not None:
        try:
            # use_angle_cls=True xử lý ảnh bị xoay nghiêng
            _OCR_MODEL = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
        except Exception as e:
            logger.error(f"Lỗi khởi tạo PaddleOCR: {e}")
    return _OCR_MODEL

CORE_SYSTEM_INSTRUCTION = """
# ROLE (VAI TRÒ)
Bạn là "AI Legal Assistant" – một Chuyên viên Pháp lý AI cấp cao, chuyên tư vấn pháp luật cho các Doanh nghiệp Vừa và Nhỏ (SME) tại Việt Nam.

# CORE TASKS (NHIỆM VỤ CHÍNH)
1. Tra cứu và giải thích quy định pháp luật dựa trên dữ liệu nội bộ.
2. Rà soát, chấm điểm và chỉ ra rủi ro trong Hợp đồng.
3. Phân tích tình huống vận hành thực tế của doanh nghiệp.
4. Cung cấp và hướng dẫn sử dụng Biểu mẫu (Templates) nếu liên quan đến thủ tục.

# DOMAIN SCOPE (PHẠM VI ÁP DỤNG)
ĐƯỢC PHÉP HỖ TRỢ: Luật Đầu tư, Luật Doanh nghiệp, Luật Thương mại, Luật Lao động, Kế toán - Thuế, Hóa đơn chứng từ.
TUYỆT ĐỐI TỪ CHỐI: Luật Hình sự, Dân sự cá nhân, Hôn nhân gia đình, Đất đai cá nhân.

# RAG & HALLUCINATION RULES (QUY TẮC RÚT TRÍCH DỮ LIỆU)
- Thông tin cung cấp trong mục [CONTEXT] là chân lý tuyệt đối.
- BẮT BUỘC trích xuất chuẩn xác định danh văn bản (Ví dụ: "Khoản 1 Điều 15 Luật Doanh nghiệp 59/2020/QH14"). KHÔNG ĐƯỢC tự bịa số hiệu.
- Nếu câu trả lời KHÔNG CÓ trong [CONTEXT]: Bắt buộc trả lời "Dữ liệu nội bộ chưa có quy định chi tiết..." và chỉ tư vấn ở mức nguyên tắc.
- Nếu người dùng hỏi thủ tục, CỐ GẮNG tìm xem có gợi ý tải BIỂU MẪU nào liên quan không (xuất text hướng dẫn tải biểu mẫu).

# OUTPUT STYLE & FORMAT (ĐỊNH DẠNG ĐẦU RA)
Giọng văn khách quan, chuyên nghiệp, trung lập. Bắt buộc dùng Markdown để trình bày. Tuyệt đối KHÔNG sử dụng bất kỳ ký tự Emoji nào.
Bạn PHẢI trình bày câu trả lời theo đúng 4 phần sau (không được tự ý đổi tên tiêu đề):

Phần 1: Kết luận ngắn gọn
(Trả lời trực tiếp vào trọng tâm câu hỏi của người dùng trong 2-3 câu)

Phần 2: Căn cứ pháp lý
(Trích dẫn chuẩn xác Số hiệu, Điều, Khoản từ dữ liệu [CONTEXT])

Phần 3: Phân tích chi tiết
(Áp dụng luật vào thực tế để giải thích tình huống)

Phần 4: Gợi ý Biểu mẫu và Hành động
(Liệt kê các bước cần làm tiếp theo và gợi ý biểu mẫu văn bản nếu có)

[DISCLAIMER NGẦM]: Lời khuyên chỉ mang tính chất tham khảo.
"""

def redact_sensitive_data(text: str) -> str:
    text = re.sub(r'\b(0\d{9,10})\b', "[SĐT ĐÃ CHE]", text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "[EMAIL ĐÃ CHE]", text)
    text = re.sub(r'\b(\d{9}|\d{12})\b', "[ID ĐÃ CHE]", text)
    return text

def read_docx(path: pathlib.Path) -> str:
    try:
        doc = Document(str(path))
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        logger.error(f"Lỗi đọc DOCX {path}: {e}")
        return ""

def read_txt(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Lỗi đọc TXT {path}: {e}")
        return ""

def read_doc(path: pathlib.Path) -> str:
    try:
        # Sử dụng antiword nếu có trên hệ điều hành
        result = subprocess.run(['antiword', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.warning(f"antiword failed cho file .doc, kết quả: {result.stderr}")
            return ""
    except Exception as e:
        logger.error(f"Lỗi đọc DOC {path} (yêu cầu cài antiword): {e}")
        return ""

def read_pdf(path: pathlib.Path) -> str:
    if not fitz:
        logger.warning("Thư viện PyMuPDF (fitz) chưa cài đặt.")
        return ""
    try:
        doc = fitz.open(str(path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
            
        # Fallback Local OCR cho PDF Scan
        if len(text.strip()) < 50:
            logger.info(f"Phát hiện PDF scan: {path.name}, tiến hành OCR bằng PaddleOCR...")
            ocr_model = get_ocr_model()
            if not ocr_model:
                return text # Trả về chuỗi rỗng nếu không có ocr
                
            ocr_text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
                img_bytes = pix.tobytes("png")
                
                temp_img_path = str(TEMP_UPLOAD_DIR / f"temp_ocr_{page_num}.png")
                with open(temp_img_path, "wb") as f:
                    f.write(img_bytes)
                    
                result = ocr_model.ocr(temp_img_path, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        ocr_text += line[1][0] + " "
                ocr_text += "\n"
                
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)
            return ocr_text.strip()
            
        return text.strip()
    except Exception as e:
        logger.error(f"Lỗi đọc PDF {path}: {e}")
        return ""

def read_contract_file(path: pathlib.Path | str) -> str:
    p = pathlib.Path(path)
    if not p.exists(): return ""
    ext = p.suffix.lower()
    if ext == ".docx":
        return read_docx(p)
    elif ext == ".pdf":
        return read_pdf(p)
    elif ext == ".doc":
        return read_doc(p)
    else:
        return read_txt(p)

def extract_keywords_local(text: str) -> str:
    try:
        # Lớp 3 LightRAG: Trích xuất tham chiếu chéo (Cross-refs) và số liệu quan trọng
        cross_refs = re.findall(r'(Điều \d+|khoản \d+ Điều \d+|Chương [IVXLCDM]+)', text)
        thresholds = re.findall(r'(\d+ ngày|\d+ tháng|\d+ năm|\d+%|\d+ triệu|\d+ tỷ)', text)
        
        tokens, tags = ViPosTagger.postagging(ViTokenizer.tokenize(text))
        keywords = [t.replace("_", " ") for t, tag in zip(tokens, tags) if tag in ("N", "Np", "Nc", "V")]
        
        final_entities = []
        if cross_refs: final_entities.extend(cross_refs)
        if thresholds: final_entities.extend(thresholds)
        final_entities.extend(keywords[:15])
        
        seen = set()
        return ", ".join([x for x in final_entities if not (x.lower() in seen or seen.add(x.lower()))])
    except Exception as e:
        logger.error(f"Lỗi extract keywords: {e}")
        return ""

def get_year_from_filename(filename: str) -> int:
    match = re.search(r'\b(19|20)\d{2}\b', filename)
    return int(match.group(0)) if match else 0

def get_law_base_name(filename: str) -> str:
    base = filename.lower().replace(".docx", "").replace(".pdf", "").replace(".doc", "").replace(".txt", "")
    base = re.sub(r'-\d+.*$', '', base)
    base = re.sub(r' \d{4}.*$', '', base)
    return base.strip()

def chunk_text(text: str, law_name: str) -> List[Dict[str, Any]]:
    # Hierarchical Legal Chunking (BookRAG 3 lớp)
    article_pattern = r'(?:\n|^)(Điều\s+\d+[:\.].*)'
    chapter_pattern = r'(?:\n|^)(Chương\s+[IVXLCDM]+[:\.].*)'
    section_pattern = r'(?:\n|^)(Mục\s+\d+[:\.].*)'
    
    chunks = []
    current_chapter = "Quy định chung"
    current_section = "Quy định chung"
    
    parts = re.split(r'(?:\n|^)(Điều\s+\d+[:\.])', text)
    if len(parts) <= 1:
        raw_chunks = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]
        return [{"text": c, "book": law_name, "chapter": "None", "section": "None", "article": "None"} for c in raw_chunks]

    titles = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        title_line = content.split('\n')[0].strip() if content else ""
        titles.append(f"{header} {title_line}")
        
    for idx, i in enumerate(range(1, len(parts), 2)):
        header = parts[i].strip()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        
        chap_matches = re.findall(chapter_pattern, parts[i-1])
        if chap_matches: 
            current_chapter = chap_matches[-1].strip()
            current_section = "Quy định chung" 
            
        sec_matches = re.findall(section_pattern, parts[i-1])
        if sec_matches: 
            current_section = sec_matches[-1].strip()

        prev_title = titles[idx-1] if idx > 0 else ""
        next_title = titles[idx+1] if idx + 1 < len(titles) else ""
        
        full_article = f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} {content}"
        
        # Tách Khoản nếu Điều quá dài (>2000 ký tự)
        if len(full_article) > 2000:
            clause_parts = re.split(r'(?:\n|^)(\d+\.\s)', content)
            if len(clause_parts) > 1:
                intro = clause_parts[0].strip()
                for j in range(1, len(clause_parts), 2):
                    c_header = clause_parts[j].strip()
                    c_content = clause_parts[j+1].strip() if j+1 < len(clause_parts) else ""
                    sub_text = f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} {intro}\n{c_header} {c_content}"
                    chunks.append({
                        "text": sub_text, "book": law_name, "chapter": current_chapter, 
                        "section": current_section, "article": header,
                        "prev_title": prev_title, "next_title": next_title
                    })
            else:
                sub_chunks = [p for p in full_article.split("\n") if p.strip()]
                for j, sub in enumerate(sub_chunks):
                    chunks.append({
                        "text": f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} (Phần {j+1}): {sub}", 
                        "book": law_name, "chapter": current_chapter, "section": current_section, 
                        "article": header, "prev_title": prev_title, "next_title": next_title
                    })
        else:
            chunks.append({
                "text": full_article, "book": law_name, "chapter": current_chapter, 
                "section": current_section, "article": header,
                "prev_title": prev_title, "next_title": next_title
            })
            
    return chunks

class LawVectorStore:
    def __init__(self, embed_model_name: str = EMBED_MODEL_NAME):
        self.embedder = SentenceTransformer(embed_model_name)
        self.index: Optional[faiss.IndexFlatIP] = None
        self.corpus_chunks: List[str] = []
        self.corpus_meta: List[Dict] = []
        self.bm25: Optional[BM25Okapi] = None
        self.kg = LegalKnowledgeGraph()

    def build_from_docs(self, doc_paths: List[pathlib.Path]) -> None:
        all_chunks = []
        all_meta = []
        for path in doc_paths:
            law_name = path.stem
            ext = path.suffix.lower()
            if ext == ".docx": text = read_docx(path)
            elif ext == ".pdf": text = read_pdf(path)
            elif ext == ".doc": text = read_doc(path)
            else: text = read_txt(path)
            
            if not text: continue
            chunk_dicts = chunk_text(text, law_name)
            year = get_year_from_filename(path.name)
            law_base = get_law_base_name(path.name)
            
            for i, cd in enumerate(chunk_dicts):
                entities = extract_keywords_local(cd["text"])
                # Hybrid RAG: BM25 Input chứa cả text, metadata adjacent, entities, cross-refs
                bm25_input = cd["text"] + "\nEntities: " + entities
                all_chunks.append(cd["text"])
                all_meta.append({
                    "source_file": path.name, "book": cd["book"], "chapter": cd.get("chapter", ""),
                    "section": cd.get("section", ""), "article": cd.get("article", ""),
                    "prev_title": cd.get("prev_title", ""), "next_title": cd.get("next_title", ""),
                    "chunk_id": i, "entities": entities, "year": year, "law_base": law_base,
                    "bm25_input": bm25_input
                })
        
        if not all_chunks: return
        embeddings = self.embedder.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        
        tokenized_corpus = [ViTokenizer.tokenize(meta["bm25_input"]).split() for meta in all_meta]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # Build Knowledge Graph (LightRAG Layer)
        logger.info(f"Bắt đầu trích xuất Knowledge Graph bằng Gemini cho {len(chunk_dicts)} chunks...")
        all_triplets = extract_triplets_llm_batch(chunk_dicts)
        for i, triplets in enumerate(all_triplets):
            self.kg.add_triplets(i, triplets)
        logger.info("Hoàn tất xây dựng Knowledge Graph.")
        
        self.corpus_chunks = all_chunks
        self.corpus_meta = all_meta

    def save(self, index_dir: pathlib.Path = INDEX_DIR) -> None:
        if self.index is None: return
        for f in index_dir.glob("*"): f.unlink()
        faiss.write_index(self.index, str(index_dir / "laws.faiss"))
        with (index_dir / "laws_meta.jsonl").open("w", encoding="utf-8") as f:
            for chunk, meta in zip(self.corpus_chunks, self.corpus_meta):
                f.write(json.dumps({"text": chunk, "meta": meta}, ensure_ascii=False) + "\n")
        if self.bm25:
            with open(index_dir / "bm25.pkl", "wb") as f: pickle.dump(self.bm25, f)
        self.kg.save(index_dir / "graph.pkl")

    def load(self, index_dir: pathlib.Path = INDEX_DIR) -> bool:
        faiss_path = index_dir / "laws.faiss"
        meta_path = index_dir / "laws_meta.jsonl"
        bm25_path = index_dir / "bm25.pkl"
        if not (faiss_path.exists() and meta_path.exists()): return False
        
        self.index = faiss.read_index(str(faiss_path))
        self.corpus_chunks = []
        self.corpus_meta = []
        with meta_path.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.corpus_chunks.append(rec["text"])
                self.corpus_meta.append(rec["meta"])
        if bm25_path.exists():
            with open(bm25_path, "rb") as f: self.bm25 = pickle.load(f)
        self.kg.load(index_dir / "graph.pkl")
        return True

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, Dict, float]]:
        if self.index is None: return []
        queries = generate_search_queries(query)
        if query not in queries: queries.append(query)
        
        fetch_k = 20
        all_v_results = {}
        all_bm25_results = {}
        
        for q in queries:
            q_emb = self.embedder.encode([q], convert_to_numpy=True, normalize_embeddings=True)
            v_scores, v_idxs = self.index.search(q_emb, fetch_k)
            for score, idx in zip(v_scores[0], v_idxs[0]):
                if 0 <= idx < len(self.corpus_chunks): 
                    all_v_results[idx] = max(all_v_results.get(idx, -1), float(score))
            
            if self.bm25:
                tokenized_query = ViTokenizer.tokenize(q).split()
                bm25_scores = self.bm25.get_scores(tokenized_query)
                top_bm25_idxs = np.argsort(bm25_scores)[::-1][:fetch_k]
                for idx in top_bm25_idxs:
                    if 0 <= idx < len(self.corpus_chunks): 
                        all_bm25_results[idx] = max(all_bm25_results.get(idx, -1), float(bm25_scores[idx]))
                        
        v_sorted = sorted(all_v_results.items(), key=lambda x: x[1], reverse=True)
        bm25_sorted = sorted(all_bm25_results.items(), key=lambda x: x[1], reverse=True)
        
        v_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(v_sorted)}
        bm25_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(bm25_sorted)}
        
        rrf_k = 60
        rrf_scores = {}
        all_candidate_idxs = set(all_v_results.keys()).union(set(all_bm25_results.keys()))
        
        for idx in all_candidate_idxs:
            rrf_v = 1.0 / (rrf_k + v_ranks.get(idx, 1000))
            rrf_bm25 = 1.0 / (rrf_k + bm25_ranks.get(idx, 1000))
            rrf_scores[idx] = rrf_v + rrf_bm25
            
        # --- GRAPH-AUGMENTED RETRIEVAL ---
        # 1. Trích xuất entities từ các top candidates
        top_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        seed_entities = []
        for idx, _ in top_candidates:
            if idx < len(self.corpus_meta):
                ents = [e.strip() for e in self.corpus_meta[idx].get("entities", "").split(",") if e.strip()]
                seed_entities.extend(ents)
                
        # 2. Traversal trên đồ thị để tìm các chunk_id lân cận (depth=2)
        related_chunk_ids = self.kg.find_related_chunks(seed_entities, depth=2)
        
        # 3. Tăng điểm (Re-rank) cho các chunk tìm được từ đồ thị
        graph_bonus = 0.05
        for idx in related_chunk_ids:
            if idx in rrf_scores:
                rrf_scores[idx] += graph_bonus
            else:
                rrf_scores[idx] = graph_bonus / 2.0 # Thêm mới nếu chưa có trong hybrid
                
        # Cập nhật lại danh sách sắp xếp sau khi qua Graph
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        # ---------------------------------
        
        registry_path = BASE_DIR / "law_registry.json"
        registry = {}
        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                try:
                    registry = json.load(f)
                except:
                    pass

        filtered_results = []
        seen_law_bases = {}
        
        for idx, score in sorted_candidates:
            meta = self.corpus_meta[idx]
            law_base = meta.get("law_base", "")
            year = meta.get("year", 0)
            
            # Xử lý cờ EXPIRED
            law_id = meta.get("source_file", "").rsplit(".", 1)[0]
            # Map tên file thực tế với key trong registry (có thể cần linh hoạt regex)
            # Tạm thời so khớp tương đối
            is_expired = False
            for reg_key, reg_val in registry.items():
                if reg_key.lower() in law_id.lower() and reg_val.get("status") == "EXPIRED":
                    is_expired = True
                    break
            
            if is_expired:
                continue
            
            if law_base in seen_law_bases:
                if year < seen_law_bases[law_base]:
                    continue
            else:
                seen_law_bases[law_base] = year
                
            # Đính kèm thêm Title Điều liền kề nếu có
            rich_chunk = self.corpus_chunks[idx]
            if meta.get("prev_title") or meta.get("next_title"):
                rich_chunk += f"\n(Liên quan: {meta.get('prev_title', '')} | {meta.get('next_title', '')})"
            
            filtered_results.append((rich_chunk, meta, score))
            if len(filtered_results) >= top_k:
                break
                
        return filtered_results

    def update_index(self, doc_path: pathlib.Path) -> bool:
        """Thêm văn bản luật mới vào hệ thống mà không cần build lại toàn bộ."""
        law_name = doc_path.stem
        ext = doc_path.suffix.lower()
        if ext == ".docx": text = read_docx(doc_path)
        elif ext == ".pdf": text = read_pdf(doc_path)
        elif ext == ".doc": text = read_doc(doc_path)
        else: text = read_txt(doc_path)
        
        if not text: return False
        chunk_dicts = chunk_text(text, law_name)
        year = get_year_from_filename(doc_path.name)
        law_base = get_law_base_name(doc_path.name)
        
        new_chunks = []
        new_meta = []
        offset = len(self.corpus_chunks)
        
        for i, cd in enumerate(chunk_dicts):
            entities = extract_keywords_local(cd["text"])
            bm25_input = cd["text"] + "\nEntities: " + entities
            new_chunks.append(cd["text"])
            new_meta.append({
                "source_file": doc_path.name, "book": cd["book"], "chapter": cd.get("chapter", ""),
                "section": cd.get("section", ""), "article": cd.get("article", ""),
                "prev_title": cd.get("prev_title", ""), "next_title": cd.get("next_title", ""),
                "chunk_id": offset + i, "entities": entities, "year": year, "law_base": law_base,
                "bm25_input": bm25_input
            })
            
        if not new_chunks: return False
        
        # 1. Update FAISS
        embeddings = self.embedder.encode(new_chunks, convert_to_numpy=True, normalize_embeddings=True)
        if self.index is None:
            self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        
        # 2. Update BM25
        self.corpus_chunks.extend(new_chunks)
        self.corpus_meta.extend(new_meta)
        tokenized_corpus = [ViTokenizer.tokenize(meta["bm25_input"]).split() for meta in self.corpus_meta]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # 3. Update Knowledge Graph
        logger.info(f"Cập nhật Knowledge Graph cho {len(chunk_dicts)} chunks mới...")
        new_triplets = extract_triplets_llm_batch(chunk_dicts)
        for i, triplets in enumerate(new_triplets):
            self.kg.add_triplets(offset + i, triplets)
            
        # 4. Save to disk
        self.save()
        logger.info(f"Đã cập nhật động (Dynamic Index) cho file: {doc_path.name}")
        return True

def smart_process_query(raw_msg: str) -> dict:
    # [TỐI ƯU TỐC ĐỘ] Bỏ qua lệnh gọi Gemini phân loại (tiết kiệm 2-3 giây)
    # Tạm thời gán mặc định là tra_cuu và giữ nguyên text gốc
    return {"corrected_text": raw_msg, "mode": "tra_cuu"}

def evaluate_context(context: str, query: str) -> dict:
    model = get_gemini_model()
    prompt = f"Bạn là AI Giám Thị. Đọc Câu hỏi và Context. Đánh giá xem Context có đủ dữ kiện để trả lời không.\nCÂU HỎI: {query}\nCONTEXT: {context}\nOUTPUT JSON: {{'is_sufficient': true/false, 'reason': '...'}}"
    try:
        res = model.generate_content(prompt)
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        logger.error(f"Lỗi Giám Thị RAG: {e}")
        return {"is_sufficient": True, "reason": "Lỗi"}

def generate_search_queries(user_question: str) -> List[str]:
    global _SEARCH_QUERY_CACHE
    if user_question in _SEARCH_QUERY_CACHE:
        return _SEARCH_QUERY_CACHE[user_question]
        
    if len(user_question.split()) < 6 or "điều " in user_question.lower() or "khoản " in user_question.lower():
        _SEARCH_QUERY_CACHE[user_question] = [user_question]
        return [user_question]
        
    model = get_gemini_model()
    prompt = f"Phân tích câu hỏi và liệt kê 3 cụm từ khóa tìm kiếm pháp lý ngắn gọn. Output JSON array ['q1', 'q2']. Câu hỏi: {user_question}"
    try:
        resp = model.generate_content(prompt)
        queries = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
        _SEARCH_QUERY_CACHE[user_question] = queries
        return queries
    except Exception as e:
        logger.error(f"Lỗi tạo query phụ: {e}")
        return [user_question]

def draft_new_contract_stream(requirement: str, safe_mode: bool = False):
    prompt = f"{CORE_SYSTEM_INSTRUCTION}\n\nSOẠN THẢO: {requirement}"
    if safe_mode: prompt = redact_sensitive_data(prompt)
    model = get_gemini_model()
    safety_settings = {HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings, stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
    except Exception as e:
        logger.error(f"Lỗi soạn thảo HĐ: {e}")
        yield f"⚠️ Lỗi kết nối AI: {e}"

def call_gemini_qa_stream(mode: str, relevant_docs: List[Tuple[str, Dict, float]], query: str, safe_mode: bool = True, history: List[Dict] = None):
    history_str = ""
    if history:
        history_str = "LỊCH SỬ HỘI THOẠI TRƯỚC ĐÓ:\n" + "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history]) + "\n\n"
        
    if not relevant_docs:
        context_str = "Không tìm thấy dữ liệu nội bộ liên quan."
    else:
        context_str = "\n\n".join([f"- {doc[0]}" for doc in relevant_docs])
    
    judge_res = evaluate_context(context_str, query)
    
    if not judge_res.get("is_sufficient", True):
        prompt = f"""Bạn là Trợ lý Pháp lý. Người dùng hỏi: "{query}".
Tuy nhiên dữ liệu nội bộ không đủ để kết luận chắc chắn.
Nhiệm vụ: 
1. Tuyệt đối KHÔNG ĐƯỢC kết luận.
2. Hãy đặt 1-2 câu hỏi làm rõ tình huống.
3. Cung cấp các quy định tham khảo sau:
{context_str[:2000]}"""
    else:
        prompt = f"{CORE_SYSTEM_INSTRUCTION}\n\n{history_str}CONTEXT (DỮ LIỆU LUẬT MỚI NHẤT TRÍCH XUẤT ĐƯỢC):\n{context_str}\n\nCÂU HỎI HIỆN TẠI:\n{query}"
        
    if safe_mode: prompt = redact_sensitive_data(prompt)
    model = get_gemini_model()
    safety_settings = {HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}
    
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings, stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
    except Exception as e:
        logger.error(f"Lỗi gọi Gemini QA: {e}")
        yield f"⚠️ Lỗi kết nối AI: {e}"

def process_user_message_stream(store: LawVectorStore, raw_msg: str, safe_mode: bool = True, history: List[Dict] = None, on_complete=None):
    full_response = ""
    greetings = ["chào", "hi", "hello", "xin chào", "chào bạn", "alo"]
    if raw_msg.strip().lower() in greetings:
        full_response = "Chào bạn, tôi là Trợ lý Luật sư AI. Tôi có thể giúp gì cho bạn về các vấn đề pháp lý doanh nghiệp hôm nay?"
        yield json.dumps({"type": "content", "text": full_response}) + "\n"
        if on_complete: on_complete(full_response)
        return
        
    yield json.dumps({"type": "status", "text": "Đang phân tích câu hỏi..."}) + "\n"
    nlp_result = smart_process_query(raw_msg)
    clean_text = nlp_result.get("corrected_text", raw_msg)
    mode = nlp_result.get("mode", "tra_cuu")
    
    if mode == "chatchit":
        full_response = "Chào bạn, tôi là Trợ lý Luật sư AI. Vui lòng đặt câu hỏi liên quan đến pháp lý doanh nghiệp nhé!"
        yield json.dumps({"type": "content", "text": full_response}) + "\n"
        if on_complete: on_complete(full_response)
        return
        
    if mode == "soan_thao":
        yield json.dumps({"type": "status", "text": "Đang soạn thảo văn bản..."}) + "\n"
        for chunk in draft_new_contract_stream(clean_text, safe_mode):
             full_response += chunk
             yield json.dumps({"type": "content", "text": chunk}) + "\n"
        
        disclaimer = "\n\n---\n> ⚠️ **BẢN NHÁP CHỜ DUYỆT (DRAFT FOR REVIEW)**\n> Mọi thông tin trên đây do AI tổng hợp và chỉ có giá trị tham khảo, không phải là tư vấn pháp lý chính thức. Quyết định cuối cùng cần được xem xét và chịu trách nhiệm bởi Luật sư hoặc Ban Giám đốc doanh nghiệp."
        full_response += disclaimer
        yield json.dumps({"type": "content", "text": disclaimer}) + "\n"
        
        if on_complete: on_complete(full_response)
        return

    yield json.dumps({"type": "status", "text": "Đang tra cứu dữ liệu luật..."}) + "\n"
    relevant_docs = store.search(clean_text, top_k=5)
    
    yield json.dumps({"type": "status", "text": "Đang kiểm duyệt ngữ cảnh..."}) + "\n"
    for chunk in call_gemini_qa_stream(mode, relevant_docs, clean_text, safe_mode, history):
        full_response += chunk
        yield json.dumps({"type": "content", "text": chunk}) + "\n"
        
    disclaimer = "\n\n---\n> ⚠️ **BẢN NHÁP CHỜ DUYỆT (DRAFT FOR REVIEW)**\n> Mọi thông tin trên đây do AI tổng hợp và chỉ có giá trị tham khảo, không phải là tư vấn pháp lý chính thức. Quyết định cuối cùng cần được xem xét và chịu trách nhiệm bởi Luật sư hoặc Ban Giám đốc doanh nghiệp."
    full_response += disclaimer
    yield json.dumps({"type": "content", "text": disclaimer}) + "\n"
    
    if on_complete: on_complete(full_response)

def analyze_contract_file_stream(store: LawVectorStore, contract_path: str | pathlib.Path, safe_mode: bool = True):
    contract_text = read_contract_file(contract_path)
    if not contract_text:
        yield json.dumps({"type": "content", "text": "❌ Lỗi đọc file. Vui lòng kiểm tra định dạng (hỗ trợ .docx, .pdf, .doc, .txt)."}) + "\n"
        return
        
    yield json.dumps({"type": "status", "text": "Đang phân tích dữ liệu hợp đồng..."}) + "\n"
    laws = store.search(contract_text[:1500].replace("\n", " "), top_k=5)
    law_block = "\n".join([f"- {c[0]}" for c in laws])
    
    prompt = f"{CORE_SYSTEM_INSTRUCTION}\nContext quy định liên quan: {law_block}.\nHãy rà soát, chấm điểm và chỉ ra rủi ro trong hợp đồng sau:\n{contract_text[:30000]}"
    if safe_mode: prompt = redact_sensitive_data(prompt)
    
    yield json.dumps({"type": "status", "text": "Đang sinh báo cáo rủi ro..."}) + "\n"
    model = get_gemini_model()
    safety_settings = {HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}
    
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings, stream=True)
        for chunk in response:
            if chunk.text: 
                yield json.dumps({"type": "content", "text": chunk.text}) + "\n"
    except Exception as e:
        logger.error(f"Lỗi AI phân tích hợp đồng: {e}")
        yield json.dumps({"type": "content", "text": f"⚠️ Lỗi kết nối AI: {e}"}) + "\n"

def analyze_contract_file(store, contract_path, safe_mode=True) -> str:
    # Fallback cho API cũ không stream
    res = []
    for chunk in analyze_contract_file_stream(store, contract_path, safe_mode):
        data = json.loads(chunk.strip())
        if data.get("type") == "content":
            res.append(data.get("text", ""))
    return "".join(res)

def build_or_load_store() -> LawVectorStore:
    store = LawVectorStore()
    if store.load():
        logger.info("Đã load index thành công.")
    else:
        docs = []
        for ext in ["*.docx", "*.pdf", "*.doc", "*.txt"]:
            docs.extend(list(DATA_DIR.glob(ext)))
        if docs:
            store.build_from_docs(docs)
            store.save()
    return store