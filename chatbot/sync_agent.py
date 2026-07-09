import sqlite3
import logging
import json
import os
from typing import List

from data_connectors.local_folder_connector import LocalFolderConnector

logger = logging.getLogger("SyncAgent")

from chatbot.config import DB_PATH

def extract_contract_info(content: str) -> dict:
    """Sử dụng Gemini để trích xuất JSON từ nội dung hợp đồng"""
    try:
        from chatbot.services.llm_service import generate_complete
        prompt = f"""
Bạn là một AI chuyên phân tích hợp đồng pháp lý. Hãy đọc nội dung hợp đồng sau và trích xuất các thông tin:
1. Tên hợp đồng (contract_name)
2. Tên đối tác (partner_name)
3. Ngày hết hạn của hợp đồng theo định dạng YYYY-MM-DD (expiration_date). Nếu không có ngày hết hạn cụ thể, hãy cố gắng suy luận từ ngày ký và thời hạn (ví dụ: có hiệu lực 1 năm). Nếu hoàn toàn không thể xác định, hãy để chuỗi rỗng "".

CHỈ TRẢ VỀ CHUỖI JSON ĐÚNG ĐỊNH DẠNG. KHÔNG CÓ BẤT KỲ ĐỊNH DẠNG MARKDOWN (```json) HAY VĂN BẢN NÀO KHÁC BÊN NGOÀI.
Ví dụ đầu ra mong muốn:
{{
  "contract_name": "Hợp đồng dịch vụ phần mềm",
  "partner_name": "Công ty TNHH ABC",
  "expiration_date": "2024-12-31"
}}

Nội dung hợp đồng:
{content[:15000]}  # Giới hạn 15000 ký tự để tránh vượt token
"""
        res_text = generate_complete(prompt)
        text = res_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Lỗi AI Extractor: {e}")
        return None

def run_sync_job():
    """Hàm chạy định kỳ để đồng bộ dữ liệu từ các Connectors"""
    logger.info("Bắt đầu chạy Sync Agent...")
    
    # Khởi tạo các Connectors (Trong thực tế có thể đọc cấu hình bật/tắt từ DB)
    connectors = [
        LocalFolderConnector(folder_path="internal_storage")
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_synced = 0
    
    try:
        for connector in connectors:
            if connector.connect():
                unprocessed = connector.fetch_unprocessed_contracts()
                for doc in unprocessed:
                    logger.info(f"Đang xử lý tài liệu mới: {doc['filename']}")
                    info = extract_contract_info(doc['content_text'])
                    
                    if info:
                        contract_name = info.get("contract_name", "Không xác định")
                        partner_name = info.get("partner_name", "Không xác định")
                        expiration_date = info.get("expiration_date", "")
                        
                        try:
                            cursor.execute('''
                                INSERT INTO company_contracts 
                                (source_id, filename, contract_name, partner_name, expiration_date) 
                                VALUES (?, ?, ?, ?, ?)
                            ''', (doc['source_id'], doc['filename'], contract_name, partner_name, expiration_date))
                            conn.commit()
                            
                            # Đánh dấu đã xử lý
                            connector.mark_as_processed(doc['source_id'])
                            total_synced += 1
                            logger.info(f"Đã lưu hợp đồng {contract_name} vào DB thành công.")
                        except sqlite3.IntegrityError:
                            logger.warning(f"Tài liệu {doc['filename']} đã tồn tại trong DB.")
                        except Exception as e:
                            logger.error(f"Lỗi lưu DB cho {doc['filename']}: {e}")
                    else:
                        logger.warning(f"Không thể trích xuất JSON từ {doc['filename']}")
    finally:
        conn.close()

    logger.info(f"Sync Agent hoàn thành. Đồng bộ được {total_synced} tài liệu.")
