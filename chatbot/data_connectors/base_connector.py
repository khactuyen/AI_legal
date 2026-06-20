from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseDataConnector(ABC):
    """
    Abstract Base Class cho mọi Data Connector (SQL, NoSQL, Local Storage, Cloud Storage, ERP/CRM).
    Kiến trúc thiết kế mô phỏng Model Context Protocol (MCP) dành riêng cho dữ liệu nội bộ.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Thiết lập kết nối tới nguồn dữ liệu"""
        pass
        
    @abstractmethod
    def fetch_unprocessed_contracts(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các hợp đồng mới hoặc chưa được xử lý.
        Trả về List các Dict, mỗi Dict tối thiểu chứa:
        - source_id: Mã định danh duy nhất của tài liệu tại nguồn
        - filename: Tên tài liệu
        - content_text: Nội dung text thô của tài liệu
        - metadata: Các thông tin bổ sung (tùy chọn)
        """
        pass
        
    @abstractmethod
    def mark_as_processed(self, source_id: str) -> bool:
        """Đánh dấu một tài liệu đã được đồng bộ và trích xuất thành công"""
        pass
