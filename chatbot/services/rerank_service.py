import re
import json
import logging
from typing import List, Tuple, Dict
from chatbot.services.llm_service import generate_complete

logger = logging.getLogger("chatbot.services.rerank_service")

def rerank_with_llm(query: str, candidates: List[Tuple[str, Dict, float]], top_k: int = 5) -> List[Tuple[str, Dict, float]]:
    if not candidates:
        return []
    
    formatted_candidates = []
    for idx, (text, meta, score) in enumerate(candidates):
        source = meta.get("source_file", "Unknown")
        article = meta.get("article", "Unknown")
        formatted_candidates.append({
            "index": idx,
            "source": f"{source} - {article}",
            "content": text[:800]
        })
        
    prompt = f"""Bạn là Trợ lý Giám thị Pháp lý. Nhiệm vụ của bạn là đọc Câu hỏi của người dùng và danh sách các đoạn văn bản pháp luật dưới đây, sau đó đánh giá độ liên quan và sắp xếp lại thứ tự từ liên quan nhất đến ít liên quan nhất.

CÂU HỎI NGƯỜI DÙNG: "{query}"

DANH SÁCH CÁC ĐOẠN VĂN BẢN PHÁP LUẬT:
{json.dumps(formatted_candidates, ensure_ascii=False, indent=2)}

YÊU CẦU:
1. Đánh giá độ liên quan của từng đoạn văn bản với câu hỏi. Lọc bỏ các đoạn hoàn toàn không liên quan (không giúp ích cho câu hỏi).
2. Sắp xếp lại thứ tự các đoạn văn bản còn lại theo độ liên quan giảm dần (đoạn trực tiếp trả lời câu hỏi nằm lên đầu).
3. Chỉ trả về một mảng JSON chứa các index của các đoạn văn bản được chọn theo đúng thứ tự xếp hạng mới. Ví dụ: [2, 0, 4]
4. Tuyệt đối không trả về bất kỳ văn bản giải thích nào khác ngoài định dạng JSON này.
"""
    from chatbot.services.llm_service import generate_complete
    try:
        res_text = generate_complete(prompt)
        text_resp = res_text.replace("```json", "").replace("```", "").strip()
        
        match = re.search(r'\[\s*\d+\s*(?:,\s*\d+\s*)*\]', text_resp)
        if match:
            reranked_indices = json.loads(match.group(0))
        else:
            reranked_indices = json.loads(text_resp)
            
        if isinstance(reranked_indices, list):
            reranked_results = []
            seen_indices = set()
            for idx in reranked_indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen_indices:
                    reranked_results.append(candidates[idx])
                    seen_indices.add(idx)
            
            for idx, cand in enumerate(candidates):
                if idx not in seen_indices and len(reranked_results) < top_k:
                    reranked_results.append(cand)
                    seen_indices.add(idx)
                    
            logger.info(f"LLM Reranker đã xếp hạng lại: {reranked_indices} -> Đã chọn {len(reranked_results)} kết quả.")
            return reranked_results[:top_k]
    except Exception as e:
        logger.error(f"Lỗi khi re-rank bằng LLM: {e}")
        
    return candidates[:top_k]
