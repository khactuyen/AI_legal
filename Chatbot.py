from __future__ import annotations

import os
import json
import pathlib
import logging
import re
import shutil
from typing import List, Tuple, Dict, Optional, Any

from dotenv import load_dotenv
from docx import Document

# Thư viện AI
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ============================================================
# 1. CẤU HÌNH HỆ THỐNG & LOGGING
# ============================================================
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

# Định nghĩa các đường dẫn thư mục
BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data_laws"
INDEX_DIR = BASE_DIR / "index_laws"
CONTRACT_DIR = BASE_DIR / "contracts"
TEMP_UPLOAD_DIR = BASE_DIR / "temp_uploads"

# Đường dẫn file Checklist mặc định (Cần đảm bảo file này tồn tại)
DEFAULT_CHECKLIST_PATH = BASE_DIR / "CheckList" / "Checklist-1.docx"

# Tự động tạo thư mục nếu chưa có
for p in [DATA_DIR, INDEX_DIR, CONTRACT_DIR, TEMP_UPLOAD_DIR]:
    p.mkdir(exist_ok=True)

# Load biến môi trường
load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#  đọc từ file .env 
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") 
GCS_LAWS_PREFIX = os.getenv("GCS_LAWS_PREFIX", "law/") # Mặc định là law/ nếu thiếu

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# ...

# Khởi tạo biến toàn cục cho Model
_GEMINI_MODEL = None

def get_gemini_model():
    """Singleton pattern để lấy Gemini Model, tránh khởi tạo nhiều lần."""
    global _GEMINI_MODEL
    if _GEMINI_MODEL is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("❌ LỖI: Thiếu GEMINI_API_KEY trong file .env")
        genai.configure(api_key=GEMINI_API_KEY)
        _GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")
    return _GEMINI_MODEL

# ============================================================
# 2. SYSTEM PROMPT (HUẤN LUYỆN CHI TIẾT - FULL TEXT)
# ============================================================
CORE_SYSTEM_INSTRUCTION = """
# ROLE
Bạn là AI Legal Assistant – một mô hình ngôn ngữ lớn được huấn luyện chuyên sâu về pháp lý dành cho DOANH NGHIỆP tại Việt Nam.

Bạn có ba nhiệm vụ chính:
1. TRA CỨU LUẬT THEO NGỮ NGHĨA 
2. PHÂN TÍCH HỢP ĐỒNG DỰA TRÊN CHECKLIST DO HỆ THỐNG CUNG CẤP 
3. LUẬT SƯ ONLINE – PHÂN TÍCH TÌNH HUỐNG THỰC TẾ CHO DOANH NGHIỆP 

Bạn phải trả lời bằng tiếng Việt, rõ ràng, logic, không bịa luật và chỉ dựa vào dữ liệu được cung cấp (CONTEXT).

────────────────────────────────────────
# DOMAIN – PHẠM VI PHÁP LÝ ĐƯỢC PHÉP XỬ LÝ

Bạn **được phép phân tích, tra cứu và giải thích pháp lý** thuộc toàn bộ các lĩnh vực sau:

## 1. **Luật Đầu tư**
- Luật Đầu tư 2020, Nghị định hướng dẫn.
- Quy định về hình thức đầu tư, ưu đãi đầu tư.

## 2. **Luật Doanh nghiệp**
- Thành lập doanh nghiệp, Loại hình doanh nghiệp (CTCP, TNHH...).
- Quyền và nghĩa vụ cổ đông, quản trị, vốn, điều lệ.

## 3. **Luật Thương mại**
- Hợp đồng mua bán hàng hóa, Cung ứng dịch vụ.
- Đại lý, phân phối, nhượng quyền, Logistics.
- Phạt vi phạm, bồi thường.

## 4. **Luật Quản lý Thuế**
- Quản lý thuế doanh nghiệp, Kê khai, nộp thuế.

## 5. **Thuế Giá trị Gia tăng (VAT)**
## 6. **Thuế Thu nhập Doanh nghiệp (TNDN)**
## 7. **Hóa đơn & Chứng từ**
## 8. **Văn bản sửa đổi – bổ sung**

────────────────────────────────────────
# PHẠM VI BỊ CẤM (OUT OF SCOPE)
Bạn **không được trả lời** các lĩnh vực: Hình sự, Dân sự cá nhân, Hôn nhân gia đình, Đất đai nhà ở cá nhân, Tôn giáo, Sức khỏe.
Nếu câu hỏi rơi vào các lĩnh vực này → trả lời: “Câu hỏi này nằm ngoài phạm vi pháp lý doanh nghiệp mà tôi được phép hỗ trợ.”

────────────────────────────────────────
# STYLE & BEHAVIOR – HÀNH VI TRẢ LỜI
Bạn phải:
- Trả lời bằng tiếng Việt, ngắn gọn, dễ hiểu. 
- Luôn dùng cấu trúc 4 phần:
  1) **Kết luận ngắn gọn**
  2) **Căn cứ pháp lý hoặc phân tích**
  3) **Giải thích chi tiết**
  4) **Cảnh báo và gợi ý hành động**
- Không được bịa thông tin. 
- Tự động che thông tin nhạy cảm (Safe Mode).

────────────────────────────────────────
# FINAL RULE (QUAN TRỌNG - HYBRID MODE)
1. ƯU TIÊN 1: Dựa vào thông tin trong phần **CONTEXT** (Dữ liệu nội bộ từ file luật đã nạp) để trả lời.
2. ƯU TIÊN 2 (NẾU CONTEXT TRỐNG): Nếu không tìm thấy thông tin trong Context nội bộ, bạn **ĐƯỢC PHÉP** sử dụng kiến thức pháp luật Việt Nam sẵn có của mình (Luật Doanh nghiệp, Luật Thương mại...) để trả lời.
   - Tuy nhiên, phải bắt đầu câu trả lời bằng câu: *"Dữ liệu nội bộ chưa cập nhật vấn đề này, nhưng theo kiến thức pháp luật hiện hành:..."*
"""

# ============================================================
# 3. CÁC HÀM TIỆN ÍCH & XỬ LÝ FILE
# ============================================================
# dowlad file từ GCS nếu có cấu hình
def download_law_docs_from_gcs() -> List[pathlib.Path]:
    """Hàm tải file từ Google Cloud Storage dựa trên .env"""
    # Kiểm tra xem có đủ thông tin GCS trong .env không
    if not GCS_BUCKET_NAME:
        logger.warning("⚠️ Chưa cấu hình GCS_BUCKET_NAME trong .env. Bỏ qua tải file Cloud.")
        return []

    try:
        from google.cloud import storage
        
        # Tự động dùng GOOGLE_APPLICATION_CREDENTIALS trong .env để login
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blobs = bucket.list_blobs(prefix=GCS_LAWS_PREFIX)
        
        local_paths = []
        logger.info(f"📡 Đang kết nối GCS Bucket: {GCS_BUCKET_NAME}...")
        
        for blob in blobs:
            if blob.name.lower().endswith(".docx"):
                # Lấy tên file (bỏ phần prefix law/)
                filename = blob.name.split("/")[-1]
                if not filename: continue # Bỏ qua folder ảo
                
                local_path = DATA_DIR / filename
                
                # Chỉ tải nếu file chưa có hoặc kích thước khác nhau (cập nhật)
                if not local_path.exists():
                    logger.info(f"⬇️ Đang tải: {filename}")
                    blob.download_to_filename(str(local_path))
                    local_paths.append(local_path)
                else:
                    # (Tùy chọn) Logic kiểm tra update có thể thêm ở đây
                    pass
                    
        if local_paths:
            logger.info(f"✅ Đã tải mới {len(local_paths)} văn bản luật từ Cloud.")
        else:
            logger.info("⚡ Dữ liệu Local đã đồng bộ với Cloud.")
            
        return local_paths

    except Exception as e:
        logger.error(f"❌ Lỗi kết nối GCS: {e}")
        return []

def redact_sensitive_data(text: str) -> str:
    """Hàm che thông tin nhạy cảm (SĐT, Email, CCCD)"""
    phone_pattern = r'\b(0\d{9,10})\b'
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    id_pattern = r'\b(\d{9}|\d{12})\b'
    
    text = re.sub(phone_pattern, "[SĐT ĐÃ CHE]", text)
    text = re.sub(email_pattern, "[EMAIL ĐÃ CHE]", text)
    text = re.sub(id_pattern, "[ID ĐÃ CHE]", text)
    return text

def auto_delete_temp_files(folder_path: pathlib.Path = TEMP_UPLOAD_DIR):
    """Xóa file tạm để bảo mật dữ liệu"""
    if not folder_path.exists(): return
    try:
        shutil.rmtree(folder_path)
        folder_path.mkdir()
        logger.info("Đã dọn dẹp thư mục tạm.")
    except Exception as e:
        logger.error(f"Lỗi khi xóa file tạm: {e}")

def read_docx(path: pathlib.Path) -> str:
    """Đọc nội dung file Word"""
    try:
        doc = Document(str(path))
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        return "\n".join(full_text)
    except Exception as e:
        logger.error(f"Lỗi đọc file docx {path}: {e}")
        return ""

def read_txt(path: pathlib.Path) -> str:
    """Đọc nội dung file Text"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Lỗi đọc file txt {path}: {e}")
        return ""

def read_contract_file(path: pathlib.Path | str) -> str:
    """Wrapper đọc file chung"""
    path_obj = pathlib.Path(path)
    if not path_obj.exists(): return ""
    if path_obj.suffix.lower() == ".docx":
        return read_docx(path_obj)
    elif path_obj.suffix.lower() == ".txt":
        return read_txt(path_obj)
    return ""

def chunk_text(text: str) -> List[str]:
    """
    STRUCTURAL CHUNKING: Cắt văn bản theo từng 'Điều luật'.
    """
    # 1. Kiểm tra xem văn bản có cấu trúc 'Điều...' không
    # Regex tìm: Xuống dòng + Chữ Điều + Số + Dấu chấm/hai chấm/khoảng trắng
    article_pattern = r'(?:\n|^)(Điều\s+\d+[:\.])'
    
    # Nếu tìm thấy ít nhất 3 'Điều', thì kích hoạt chế độ cắt theo Điều
    if len(re.findall(article_pattern, text)) > 3:
        # Tách văn bản
        parts = re.split(article_pattern, text)
        chunks = []
        
        # Phần đầu tiên (trước Điều 1) thường là Tiêu đề luật, giữ lại
        if parts[0].strip():
            chunks.append(f"[PHẦN MỞ ĐẦU]\n{parts[0].strip()}")
            
        # Ghép lại: Tiêu đề Điều (Điều 1.) + Nội dung Điều
        # re.split trả về: [Text đầu, 'Điều 1.', 'Nội dung...', 'Điều 2.', 'Nội dung...']
        for i in range(1, len(parts), 2):
            header = parts[i].strip() # VD: "Điều 1."
            content = parts[i+1].strip() if i+1 < len(parts) else ""
            
            full_article = f"{header} {content}"
            
            # Nếu Điều luật quá dài (>2000 ký tự), cắt nhỏ tiếp để vừa bộ nhớ
            if len(full_article) > 2000:
                # Cắt theo đoạn văn nhỏ (Paragraph)
                sub_chunks = [p for p in full_article.split("\n") if p.strip()]
                chunks.extend(sub_chunks)
            else:
                chunks.append(full_article)
                
        return chunks

    # 2. Fallback: Nếu không phải văn bản luật (vd: Hợp đồng), cắt theo đoạn văn
    return [p.strip() for p in text.split("\n") if len(p.strip()) > 50]

# ============================================================
# 4. LỚP QUẢN LÝ VECTOR STORE (FAISS)
# ============================================================
class LawVectorStore:
    def __init__(self, embed_model_name: str = EMBED_MODEL_NAME):
        self.embedder = SentenceTransformer(embed_model_name)
        self.index: Optional[faiss.IndexFlatIP] = None
        self.corpus_chunks: List[str] = []
        self.corpus_meta: List[Dict] = []
        self.bm25 = None
        self.reranker = None

    def build_from_docs(self, doc_paths: List[pathlib.Path]) -> None:
        logger.info("Bắt đầu build index từ %d file...", len(doc_paths))
        all_chunks = []
        all_meta = []
        
        for path in doc_paths:
            text = read_docx(path)
            if not text: continue
            
            chunks = chunk_text(text)
            for i, ch in enumerate(chunks):
                all_chunks.append(ch)
                all_meta.append({"source_file": path.name, "chunk_id": i})
        
        if not all_chunks:
            logger.warning("Không có dữ liệu text để build index.")
            return

        logger.info("Đang tạo embeddings cho %d chunks...", len(all_chunks))
        embeddings = self.embedder.encode(
            all_chunks, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True
        )
        
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        
        self.corpus_chunks = all_chunks
        self.corpus_meta = all_meta
        logger.info("Build index thành công.")

    def save(self, index_dir: pathlib.Path = INDEX_DIR) -> None:
        if self.index is None: return
        faiss.write_index(self.index, str(index_dir / "laws.faiss"))
        with (index_dir / "laws_meta.jsonl").open("w", encoding="utf-8") as f:
            for chunk, meta in zip(self.corpus_chunks, self.corpus_meta):
                json_record = json.dumps({"text": chunk, "meta": meta}, ensure_ascii=False)
                f.write(json_record + "\n")
        logger.info("Đã lưu index xuống ổ cứng.")

    def load(self, index_dir: pathlib.Path = INDEX_DIR) -> bool:
        faiss_path = index_dir / "laws.faiss"
        meta_path = index_dir / "laws_meta.jsonl"
        
        if not (faiss_path.exists() and meta_path.exists()):
            return False
        
        logger.info("Đang load index từ ổ cứng...")
        self.index = faiss.read_index(str(faiss_path))
        self.corpus_chunks = []
        self.corpus_meta = []
        
        with meta_path.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.corpus_chunks.append(rec["text"])
                self.corpus_meta.append(rec["meta"])
        
        logger.info("Load index thành công. Tổng số vectors: %d", self.index.ntotal)
        return True

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, Dict, float]]:
        """
        TRUY XUẤT TỐI ƯU CHO CẤU TRÚC 'ĐIỀU LUẬT':
        Kết hợp: CoT (Tư duy) + Hybrid (Vector & Keyword) + Re-ranking (Chấm điểm)
        """
        if self.index is None: return []
        
        # --- BƯỚC 1: MỞ RỘNG TRUY VẤN (CoT) ---
        # Để đảm bảo không sót điều luật nào liên quan
        queries = generate_search_queries(query)
        queries.append(query) # Luôn giữ câu gốc
        
        # Tập hợp các ứng viên (Candidate Set)
        candidates = {} # Dùng dict để dedup và cộng dồn điểm: {chunk_idx: score}
        
        # --- BƯỚC 2: TÌM KIẾM DIỆN RỘNG (HYBRID SEARCH) ---
        # Lấy số lượng lớn để lọc dần
        fetch_k = 30 
        
        for q in queries:
            # 2.1 Vector Search (FAISS) - Hiểu ngữ nghĩa
            q_emb = self.embedder.encode([q], convert_to_numpy=True, normalize_embeddings=True)
            v_scores, v_idxs = self.index.search(q_emb, fetch_k)
            
            for score, idx in zip(v_scores[0], v_idxs[0]):
                if idx < 0 or idx >= len(self.corpus_chunks): continue
                
                # Chuẩn hóa điểm Vector (0-1)
                if idx not in candidates: candidates[idx] = 0.0
                candidates[idx] += float(score) * 0.7 # Trọng số Vector: 70%

            # 2.2 Keyword Search (BM25) - Bắt chính xác từ chuyên ngành/số điều
            if self.bm25:
                tokenized_query = q.split()
                # BM25 trả về top docs, ta cần map ngược lại index
                # (Lưu ý: Trong production cần map hiệu quả hơn, ở đây minh họa logic)
                bm25_scores = self.bm25.get_scores(tokenized_query)
                # Lấy top fetch_k chỉ số có điểm cao nhất
                top_bm25_idxs = np.argsort(bm25_scores)[::-1][:fetch_k]
                
                for idx in top_bm25_idxs:
                    if idx < 0 or idx >= len(self.corpus_chunks): continue
                    
                    # Chuẩn hóa điểm BM25 (tương đối) và cộng vào
                    # (BM25 score không có giới hạn, ta scale nhẹ để nó đóng vai trò bổ trợ)
                    if idx not in candidates: candidates[idx] = 0.0
                    candidates[idx] += 0.3 # Trọng số Keyword: 30% (tượng trưng)

        # Chuyển candidates thành list để xử lý tiếp
        raw_results = []
        for idx, score in candidates.items():
            raw_results.append({
                "text": self.corpus_chunks[idx],
                "meta": self.corpus_meta[idx],
                "score": score
            })

        # --- BƯỚC 3: BỘ LỌC NĂM (METADATA FILTERING) ---
        # Loại bỏ luật cũ nếu có luật mới cùng nhóm
        max_year_map = {}
        for item in raw_results:
            group = item['meta'].get('law_group', 'unknown')
            year = item['meta'].get('year', 0)
            if group != 'unknown':
                if group not in max_year_map or year > max_year_map[group]:
                    max_year_map[group] = year
        
        filtered_results = []
        for item in raw_results:
            group = item['meta'].get('law_group', 'unknown')
            year = item['meta'].get('year', 0)
            if group in max_year_map and year < max_year_map[group]:
                continue # Bỏ luật cũ
            filtered_results.append(item)

        if not filtered_results: return []

        # --- BƯỚC 4: TINH CHỈNH CUỐI CÙNG (RE-RANKING) ---
        final_ranking = []
        if self.reranker:
            # Cross-Encoder đọc kỹ nội dung từng Điều luật để chọn ra cái khớp nhất
            pairs = [[query, item['text']] for item in filtered_results]
            rerank_scores = self.reranker.predict(pairs)
            for i, score in enumerate(rerank_scores):
                item = filtered_results[i]
                year_boost = item['meta'].get('year', 0) * 0.0001
                final_ranking.append((item['text'], item['meta'], score + year_boost))
        else:
            # Nếu chưa cài Reranker, dùng điểm số của Hybrid Search
            for item in filtered_results:
                year_boost = item['meta'].get('year', 0) * 0.0001
                final_ranking.append((item['text'], item['meta'], item['score'] + year_boost))
            
        # Sắp xếp & Cắt Top K
        final_ranking.sort(key=lambda x: x[2], reverse=True)
        
        return final_ranking[:top_k]
# ============================================================
# 5. CÔNG CỤ NLP THÔNG MINH (SỬA LỖI CHÍNH TẢ & Ý ĐỊNH)
# ============================================================

def smart_process_query(raw_query: str) -> dict:
    """
    Dùng AI để tiền xử lý câu hỏi người dùng.
    - Sửa lỗi chính tả (k -> không, hđ -> hợp đồng)
    - Phân loại ý định (Mode) chính xác.
    """
    model = get_gemini_model()
    
    system_prompt = """
    Bạn là bộ xử lý ngôn ngữ tự nhiên (NLP Processor) cho hệ thống pháp lý.
    
    NHIỆM VỤ:
    1. Sửa lỗi chính tả, viết tắt, teencode trong câu input thành tiếng Việt chuẩn chỉnh.
    2. Xác định ý định (Mode) của người dùng theo danh sách sau:
       - "soan_thao": Nếu user muốn viết mới, soạn thảo, làm hợp đồng/văn bản.
       - "hop_dong": Nếu user muốn kiểm tra, soát lỗi, phân tích rủi ro, chấm điểm hợp đồng đã có.
       - "luat_su_online": Nếu user hỏi tư vấn tình huống, tranh chấp, cách xử lý vấn đề cụ thể.
       - "tra_cuu": Nếu user hỏi kiến thức luật, quy định, thủ tục hành chính, hồ sơ cần chuẩn bị.
       - "chatchit": Nếu user chào hỏi xã giao (hi, hello, cảm ơn) hoặc hỏi không liên quan luật.
    
    OUTPUT ĐỊNH DẠNG JSON:
    {
        "corrected_text": "câu đã sửa", 
        "mode": "tên mode"
    }
    """
    
    try:
        response = model.generate_content(f"{system_prompt}\n\nINPUT: {raw_query}")
        # Clean JSON string
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Lỗi Smart NLP: {e}")
        # Fallback nếu lỗi
        return {"corrected_text": raw_query, "mode": "tra_cuu"}

# ============================================================
# 6. CÁC HÀM XỬ LÝ CHỨC NĂNG (LOGIC CHÍNH)
# ============================================================
def detect_contract_status(text: str) -> Dict:
    """
    Phân loại xem đây là Hợp đồng Mẫu (Template) hay Đã điền (Final).
    """
    model = get_gemini_model()
    
    # Prompt chuyên dụng để phân loại
    prompt = f"""
    Bạn là chuyên gia phân loại tài liệu.
    Nhiệm vụ: Xác định trạng thái của văn bản hợp đồng dưới đây.
    
    INPUT TEXT:
    {text[:500]}  # Chỉ cần đọc 500 ký tự đầu là đủ biết
    
    TIÊU CHÍ:
    1. **TEMPLATE (Bản mẫu):** Chứa nhiều ký tự giữ chỗ (...., ____), các trường thông tin chưa được điền (VD: [Tên Bên A], [Ngày...]), ngôn ngữ chung chung.
    2. **FINAL (Bản hoàn thiện):** Các trường thông tin (Tên, Địa chỉ, MST, Số tiền) đã được điền cụ thể. Không còn nhiều ký tự giữ chỗ.
    
    OUTPUT JSON:
    {{
        "status": "TEMPLATE" hoặc "FINAL",
        "confidence": <Độ tin cậy 0-100>,
        "reason": "Lý do ngắn gọn (VD: Còn nhiều dòng kẻ trống...)"
    }}
    """
    try:
        res = model.generate_content(prompt).text
        clean_json = res.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        logger.error(f"Lỗi phân loại: {e}")
        return {"status": "UNKNOWN", "confidence": 0, "reason": "Lỗi AI"}
def generate_search_queries(user_question: str) -> List[str]:
    """
    CoT Framework: Phân tích câu hỏi để sinh ra các từ khóa tìm kiếm tối ưu hơn.
    """
    model = get_gemini_model()
    
    prompt = f"""
    Bạn là chuyên gia tra cứu pháp lý.
    Câu hỏi người dùng: "{user_question}"
    
    NHIỆM VỤ:
    Hãy phân tích câu hỏi này và liệt kê 3 cụm từ khóa tìm kiếm (Search Queries) ngắn gọn, xác đáng nhất để tra cứu trong văn bản luật.
    Tách các vấn đề phức tạp thành các vấn đề đơn giản.
    
    Ví dụ: "Công ty đuổi việc bà bầu ăn trộm" 
    -> Output: ["kỷ luật sa thải người lao động", "bảo vệ lao động nữ mang thai", "xử lý vi phạm trộm cắp tại nơi làm việc"]
    
    OUTPUT ĐỊNH DẠNG JSON (Chỉ trả về mảng string):
    ["query1", "query2", "query3"]
    """
    try:
        resp = model.generate_content(prompt)
        clean_json = resp.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        logger.warning(f"Lỗi CoT generation: {e}")
        # Nếu lỗi thì trả về chính câu hỏi gốc (Fallback)
        return [user_question]

def safe_generate_content(prompt: str, safe_mode: bool = False) -> str:
    """Hàm gọi Gemini có xử lý lỗi và Safe Mode"""
    if safe_mode:
        prompt = redact_sensitive_data(prompt)
    
    model = get_gemini_model()
    try:
        # Cấu hình safety lỏng để tránh chặn nhầm nội dung pháp lý
        safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        resp = model.generate_content(prompt, safety_settings=safety_settings)
        return resp.text
    except Exception as e:
        logger.error(f"Lỗi khi gọi Gemini: {e}")
        return f"⚠️ Hệ thống đang bận hoặc gặp lỗi kết nối AI. Chi tiết: {str(e)}"

def draft_new_contract(requirement: str, safe_mode: bool = False) -> str:
    """Chức năng soạn thảo hợp đồng mới"""
    prompt = f"""
    {CORE_SYSTEM_INSTRUCTION}
    
    === YÊU CẦU CỤ THỂ CỦA USER ===
    User muốn SOẠN THẢO văn bản: "{requirement}"
    
    === NHIỆM VỤ ===
    Hãy soạn thảo một bản hợp đồng hoàn chỉnh, chi tiết, chuẩn pháp lý Việt Nam.
    Bao gồm: Quốc hiệu tiêu ngữ, Tên hợp đồng, Căn cứ pháp lý, Thông tin các bên, Các điều khoản chi tiết và Phần ký tên.
    """
    return safe_generate_content(prompt, safe_mode=safe_mode)

def analyze_contract_file(store, contract_path, checklist_text=None, safe_mode=True) -> str:
    """
    QUY TRÌNH THÔNG MINH: Phân loại -> Chọn chiến thuật phân tích phù hợp.
    """
    contract_text = read_contract_file(contract_path)
    if not contract_text: return "❌ Lỗi: Không đọc được nội dung file hợp đồng."

    # 1. NHẬN DIỆN TRẠNG THÁI HỢP ĐỒNG
    status_info = detect_contract_status(contract_text)
    doc_type = status_info.get("status", "FINAL")
    reason = status_info.get("reason", "")
    
    # Log trạng thái để debug
    logger.info(f"Phân loại hợp đồng: {doc_type} | Lý do: {reason}")

    # 2. Chuẩn bị Checklist & RAG
    if not checklist_text and DEFAULT_CHECKLIST_PATH.exists():
        checklist_text = read_contract_file(DEFAULT_CHECKLIST_PATH)
    else: checklist_text = "Tiêu chuẩn Luật Thương mại & Dân sự."
    
    query = contract_text[:1500].replace("\n", " ")
    laws = store.search(query, top_k=8)
    law_block = "\n".join([f"- {c[0]}" for c in laws])

    # 3. XÂY DỰNG PROMPT THEO TỪNG LOẠI
    
    # --- CHIẾN THUẬT CHO BẢN MẪU (TEMPLATE) ---
    if doc_type == "TEMPLATE":
        system_instruction = """
        ⚠️ PHÁT HIỆN: ĐÂY LÀ HỢP ĐỒNG MẪU (TEMPLATE/DRAFT).
        NHIỆM VỤ CỦA BẠN:
        1. Đánh giá chất lượng của biểu mẫu này (có chuẩn pháp lý không?).
        2. Hướng dẫn người dùng cách điền vào các chỗ trống (Placeholder).
        3. Cảnh báo các điều khoản còn thiếu trong mẫu.
        """
    # --- CHIẾN THUẬT CHO BẢN HOÀN THIỆN (FINAL) ---
    else:
        system_instruction = """
        ✅ PHÁT HIỆN: ĐÂY LÀ HỢP ĐỒNG ĐÃ ĐIỀN THÔNG TIN (FINAL/EXECUTED).
        NHIỆM VỤ CỦA BẠN:
        1. Tìm rủi ro pháp lý cụ thể cho các bên đã nêu tên.
        2. Kiểm tra tính hợp lệ của thông tin đã điền (nếu có thể suy luận).
        3. Soi kỹ các con số, thời hạn, phạt vi phạm.
        """

    prompt_final = f"""
    {CORE_SYSTEM_INSTRUCTION}
    
    {system_instruction}
    
    === KẾT QUẢ PHÂN LOẠI ĐẦU VÀO ===
    - Trạng thái: {doc_type}
    - Nhận định sơ bộ: {reason}
    
    === DỮ LIỆU ===
    - Checklist: {checklist_text}
    - Luật tham chiếu: {law_block}
    - Hợp đồng: {contract_text[:30000]}
    
    === YÊU CẦU OUTPUT (Markdown) ===
    
    ## 1. NHẬN DIỆN TÀI LIỆU
    * **Loại văn bản:** {doc_type} (Dựa trên: {reason})
    * **Tóm tắt:** ...
    
    ## 2. PHÂN TÍCH CHI TIẾT (Validation)
    (Nếu là Template: Chỉ ra các mục cần điền và rủi ro nếu điền sai)
    (Nếu là Final: Chỉ ra rủi ro pháp lý của các điều khoản đã chốt)
    
    ### 🔴 [VẤN ĐỀ TRỌNG YẾU]
    ...
    
    ## 3. GỢI Ý TỐI ƯU (Optimization)
    ...
    
    ## 4. ĐIỂM SỐ (JSON)
    ```json
    {{
      "score": <0-100>,
      "risk_level": "<CAO/TRUNG BÌNH/THẤP>",
      "risk_summary": "<...>"
    }}
    ```
    """
    return safe_generate_content(prompt_final, safe_mode)

def build_or_load_store() -> LawVectorStore:
    """Hàm khởi tạo hệ thống"""
    store = LawVectorStore()
    
    # --- BƯỚC 1: ĐỒNG BỘ DỮ LIỆU TỪ CLOUD (MỚI THÊM) ---
    download_law_docs_from_gcs()
    # ---------------------------------------------------

    # Sau khi tải xong mới load index
    if store.load():
        logger.info("Đã load index thành công.")
    else:
        logger.info("Không tìm thấy index, bắt đầu quét thư mục data_laws...")
        docs = list(DATA_DIR.glob("*.docx"))
        if docs:
            store.build_from_docs(docs)
            store.save()
        else:
            logger.warning("Cảnh báo: Thư mục data_laws trống! Chatbot sẽ chạy bằng kiến thức nền.")
    return store

# ============================================================
# 7. HÀM XỬ LÝ TRUNG TÂM (MAIN PROCESSOR)
# ============================================================

def call_gemini_qa(mode: str, relevant_docs: List[Tuple[str, Dict, float]], query: str, safe_mode: bool = True) -> str:
    """Gọi Gemini để trả lời câu hỏi dựa trên kết quả RAG."""
    if not relevant_docs:
        context_str = "Không tìm thấy dữ liệu nội bộ liên quan."
    else:
        # Chỉ lấy phần text của các document được tìm thấy
        context_str = "\n\n".join([f"- {doc[0]}" for doc in relevant_docs])
    
    prompt = f"""
    {CORE_SYSTEM_INSTRUCTION}
    
    === NGỮ CẢNH TỪ DỮ LIỆU LUẬT (CONTEXT) ===
    {context_str}
    
    === CÂU HỎI CỦA NGƯỜI DÙNG ===
    {query}
    
    === YÊU CẦU ĐẶC BIỆT ===
    Bạn hãy đóng vai AI Legal Assistant, trả lời theo đúng cấu trúc 4 phần đã quy định.
    Nếu Context phía trên không đủ để trả lời, bạn được phép dùng kiến thức luật pháp bên ngoài nhưng phải ghi chú rõ điều này.
    """
    return safe_generate_content(prompt, safe_mode)

def process_user_message(store: LawVectorStore, raw_msg: str, safe_mode: bool = True) -> str:
    """
    Hàm duy nhất mà Giao diện (UI) cần gọi.
    Nó tự động: Sửa lỗi chính tả -> Phân loại Mode -> Gọi hàm xử lý tương ứng.
    """
    # BƯỚC 1: Dùng AI để sửa lỗi chính tả và đoán ý
    logger.info(f"Nhận tin nhắn gốc: {raw_msg}")
    nlp_result = smart_process_query(raw_msg)
    
    clean_text = nlp_result.get("corrected_text", raw_msg)
    mode = nlp_result.get("mode", "tra_cuu")
    
    logger.info(f"-> Sau khi xử lý: '{clean_text}' | Mode: {mode}")

    # BƯỚC 2: Điều hướng xử lý theo Mode
    if mode == "chatchit":
        return "Chào bạn, tôi là Trợ lý Luật sư AI. Tôi có thể giúp gì cho bạn về các vấn đề pháp lý doanh nghiệp hôm nay?"
    
    if mode == "soan_thao":
        return draft_new_contract(clean_text, safe_mode)
    
    # BƯỚC 3: Nếu là Tra cứu hoặc Tư vấn -> Dùng RAG
    # Tìm kiếm luật liên quan (Dùng text đã sửa lỗi để tìm cho chính xác)
    relevant_docs = store.search(clean_text, top_k=5)
    
    # Gọi Gemini trả lời
    return call_gemini_qa(mode, relevant_docs, clean_text, safe_mode)