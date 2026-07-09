import networkx as nx
import pickle
import pathlib
import logging
import json
import os
import google.generativeai as genai
from typing import List, Dict, Any

logger = logging.getLogger("HyperExtract")

class HyperExtractor:
    def __init__(self):
        # Hypergraph có thể được mô phỏng bằng Bipartite Graph trong NetworkX
        # Tập đỉnh V: Các entities
        # Tập đỉnh E: Các hyperedges (mỗi hyperedge là 1 node nối với nhiều entities)
        self.hypergraph = nx.Graph() 
        self.timeline_events: List[Dict[str, Any]] = []

    def build_hyperedges(self, hyperedges_data: List[Dict[str, Any]], chunk_id: int):
        """
        hyperedges_data: [{"event": "Tranh chấp hợp đồng", "entities": ["CTY A", "CTY B", "Luật sư C"]}, ...]
        """
        for edge in hyperedges_data:
            event_name = edge.get("event", "").strip()
            entities = edge.get("entities", [])
            if not event_name or not entities:
                continue
                
            # Tạo node đại diện cho Hyperedge (Event)
            event_node = f"EVENT_{event_name}"
            if not self.hypergraph.has_node(event_node):
                self.hypergraph.add_node(event_node, type="hyperedge", chunk_ids=set())
            self.hypergraph.nodes[event_node]["chunk_ids"].add(chunk_id)
            
            # Kết nối các entities vào Hyperedge này
            for ent in entities:
                ent = ent.strip().lower()
                if not self.hypergraph.has_node(ent):
                    self.hypergraph.add_node(ent, type="entity")
                self.hypergraph.add_edge(ent, event_node)

    def add_timeline_events(self, events: List[Dict[str, Any]], chunk_id: int):
        for ev in events:
            ev["chunk_id"] = chunk_id
            self.timeline_events.append(ev)
            
    def save(self, path_prefix: pathlib.Path):
        try:
            with open(path_prefix.with_name("hypergraph.pkl"), "wb") as f:
                pickle.dump(self.hypergraph, f)
            with open(path_prefix.with_name("timeline.json"), "w", encoding="utf-8") as f:
                json.dump({"events": self.timeline_events}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi khi lưu HyperExtract data: {e}")

    def load(self, path_prefix: pathlib.Path) -> bool:
        hg_path = path_prefix.with_name("hypergraph.pkl")
        tl_path = path_prefix.with_name("timeline.json")
        
        if not hg_path.exists() or not tl_path.exists():
            return False
            
        try:
            with open(hg_path, "rb") as f:
                self.hypergraph = pickle.load(f)
            with open(tl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.timeline_events = data.get("events", [])
            return True
        except Exception as e:
            logger.error(f"Lỗi khi load HyperExtract data: {e}")
            return False

def extract_deep_features_batch(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sử dụng LLM trích xuất Timeline và Hyperedges.
    Trả về mảng kết quả tương ứng với mỗi chunk.
    """
    from chatbot.services.llm_service import generate_complete
    
    results = []
    batch_size = 2 # Batch nhỏ lại vì Local LLM thường giới hạn context ngắn hơn
    
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i+batch_size]
        
        prompt = "Bạn là AI phân tích Pháp lý Chuyên sâu (Hyper-Extractor).\n"
        prompt += "Dưới đây là một số đoạn văn bản pháp lý/hợp đồng. Cho MỖI đoạn, hãy trích xuất:\n"
        prompt += "1. Các sự kiện theo mốc thời gian (timeline). Mốc thời gian có thể là ngày tháng cụ thể hoặc mốc tương đối (ví dụ: 'khi ký hợp đồng').\n"
        prompt += "2. Các sự kiện đa chiều (hyperedges) liên quan từ 2 thực thể trở lên cùng một lúc.\n\n"
        
        for idx, chunk in enumerate(batch_chunks):
            prompt += f"--- ĐOẠN {idx} ---\n{chunk['text'][:1200]}\n\n"
            
        prompt += """
ĐẦU RA PHẢI LÀ MỘT JSON ARRAY chứa các đối tượng kết quả tương ứng với số lượng đoạn văn bản.
Ví dụ nếu có 2 đoạn, mảng phải chứa đúng 2 objects:
[
  {
    "timeline": [
      {"date": "15/01/2024", "event": "Ký kết hợp đồng", "entities": ["Công ty A", "Công ty B"]}
    ],
    "hyperedges": [
      {"event": "Hợp tác đầu tư", "entities": ["Công ty A", "Công ty B", "Dự án X"]}
    ]
  },
  {
    "timeline": [],
    "hyperedges": []
  }
]
CHỈ TRẢ VỀ JSON HỢP LỆ. KHÔNG THÊM VĂN BẢN NÀO KHÁC.
"""
        try:
            res_text = generate_complete(prompt)
            text = res_text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.endswith("```"): text = text[:-3]
                
            batch_result = json.loads(text.strip())
            
            while len(batch_result) < len(batch_chunks):
                batch_result.append({"timeline": [], "hyperedges": []})
                
            results.extend(batch_result[:len(batch_chunks)])
            
        except Exception as e:
            logger.error(f"Lỗi trích xuất HyperExtract LLM: {e}")
            results.extend([{"timeline": [], "hyperedges": []} for _ in batch_chunks])
            if "429" in str(e) or "Quota" in str(e):
                logger.warning("Quota exceeded! Bỏ qua quá trình trích xuất HyperExtract còn lại.")
                remaining = len(chunks) - len(results)
                if remaining > 0:
                    results.extend([{"timeline": [], "hyperedges": []} for _ in range(remaining)])
                break
            
    return results
