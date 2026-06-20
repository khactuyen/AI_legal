import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VBPL_SITEMAP = "https://vbpl.vn/sitemap.xml"
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'law_registry.json')

class VbplCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.load_registry()

    def load_registry(self):
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                self.registry = json.load(f)
        else:
            self.registry = {}

    def save_registry(self):
        with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def fetch_sitemap(self):
        """Lấy danh sách các URL mới nhất từ Sitemap (Incremental Crawling)"""
        logger.info(f"Đang đọc Sitemap từ: {VBPL_SITEMAP}")
        try:
            response = requests.get(VBPL_SITEMAP, headers=self.headers, timeout=10)
            if response.status_code == 200:
                # Xử lý parse XML ở đây
                # Tạm thời giả lập trả về 1 link mới
                logger.info("Tìm thấy văn bản mới!")
                return ["https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=12345"]
            return []
        except Exception as e:
            logger.error(f"Lỗi cào sitemap: {e}")
            return []

    def extract_metadata(self, url):
        """Cào trạng thái hiệu lực trực tiếp trên trang VBPL"""
        logger.info(f"Đang phân tích Metadata từ URL: {url}")
        time.sleep(2)  # Tuân thủ đạo đức cào dữ liệu, nghỉ 2s
        try:
            # response = requests.get(url, headers=self.headers)
            # soup = BeautifulSoup(response.content, 'html.parser')
            # status_element = soup.find('div', class_='status-class') 
            
            # Giả lập trả về
            return {
                "status": "ACTIVE",
                "effective_date": "2026-01-01"
            }
        except Exception as e:
            logger.error(f"Lỗi cào metadata: {e}")
            return None

    def analyze_expiration_with_ai(self, text_content):
        """Sử dụng Gemini để phân tích Điều khoản thi hành và tìm luật bị thay thế"""
        logger.info("Chạy AI phân tích Điều khoản thi hành...")
        try:
            # Gửi 2 trang cuối của text_content cho AI
            prompt = f"""
            Hãy đọc phần Điều khoản thi hành của văn bản pháp luật sau.
            Nhiệm vụ của bạn là tìm ra các số hiệu văn bản bị bãi bỏ hoặc thay thế bởi văn bản này.
            Trả về CHỈ một chuỗi JSON chuẩn: {{"expired_laws": ["Số hiệu 1", "Số hiệu 2"]}}
            Nếu không có, trả về {{"expired_laws": []}}
            
            Đoạn văn bản:
            {text_content[-2000:]}
            """
            # model = genai.GenerativeModel("gemini-2.5-flash")
            # response = model.generate_content(prompt)
            # return json.loads(response.text)
            
            # Giả lập AI tìm thấy 1 luật bị bãi bỏ
            return {"expired_laws": ["Luat_Doanh_Nghiep_2014"]}
        except Exception as e:
            logger.error(f"Lỗi AI phân tích: {e}")
            return {"expired_laws": []}

    def run_daily_crawl(self):
        urls = self.fetch_sitemap()
        for url in urls:
            law_id = url.split("ItemID=")[-1]  # Tạm tạo ID từ URL
            if law_id not in self.registry:
                metadata = self.extract_metadata(url)
                if metadata:
                    self.registry[law_id] = {
                        "status": metadata["status"],
                        "superseded_by": None,
                        "url": url,
                        "effective_date": metadata["effective_date"]
                    }
                    
                    # Giả lập: Tải file text và dùng AI phân tích
                    fake_text = "Điều 100. Hiệu lực thi hành. Luật này bãi bỏ Luật Doanh nghiệp 2014."
                    ai_result = self.analyze_expiration_with_ai(fake_text)
                    
                    for expired_law in ai_result.get("expired_laws", []):
                        if expired_law in self.registry:
                            self.registry[expired_law]["status"] = "EXPIRED"
                            self.registry[expired_law]["superseded_by"] = law_id
                            logger.info(f"Đã gán cờ EXPIRED cho: {expired_law}")
                
        self.save_registry()
        logger.info("Hoàn thành cào dữ liệu ngày hôm nay!")

if __name__ == "__main__":
    crawler = VbplCrawler()
    crawler.run_daily_crawl()
