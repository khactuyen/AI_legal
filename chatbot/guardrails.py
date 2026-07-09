"""
Bộ lá chắn bảo mật (Guardrails) cho hệ thống AI Legal Assistant.
Chạy hoàn toàn cục bộ (offline), không gọi API bên ngoài.

Bao gồm:
1. PromptGuardrail  - Chặn Jailbreak / Prompt Injection / Chủ đề cấm
2. GroundingGuardrail - Đối chiếu trích dẫn luật trong câu trả lời với context
3. StreamLoopGuardrail - Phát hiện vòng lặp vô hạn trong luồng stream
"""

import re
import logging
from typing import List, Dict, Tuple, Set, Optional
from collections import deque

logger = logging.getLogger("Guardrails")


# ===========================================================================
# 1. PROMPT GUARDRAIL – Bảo vệ đầu vào
# ===========================================================================

class PromptGuardrail:
    """
    Quét câu hỏi người dùng trước khi gửi tới LLM.
    Phát hiện Jailbreak, Prompt Injection và chủ đề cấm.
    """

    # --- Các pattern tấn công Jailbreak / Prompt Injection ---
    INJECTION_PATTERNS: List[str] = [
        # Tiếng Anh
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?above",
        r"disregard\s+(all\s+)?prior",
        r"forget\s+(everything|all|your)\s+(instructions|rules|guidelines)",
        r"you\s+are\s+now\s+(DAN|a\s+new\s+AI|unrestricted)",
        r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
        r"system\s*prompt",
        r"reveal\s+(your|the)\s+(system|initial)\s+(prompt|instructions)",
        r"what\s+(are|is)\s+your\s+(instructions|system\s+prompt|rules)",
        r"print\s+(your|the)\s+system\s+(prompt|message)",
        r"jailbreak",
        r"DAN\s+mode",
        r"do\s+anything\s+now",
        r"bypass\s+(the\s+)?(filter|restriction|safety|guardrail)",

        # Tiếng Việt
        r"lờ\s+đi\s+hướng\s+dẫn",
        r"bỏ\s+qua\s+(tất\s+cả\s+)?hướng\s+dẫn",
        r"hãy\s+quên\s+(hết\s+)?(các\s+)?quy\s+tắc",
        r"bỏ\s+qua\s+(tất\s+cả\s+)?quy\s+tắc",
        r"hiện\s+ra\s+system\s+prompt",
        r"cho\s+tôi\s+xem\s+prompt\s+hệ\s+thống",
        r"giả\s+vờ\s+(là|bạn\s+là)\s+một\s+AI\s+không\s+giới\s+hạn",
        r"bạn\s+là\s+DAN",
        r"vượt\s+qua\s+bộ\s+lọc",
    ]

    # --- Các chủ đề nằm ngoài phạm vi (Luật Hình sự, Dân sự cá nhân, v.v.) ---
    FORBIDDEN_TOPIC_PATTERNS: List[str] = [
        # Hình sự
        r"(tội\s+)?(giết\s+người|cướp\s+(tài\s+sản|giật)|hiếp\s+dâm|bắt\s+cóc)",
        r"ma\s+túy|chất\s+cấm|buôn\s+bán\s+người",
        r"(cách|làm\s+sao)\s+(để\s+)?(lách|trốn|tránh)\s+(luật|thuế|pháp\s+luật)",

        # Chính trị nhạy cảm
        r"lật\s+đổ\s+chính\s+quyền",
        r"chống\s+phá\s+nhà\s+nước",
    ]

    REFUSAL_MESSAGES = {
        "injection": "Xin lỗi, câu hỏi của bạn chứa nội dung không hợp lệ. Vui lòng đặt câu hỏi liên quan đến pháp lý doanh nghiệp.",
        "forbidden": "Xin lỗi, chủ đề này nằm ngoài phạm vi hỗ trợ của tôi. Tôi chỉ tư vấn về Luật Doanh nghiệp, Luật Thương mại, Luật Lao động, Luật Đầu tư và Kế toán-Thuế.",
    }

    @classmethod
    def check(cls, user_input: str) -> Tuple[bool, str]:
        """
        Kiểm tra câu hỏi người dùng.
        Returns:
            (is_safe, reason): True nếu an toàn, False kèm lý do từ chối.
        """
        if not user_input or not user_input.strip():
            return True, ""

        text_lower = user_input.lower().strip()

        # Kiểm tra Prompt Injection / Jailbreak
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"[PromptGuardrail] BLOCKED Injection: matched pattern '{pattern}' in: {user_input[:80]}...")
                return False, cls.REFUSAL_MESSAGES["injection"]

        # Kiểm tra chủ đề cấm
        for pattern in cls.FORBIDDEN_TOPIC_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"[PromptGuardrail] BLOCKED Forbidden Topic: matched pattern '{pattern}' in: {user_input[:80]}...")
                return False, cls.REFUSAL_MESSAGES["forbidden"]

        return True, ""


# ===========================================================================
# 2. GROUNDING GUARDRAIL – Chống ảo giác pháp lý
# ===========================================================================

class GroundingGuardrail:
    """
    Đối chiếu các trích dẫn pháp lý trong câu trả lời của LLM
    với danh sách context chunks đã được truy vấn.
    Nếu AI trích dẫn điều luật không có trong context → gắn cảnh báo.
    """

    # Regex bắt các trích dẫn pháp lý trong câu trả lời
    CITATION_PATTERNS = [
        # "Điều 15", "Điều 123"
        r"Điều\s+(\d+)",
        # "Khoản 1 Điều 15"
        r"Khoản\s+(\d+)\s+Điều\s+(\d+)",
        # Số hiệu văn bản: "59/2020/QH14", "68/2014/QH13", "198-2025-qh15"
        r"(\d{1,3}[/-]\d{4}[/-][qQ][hH]\d{1,2})",
    ]

    @classmethod
    def extract_citations_from_response(cls, response_text: str) -> Set[str]:
        """Trích xuất tất cả các trích dẫn pháp lý duy nhất từ câu trả lời."""
        citations = set()
        for pattern in cls.CITATION_PATTERNS:
            matches = re.findall(pattern, response_text)
            for match in matches:
                if isinstance(match, tuple):
                    # Khoản X Điều Y → lưu "Điều Y"
                    citations.add(f"Điều {match[-1]}")
                else:
                    if match.isdigit():
                        citations.add(f"Điều {match}")
                    else:
                        # Chuẩn hóa số hiệu văn bản (vd: 198-2025-qh15 -> 198/2025/QH15)
                        normalized = match.replace("-", "/").upper()
                        citations.add(normalized)
        return citations

    @classmethod
    def extract_citations_from_context(cls, relevant_docs: List[Tuple[str, Dict, float]]) -> Set[str]:
        """Trích xuất tất cả các Điều luật có trong context chunks."""
        context_citations = set()
        for text, meta, score in relevant_docs:
            # Từ text của chunk
            dieu_matches = re.findall(r"Điều\s+(\d+)", text)
            for m in dieu_matches:
                context_citations.add(f"Điều {m}")

            # Từ metadata article field (ví dụ: "Điều 15:")
            article = meta.get("article", "")
            if article:
                article_nums = re.findall(r"\d+", article)
                for num in article_nums:
                    context_citations.add(f"Điều {num}")

            # Từ source_file (ví dụ: "59/2020/QH14" hoặc "59-2020-QH14")
            source = meta.get("source_file", "")
            if source:
                # Chuẩn hóa dấu gạch ngang thành gạch chéo để khớp với regex của số hiệu văn bản
                normalized_source = source.replace("-", "/")
                doc_id_matches = re.findall(r"(\d{1,3}/\d{4}/[qQ][hH]\d{1,2})", normalized_source)
                for doc_id in doc_id_matches:
                    context_citations.add(doc_id.upper())

        return context_citations

    @classmethod
    def verify(cls, response_text: str, relevant_docs: List[Tuple[str, Dict, float]]) -> Tuple[str, List[str]]:
        """
        Xác minh các trích dẫn trong câu trả lời có khớp với context không.
        
        Returns:
            (verified_response, unverified_citations):
            - verified_response: Câu trả lời đã gắn cảnh báo cho các trích dẫn không xác minh được.
            - unverified_citations: Danh sách các trích dẫn không tìm thấy trong context.
        """
        if not relevant_docs:
            return response_text, []

        response_citations = cls.extract_citations_from_response(response_text)
        context_citations = cls.extract_citations_from_context(relevant_docs)

        if not response_citations:
            return response_text, []

        unverified = []
        verified_response = response_text

        for citation in response_citations:
            if citation not in context_citations:
                unverified.append(citation)
                # Gắn cảnh báo vào dòng chứa trích dẫn không xác minh được
                verified_response = verified_response.replace(
                    citation,
                    f"{citation} [⚠️ CHƯA XÁC MINH]",
                    1  # Chỉ thay thế lần xuất hiện đầu tiên
                )

        if unverified:
            logger.warning(f"[GroundingGuardrail] {len(unverified)} trích dẫn chưa xác minh: {unverified}")

        return verified_response, unverified


# ===========================================================================
# 3. STREAM LOOP GUARDRAIL – Phát hiện vòng lặp stream
# ===========================================================================

class StreamLoopGuardrail:
    """
    Giám sát đầu ra stream từ LLM. Nếu phát hiện LLM bị lặp lại
    cùng một cụm từ liên tục, tự động báo cắt luồng.
    """

    def __init__(self, window_size: int = 15, threshold: int = 4):
        """
        Args:
            window_size: Kích thước cửa sổ trượt (số chunks gần nhất cần theo dõi).
            threshold: Số lần lặp lại trong cửa sổ để coi là vòng lặp.
        """
        self.window: deque = deque(maxlen=window_size)
        self.threshold = threshold
        self._total_chars = 0
        self._last_100_chars = ""

    def check(self, text_chunk: str) -> bool:
        """
        Kiểm tra xem chunk mới có tạo thành vòng lặp không.
        
        Returns:
            True nếu phát hiện vòng lặp (cần ngắt stream).
            False nếu bình thường.
        """
        if not text_chunk or not text_chunk.strip():
            return False

        normalized = text_chunk.strip().lower()

        # --- Phương pháp 1: Đếm tần suất chunk trong cửa sổ trượt ---
        self.window.append(normalized)
        count = sum(1 for c in self.window if c == normalized)
        if count >= self.threshold:
            logger.warning(f"[StreamLoopGuardrail] LOOP DETECTED (chunk repeat): '{normalized[:50]}...' appeared {count}/{self.threshold} times")
            return True

        # --- Phương pháp 2: Kiểm tra lặp ký tự liên tục ---
        self._total_chars += len(text_chunk)
        self._last_100_chars += text_chunk
        if len(self._last_100_chars) > 200:
            self._last_100_chars = self._last_100_chars[-200:]

        # Kiểm tra xem 200 ký tự cuối có chứa chuỗi lặp lại hay không
        if len(self._last_100_chars) >= 100:
            # Tìm pattern lặp: nếu một chuỗi 10-50 ký tự xuất hiện >= 3 lần liên tiếp
            for pattern_len in range(10, min(51, len(self._last_100_chars) // 3 + 1)):
                pattern = self._last_100_chars[-pattern_len:]
                check_str = self._last_100_chars[-(pattern_len * 3):]
                if len(check_str) >= pattern_len * 3:
                    if check_str == pattern * 3:
                        logger.warning(f"[StreamLoopGuardrail] LOOP DETECTED (char repeat): pattern '{pattern[:30]}...'")
                        return True

        return False

    def reset(self):
        """Reset trạng thái guardrail cho phiên stream mới."""
        self.window.clear()
        self._total_chars = 0
        self._last_100_chars = ""
