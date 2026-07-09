import os
import json
import pathlib
import logging
import re
import pickle
import numpy as np
from typing import List, Tuple, Dict, Optional, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from pyvi import ViTokenizer

from knowledge_graph import LegalKnowledgeGraph, extract_triplets_llm_batch
from hyper_extract import HyperExtractor, extract_deep_features_batch

# Config constants
from chatbot.config import (
    EMBED_MODEL_NAME, QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION,
    DATA_DIR, INDEX_DIR, BASE_DIR
)
# Loaders
from chatbot.utils.document_loaders import read_docx, read_txt, read_doc, read_pdf
# Text processing
from chatbot.utils.text_processing import (
    extract_keywords_local, get_year_from_filename, get_law_base_name, chunk_text
)
# Services
from chatbot.services.llm_service import generate_search_queries
from chatbot.services.rerank_service import rerank_with_llm

logger = logging.getLogger("chatbot.database.vector_store")

class LawVectorStore:
    def __init__(self, embed_model_name: str = EMBED_MODEL_NAME, rerank_model_name: str = "BAAI/bge-reranker-base"):
        self.embedder = SentenceTransformer(embed_model_name)
        self.embed_dim = self.embedder.get_sentence_embedding_dimension()
        self.client: Optional[QdrantClient] = None
        self.corpus_chunks: List[str] = []
        self.corpus_meta: List[Dict] = []
        self.bm25: Optional[BM25Okapi] = None
        self.kg = LegalKnowledgeGraph()
        self.hyper = HyperExtractor()
        self.reranker_name = rerank_model_name
        self._reranker = None
        self._onnx_session = None
        self._onnx_tokenizer = None
        
        try:
            if QDRANT_HOST == "memory":
                self.client = QdrantClient(":memory:")
                logger.info("Đã kết nối Qdrant in-memory (không cần server)")
            elif QDRANT_HOST == "local":
                self.client = QdrantClient(path=str(INDEX_DIR / "qdrant_storage"))
                logger.info("Đã kết nối Qdrant local on-disk (không cần server)")
            else:
                self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
                logger.info(f"Đã kết nối Qdrant tại {QDRANT_HOST}:{QDRANT_PORT}")
        except Exception as e:
            logger.warning(f"Không thể kết nối Qdrant tại {QDRANT_HOST}:{QDRANT_PORT} ({e}). Tự động fallback sang Qdrant local in-memory...")
            try:
                self.client = QdrantClient(":memory:")
                logger.info("Đã kết nối Qdrant in-memory thành công.")
            except Exception as ex:
                logger.error(f"Lỗi khởi tạo Qdrant in-memory: {ex}")
                self.client = None

    def _init_onnx_reranker(self) -> bool:
        onnx_path = INDEX_DIR / "reranker.onnx"
        tokenizer_path = INDEX_DIR / "reranker_tokenizer"
        if onnx_path.exists() and tokenizer_path.exists():
            try:
                import onnxruntime as ort
                from transformers import AutoTokenizer
                self._onnx_session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                self._onnx_tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
                logger.info("Đã khởi tạo ONNX Reranker thành công!")
                return True
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo ONNX Reranker: {e}. Sẽ fallback sang CrossEncoder.")
        return False

    def _rerank_cross_encoder(self, query: str, candidates: List[Tuple[str, Dict, float]], top_n: int = 15) -> List[Tuple[str, Dict, float]]:
        if not candidates:
            return []
        
        if self._onnx_session is None and self._reranker is None:
            if not self._init_onnx_reranker():
                try:
                    logger.info(f"Đang khởi tạo CrossEncoder: {self.reranker_name}...")
                    self._reranker = CrossEncoder(self.reranker_name)
                    logger.info("Khởi tạo CrossEncoder thành công!")
                except Exception as e:
                    logger.error(f"Lỗi khởi tạo CrossEncoder: {e}. Sử dụng bảng xếp hạng gốc.")
                    return candidates[:top_n]
        
        try:
            if self._onnx_session is not None and self._onnx_tokenizer is not None:
                pairs = [[query, c[0][:512]] for c in candidates]
                encoded = self._onnx_tokenizer(
                    [p[0] for p in pairs], [p[1] for p in pairs],
                    return_tensors="np", max_length=512, padding=True, truncation=True
                )
                outputs = self._onnx_session.run(None, {
                    "input_ids": encoded["input_ids"],
                    "attention_mask": encoded["attention_mask"]
                })
                scores = outputs[0].flatten().tolist()
            else:
                pairs = [[query, c[0]] for c in candidates]
                scores = self._reranker.predict(pairs).tolist()
                
            scored_candidates = []
            for i, score in enumerate(scores):
                scored_candidates.append((candidates[i][0], candidates[i][1], float(score)))
                
            scored_candidates.sort(key=lambda x: x[2], reverse=True)
            logger.info(f"Reranker đã xếp hạng xong {len(candidates)} ứng viên.")
            return scored_candidates[:top_n]
        except Exception as e:
            logger.error(f"Lỗi trong quá trình Reranking: {e}")
            return candidates[:top_n]

    def _ensure_collection(self):
        if self.client is None:
            return
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if QDRANT_COLLECTION not in collections:
                self.client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=self.embed_dim, distance=Distance.COSINE)
                )
                logger.info(f"Đã tạo collection '{QDRANT_COLLECTION}' trong Qdrant.")
        except Exception as e:
            logger.error(f"Lỗi tạo collection Qdrant: {e}")

    def build_from_docs(self, doc_paths: List[pathlib.Path]) -> None:
        if self.client is None:
            logger.error("Không thể build index: Chưa kết nối Qdrant.")
            return
            
        self._ensure_collection()
        
        try:
            self.client.delete_collection(QDRANT_COLLECTION)
            self.client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=self.embed_dim, distance=Distance.COSINE)
            )
        except Exception:
            pass
            
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
        
        logger.info(f"Đang encode {len(all_chunks)} chunks...")
        embeddings = self.embedder.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
        
        batch_size = 100
        for batch_start in range(0, len(all_chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(all_chunks))
            points = []
            for idx in range(batch_start, batch_end):
                points.append(PointStruct(
                    id=idx,
                    vector=embeddings[idx].tolist(),
                    payload={
                        "text": all_chunks[idx],
                        **all_meta[idx]
                    }
                ))
            self.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        
        logger.info(f"Đã upload {len(all_chunks)} vectors lên Qdrant.")
        
        tokenized_corpus = [ViTokenizer.tokenize(meta["bm25_input"]).split() for meta in all_meta]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Bắt đầu trích xuất Knowledge Graph bằng Gemini cho {len(all_chunks)} chunks...")
        
        # We need to construct chunk dicts for triplets extraction
        chunk_dicts = []
        for text, meta in zip(all_chunks, all_meta):
            chunk_dicts.append({"text": text, "book": meta["book"], "chapter": meta["chapter"], "section": meta["section"], "article": meta["article"]})
            
        all_triplets = extract_triplets_llm_batch(chunk_dicts)
        for i, triplets in enumerate(all_triplets):
            self.kg.add_triplets(i, triplets)
        logger.info("Hoàn tất xây dựng Knowledge Graph.")
        
        logger.info(f"Bắt đầu trích xuất Hyper-Extract (Deep Index) cho {len(all_chunks)} chunks...")
        all_deep_features = extract_deep_features_batch(chunk_dicts)
        for i, features in enumerate(all_deep_features):
            self.hyper.build_hyperedges(features.get("hyperedges", []), i)
            self.hyper.add_timeline_events(features.get("timeline", []), i)
        logger.info("Hoàn tất xây dựng Hyper-Extract.")
        
        self.corpus_chunks = all_chunks
        self.corpus_meta = all_meta

    def save(self, index_dir: pathlib.Path = INDEX_DIR) -> None:
        if not self.corpus_chunks: return
        
        with (index_dir / "laws_meta.jsonl").open("w", encoding="utf-8") as f:
            for chunk, meta in zip(self.corpus_chunks, self.corpus_meta):
                f.write(json.dumps({"text": chunk, "meta": meta}, ensure_ascii=False) + "\n")
        if self.bm25:
            with open(index_dir / "bm25.pkl", "wb") as f: pickle.dump(self.bm25, f)
        self.kg.save(index_dir / "graph.pkl")
        self.hyper.save(index_dir / "graph.pkl")

    def load(self, index_dir: pathlib.Path = INDEX_DIR) -> bool:
        meta_path = index_dir / "laws_meta.jsonl"
        bm25_path = index_dir / "bm25.pkl"
        
        if not meta_path.exists(): return False
        if self.client is None: return False
        
        try:
            collection_info = self.client.get_collection(QDRANT_COLLECTION)
            if collection_info.points_count == 0:
                logger.warning("Qdrant collection trống. Cần build lại index.")
                return False
        except Exception:
            logger.warning("Qdrant collection chưa tồn tại.")
            return False
        
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
        self.hyper.load(index_dir / "graph.pkl")
        
        logger.info(f"Loaded {len(self.corpus_chunks)} chunks metadata. Qdrant has {collection_info.points_count} vectors.")
        return True

    def search(self, query: str, top_k: int = 5, use_reranker: bool = True, use_llm_rerank: bool = False, use_query_expansion: bool = False, use_hyde: bool = False) -> List[Tuple[str, Dict, float]]:
        if self.client is None or not self.corpus_chunks: return []
        
        # 1. Query Expansion (Mở rộng truy vấn)
        if use_query_expansion:
            queries = generate_search_queries(query)
            if query not in queries: queries.append(query)
        else:
            queries = [query]
            
        # 2. HyDE (Hypothetical Document Embeddings)
        hyde_doc = None
        if use_hyde:
            from chatbot.services.llm_service import generate_hyde_document
            hyde_doc = generate_hyde_document(query)
            
        fetch_k = 20
        all_v_results = {}
        all_bm25_results = {}
        
        # Tìm kiếm ngữ nghĩa (Dense Vector Search) trên câu hỏi gốc + HyDE document
        semantic_queries = [query]
        if hyde_doc:
            semantic_queries.append(hyde_doc)
            
        for sq in semantic_queries:
            q_emb = self.embedder.encode([sq], convert_to_numpy=True, normalize_embeddings=True)
            try:
                hits = self.client.query_points(
                    collection_name=QDRANT_COLLECTION,
                    query=q_emb[0].tolist(),
                    limit=fetch_k,
                    with_payload=True,
                ).points
                for hit in hits:
                    idx = hit.id
                    score = hit.score
                    if 0 <= idx < len(self.corpus_chunks):
                        all_v_results[idx] = max(all_v_results.get(idx, -1), float(score))
            except Exception as e:
                logger.error(f"Lỗi Qdrant search: {e}")
            
        # Tìm kiếm từ khóa (BM25) trên các từ khóa mở rộng (Query Expansion)
        for q in queries:
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
            
        top_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        seed_entities = []
        for idx, _ in top_candidates:
            if idx < len(self.corpus_meta):
                ents = [e.strip() for e in self.corpus_meta[idx].get("entities", "").split(",") if e.strip()]
                seed_entities.extend(ents)
                
        related_chunk_ids = self.kg.find_related_chunks(seed_entities, depth=2)
        
        graph_bonus = 0.05
        for idx in related_chunk_ids:
            if idx in rrf_scores:
                rrf_scores[idx] += graph_bonus
            else:
                rrf_scores[idx] = graph_bonus / 2.0
                
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        registry_path = BASE_DIR / "law_registry.json"
        registry = {}
        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                try:
                    registry = json.load(f)
                except Exception:
                    pass

        filtered_results = []
        seen_law_bases = {}
        
        max_candidates = max(25, top_k * 2) if use_llm_rerank else (10 if use_reranker else top_k)
        
        for idx, score in sorted_candidates:
            if idx >= len(self.corpus_meta): continue
            meta = self.corpus_meta[idx]
            law_base = meta.get("law_base", "")
            year = meta.get("year", 0)
            
            law_id = meta.get("source_file", "").rsplit(".", 1)[0]
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
                
            rich_chunk = self.corpus_chunks[idx]
            if meta.get("prev_title") or meta.get("next_title"):
                rich_chunk += f"\n(Liên quan: {meta.get('prev_title', '')} | {meta.get('next_title', '')})"
            
            filtered_results.append((rich_chunk, meta, score))
            if len(filtered_results) >= max_candidates:
                break
                
        if use_reranker and filtered_results:
            top_n = max(10, top_k) if use_llm_rerank else top_k
            filtered_results = self._rerank_cross_encoder(query, filtered_results, top_n=top_n)
            
        if use_llm_rerank and filtered_results:
            filtered_results = rerank_with_llm(query, filtered_results, top_k=top_k)
            
        return filtered_results[:top_k]


    def search_deep(self, query: str, top_k: int = 15) -> Dict[str, Any]:
        fast_results = self.search(query, top_k=top_k, use_reranker=True, use_llm_rerank=True, use_query_expansion=True)
        
        context_chunks = []
        chunk_indices = set()
        for text, meta, score in fast_results:
            context_chunks.append({"text": text, "meta": meta})
            try:
                idx = self.corpus_chunks.index(text)
                chunk_indices.add(idx)
            except ValueError:
                pass
                
        relevant_timeline = []
        for ev in self.hyper.timeline_events:
            if ev.get("chunk_id") in chunk_indices:
                relevant_timeline.append(ev)
                
        return {
            "fast_context": context_chunks,
            "timeline": relevant_timeline,
            "hyper_info": "Tính năng tra cứu Siêu Đồ Thị đang phân tích rủi ro đa chiều..."
        }

    def update_index(self, doc_path: pathlib.Path) -> bool:
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
        
        embeddings = self.embedder.encode(new_chunks, convert_to_numpy=True, normalize_embeddings=True)
        if self.client is None:
            logger.error("Không thể update: Chưa kết nối Qdrant.")
            return False
        self._ensure_collection()
        
        points = []
        for i, (chunk, meta) in enumerate(zip(new_chunks, new_meta)):
            points.append(PointStruct(
                id=offset + i,
                vector=embeddings[i].tolist(),
                payload={"text": chunk, **meta}
            ))
        self.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        
        self.corpus_chunks.extend(new_chunks)
        self.corpus_meta.extend(new_meta)
        tokenized_corpus = [ViTokenizer.tokenize(meta["bm25_input"]).split() for meta in self.corpus_meta]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Cập nhật Knowledge Graph cho {len(chunk_dicts)} chunks mới...")
        new_triplets = extract_triplets_llm_batch(chunk_dicts)
        for i, triplets in enumerate(new_triplets):
            self.kg.add_triplets(offset + i, triplets)
            
        logger.info(f"Cập nhật Hyper-Extract cho {len(chunk_dicts)} chunks mới...")
        new_deep_features = extract_deep_features_batch(chunk_dicts)
        for i, features in enumerate(new_deep_features):
            self.hyper.build_hyperedges(features.get("hyperedges", []), offset + i)
            self.hyper.add_timeline_events(features.get("timeline", []), offset + i)
            
        self.save()
        logger.info(f"Đã cập nhật động (Dynamic Index) cho file: {doc_path.name}")
        return True

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
