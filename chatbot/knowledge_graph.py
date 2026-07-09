import networkx as nx
import pickle
import pathlib
import logging
import json
import os
import google.generativeai as genai
from typing import List, Dict, Any, Set

logger = logging.getLogger("KnowledgeGraph")

class LegalKnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.chunk_to_entities = {} # chunk_id -> list of entities

    def add_triplets(self, chunk_id: int, triplets: List[Dict[str, str]]):
        """Thêm các bộ ba (head, relation, tail) vào đồ thị và gắn nhãn nguồn chunk_id"""
        if chunk_id not in self.chunk_to_entities:
            self.chunk_to_entities[chunk_id] = set()
            
        for t in triplets:
            if not isinstance(t, dict): continue
            head = t.get("head", "").strip().lower()
            rel = t.get("relation", "").strip().upper()
            tail = t.get("tail", "").strip().lower()
            
            if not head or not tail or not rel:
                continue
                
            self.chunk_to_entities[chunk_id].add(head)
            self.chunk_to_entities[chunk_id].add(tail)
            
            # Thêm hoặc cập nhật edge
            if self.graph.has_edge(head, tail):
                # Lưu mảng chunk_ids để biết edge này thuộc những văn bản nào
                self.graph[head][tail]['relations'].add(rel)
                self.graph[head][tail]['chunk_ids'].add(chunk_id)
            else:
                self.graph.add_edge(head, tail, relations={rel}, chunk_ids={chunk_id})

    def find_related_chunks(self, seed_entities: List[str], depth: int = 1) -> Set[int]:
        """Từ một tập entity mồi (có trong câu hỏi/kết quả vector), tìm các chunk liên đới qua đồ thị"""
        if not self.graph.nodes:
            return set()
            
        seed_entities = [e.lower() for e in seed_entities]
        found_chunks = set()
        visited_nodes = set()
        
        # Lọc những seed entities có trong graph
        active_nodes = [n for n in seed_entities if n in self.graph.nodes]
        
        for _ in range(depth):
            next_nodes = []
            for node in active_nodes:
                if node in visited_nodes:
                    continue
                visited_nodes.add(node)
                
                # Khám phá các node lân cận (cả incoming và outgoing edges)
                neighbors = list(self.graph.successors(node)) + list(self.graph.predecessors(node))
                next_nodes.extend(neighbors)
                
                # Thu thập các chunk_ids từ các edges liên quan đến node này
                for succ in self.graph.successors(node):
                    found_chunks.update(self.graph[node][succ]['chunk_ids'])
                for pred in self.graph.predecessors(node):
                    found_chunks.update(self.graph[pred][node]['chunk_ids'])
            
            active_nodes = list(set(next_nodes))
            
        return found_chunks

    def save(self, path: pathlib.Path):
        try:
            with open(path, "wb") as f:
                pickle.dump({
                    "graph": self.graph,
                    "chunk_to_entities": self.chunk_to_entities
                }, f)
        except Exception as e:
            logger.error(f"Lỗi khi lưu Knowledge Graph: {e}")

    def load(self, path: pathlib.Path) -> bool:
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
                self.graph = data.get("graph", nx.DiGraph())
                self.chunk_to_entities = data.get("chunk_to_entities", {})
            return True
        except Exception as e:
            logger.error(f"Lỗi khi nạp Knowledge Graph: {e}")
            return False

def extract_triplets_llm_batch(chunks: List[Dict[str, Any]]) -> List[List[Dict[str, str]]]:
    """
    Sử dụng LLM để trích xuất các Knowledge Triplets từ một mảng các văn bản pháp lý.
    Output: Một mảng các danh sách bộ 3, tương ứng với mỗi chunk.
    """
    from chatbot.services.llm_service import generate_complete
    
    # Hợp nhất các chunk vào 1 prompt (giới hạn 5 chunk mỗi lần gọi để tránh quá tải JSON)
    results = []
    
    batch_size = 5
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i+batch_size]
        
        prompt = "Bạn là hệ thống trích xuất Tri thức Pháp lý (Legal Knowledge Extractor).\n"
        prompt += "Dưới đây là một số đoạn văn bản luật. Hãy trích xuất các mối quan hệ thành bộ ba (head, relation, tail) cho MỖI đoạn.\n"
        prompt += "Các loại relation ưu tiên: VIỆN_DẪN, QUY_ĐỊNH_VỀ, PHẠT_VI_PHẠM, YÊU_CẦU, CẤM, LIÊN_QUAN.\n\n"
        
        for idx, chunk in enumerate(batch_chunks):
            prompt += f"--- ĐOẠN {idx} ---\n{chunk['text'][:1000]}\n\n"
            
        prompt += """
ĐẦU RA PHẢI LÀ ĐÚNG ĐỊNH DẠNG JSON ARRAY SAU, VÀ LÀ MỘT ARRAY CHỨA CÁC ARRAY CON:
[
  [
    {"head": "Tên thực thể 1", "relation": "QUY_ĐỊNH_VỀ", "tail": "Tên thực thể 2"}
  ],
  [
    {"head": "Công ty TNHH", "relation": "YÊU_CẦU", "tail": "Nộp thuế"}
  ]
]
Lưu ý: Array cha phải có số lượng phần tử ĐÚNG BẰNG số lượng ĐOẠN văn bản đầu vào. Nếu một đoạn không có quan hệ nào, trả về mảng rỗng [] ở vị trí đó.
CHỈ TRẢ VỀ JSON, KHÔNG THÊM BẤT KỲ VĂN BẢN NÀO KHÁC.
"""
        try:
            res_text = generate_complete(prompt)
            text = res_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
                
            batch_result = json.loads(text.strip())
            
            # Đảm bảo độ dài khớp
            while len(batch_result) < len(batch_chunks):
                batch_result.append([])
                
            results.extend(batch_result[:len(batch_chunks)])
            
        except Exception as e:
            logger.error(f"Lỗi trích xuất Triplets LLM: {e}")
            results.extend([[] for _ in batch_chunks])
            if "429" in str(e) or "Quota" in str(e):
                logger.warning("Quota exceeded! Bỏ qua quá trình trích xuất đồ thị còn lại.")
                remaining = len(chunks) - len(results)
                if remaining > 0:
                    results.extend([[] for _ in range(remaining)])
                break
            
    return results
