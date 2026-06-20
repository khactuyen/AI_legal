import os
import pathlib
import hashlib
import fitz  # PyMuPDF
from docx import Document
from typing import List, Dict, Any
from .base_connector import BaseDataConnector
import logging

logger = logging.getLogger("LocalFolderConnector")

class LocalFolderConnector(BaseDataConnector):
    """
    Connector đọc file hợp đồng từ một thư mục nội bộ (Mô phỏng MCP File System Server).
    Hỗ trợ .txt, .pdf, .docx
    """
    def __init__(self, folder_path: str):
        self.folder_path = pathlib.Path(folder_path)
        self.processed_log_path = self.folder_path / ".processed_files.log"
        self.processed_files = set()
        
    def connect(self) -> bool:
        if not self.folder_path.exists():
            self.folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Đã tạo thư mục nội bộ tại: {self.folder_path}")
            
        if self.processed_log_path.exists():
            with open(self.processed_log_path, "r", encoding="utf-8") as f:
                self.processed_files = set(line.strip() for line in f if line.strip())
        return True

    def _read_file_content(self, file_path: pathlib.Path) -> str:
        ext = file_path.suffix.lower()
        content = ""
        try:
            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            elif ext == ".pdf":
                doc = fitz.open(str(file_path))
                for page in doc:
                    content += page.get_text("text") + "\n"
                doc.close()
            elif ext == ".docx":
                doc = Document(str(file_path))
                content = "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            logger.error(f"Lỗi đọc file {file_path.name}: {e}")
        return content

    def fetch_unprocessed_contracts(self) -> List[Dict[str, Any]]:
        results = []
        for file_path in self.folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in [".txt", ".pdf", ".docx"]:
                # Dùng MD5 của tên file làm source_id tĩnh
                source_id = hashlib.md5(file_path.name.encode()).hexdigest()
                if source_id not in self.processed_files:
                    content = self._read_file_content(file_path)
                    if content.strip():
                        results.append({
                            "source_id": source_id,
                            "filename": file_path.name,
                            "content_text": content
                        })
        return results

    def mark_as_processed(self, source_id: str) -> bool:
        self.processed_files.add(source_id)
        try:
            with open(self.processed_log_path, "a", encoding="utf-8") as f:
                f.write(f"{source_id}\n")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đánh dấu processed {source_id}: {e}")
            return False
