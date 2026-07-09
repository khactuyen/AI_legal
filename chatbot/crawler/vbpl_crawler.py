import os
import json
import time
import requests
import re
import pathlib
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VbplCrawler")

# Thêm các thư mục cần thiết vào sys.path để import đúng
crawler_dir = os.path.dirname(os.path.abspath(__file__))
chatbot_dir = os.path.dirname(crawler_dir)
parent_dir = os.path.dirname(chatbot_dir)

import sys
for d in [parent_dir, chatbot_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from chatbot.services.llm_service import generate_complete

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'law_registry.json')
VBPL_BASE = "https://vbpl.vn"

# Next.js Server Action ID để lấy toàn văn văn bản (cập nhật tháng 4/2026)
# Nếu site nâng cấp và action này thay đổi, cần sniff lại bằng DevTools
FULLTEXT_ACTION_ID = "0fb12b3561faa05adec51a82efb3e4f4f427f07b"


class VbplCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.registry = {}
        self.load_registry()
        # Cache sitemap để không tải lại nhiều lần trong một lần chạy
        self._sitemap_cache = {}

    # ─────────────────────────────────────────────────────────────
    # Registry
    # ─────────────────────────────────────────────────────────────

    def load_registry(self):
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                    self.registry = json.load(f)
                logger.info(f"Đã nạp registry từ {REGISTRY_PATH} ({len(self.registry)} entries).")
            except Exception as e:
                logger.error(f"Lỗi đọc registry: {e}")
                self.registry = {}
        else:
            self.registry = {}

    def save_registry(self):
        try:
            with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)
            logger.info("Đã lưu registry thành công.")
        except Exception as e:
            logger.error(f"Lỗi lưu registry: {e}")

    # ─────────────────────────────────────────────────────────────
    # Tìm kiếm ItemID qua Sitemap XML
    # ─────────────────────────────────────────────────────────────

    def _keyword_to_slug(self, keyword):
        """Chuyển số hiệu văn bản thành dạng slug để tìm trong sitemap.
        Ví dụ: '59/2020/QH14' → '59-2020-qh14'
        """
        norm = keyword.lower().replace('đ', 'd').replace('đ', 'd')
        normalized = re.sub(r'[^a-zA-Z0-9]', '-', norm)
        normalized = re.sub(r'-+', '-', normalized).strip('-')
        return normalized

    def _load_sitemap(self, sitemap_url):
        """Tải và cache danh sách URL từ một sitemap XML."""
        if sitemap_url in self._sitemap_cache:
            return self._sitemap_cache[sitemap_url]
        try:
            resp = requests.get(sitemap_url, headers=self.headers, timeout=20)
            if resp.status_code != 200:
                return None  # Sitemap không tồn tại
            root = ET.fromstring(resp.content)
            ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
            urls = [
                loc.text
                for url_node in root.findall(f'{ns}url')
                for loc in [url_node.find(f'{ns}loc')]
                if loc is not None
            ]
            self._sitemap_cache[sitemap_url] = urls
            logger.info(f"Đã cache sitemap ({len(urls)} URLs): {sitemap_url}")
            return urls
        except Exception as e:
            logger.error(f"Lỗi tải sitemap {sitemap_url}: {e}")
            return []

    def search_law_id(self, keyword):
        """Tìm kiếm ItemID của văn bản Trung ương trong các sitemap XML của VBPL.

        Cách hoạt động:
        - Chuyển số hiệu (vd: 59/2020/QH14) thành slug (59-2020-qh14)
        - Duyệt qua sitemap-trung-uong-1.xml đến 11.xml
        - Ưu tiên URL kết thúc bằng slug--ID (khớp chính xác phần số hiệu)
        - Fallback về URL có chứa slug bất kỳ
        """
        logger.info(f"Tìm kiếm ItemID cho: {keyword}")
        slug = self._keyword_to_slug(keyword)
        logger.debug(f"Slug tìm kiếm: '{slug}'")

        # Pattern: URL kết thúc bằng -so-{slug}--{id} hoặc -{slug}--{id}
        # Tức là slug nằm ngay trước --{id}, không phải nằm giữa chuỗi dài hơn
        exact_pattern = re.compile(rf'-{re.escape(slug)}--(\d+)$', re.IGNORECASE)

        exact_result = None
        fallback_result = None

        for i in range(1, 12):
            sitemap_url = f"{VBPL_BASE}/sitemap-trung-uong-{i}.xml"
            urls = self._load_sitemap(sitemap_url)
            if urls is None:
                logger.info(f"Sitemap {i} không tồn tại, dừng tìm kiếm.")
                break

            for url in urls:
                url_lower = url.lower()

                # Ưu tiên 1: slug khớp chính xác ngay trước --ID
                m = exact_pattern.search(url_lower)
                if m:
                    item_id = m.group(1)
                    logger.info(f"Tìm thấy (chính xác) ItemID={item_id} cho '{keyword}' tại {url}")
                    return item_id

                # Fallback: slug xuất hiện bất kỳ trong URL
                if slug in url_lower and fallback_result is None:
                    m2 = re.search(r'--(\d+)$', url)
                    if m2:
                        fallback_result = (m2.group(1), url)

            if exact_result:
                break

        if fallback_result:
            item_id, url = fallback_result
            logger.info(f"Tìm thấy (fallback) ItemID={item_id} cho '{keyword}' tại {url}")
            return item_id

        logger.warning(f"Không tìm thấy ItemID cho '{keyword}' trong sitemap.")
        return None

    # ─────────────────────────────────────────────────────────────
    # Lấy toàn văn + metadata qua Next.js Server Action
    # ─────────────────────────────────────────────────────────────

    def fetch_full_text_and_metadata(self, item_id):
        """Lấy toàn văn và metadata bằng Next.js Server Action POST request.

        Cách hoạt động:
        - POST tới /van-ban/chi-tiet/{item_id}
        - Header đặc biệt: next-action: <FULLTEXT_ACTION_ID>
        - Body: ["{item_id}"]
        - Response trả về: phần HTML toàn văn + JSON metadata ở cuối

        Trả về: (full_text: str, metadata: dict | None)
        """
        logger.info(f"Đang lấy toàn văn + metadata cho ItemID: {item_id}")
        url = f"{VBPL_BASE}/van-ban/chi-tiet/{item_id}"
        action_headers = {
            **self.headers,
            'accept': 'text/x-component',
            'content-type': 'text/plain;charset=UTF-8',
            'next-action': FULLTEXT_ACTION_ID,
            'referer': url,
        }

        try:
            response = requests.post(
                url,
                data=f'["{item_id}"]',
                headers=action_headers,
                timeout=30
            )
            if response.status_code != 200:
                logger.error(f"Server Action trả về lỗi: HTTP {response.status_code}")
                return "", None

            # Decode bytes UTF-8 trực tiếp để giữ nguyên tiếng Việt
            raw_text = response.content.decode("utf-8", errors="ignore")

            full_text = self._extract_full_text(raw_text)
            metadata = self._extract_metadata(raw_text, item_id)

            return full_text, metadata

        except Exception as e:
            logger.error(f"Lỗi khi gọi Server Action cho ItemID {item_id}: {e}")
            return "", None

    def _extract_full_text(self, raw_text):
        """Trích xuất nội dung toàn văn từ HTML trong response Server Action.
        Tìm <div class="WordSection1"> hoặc fallback về <body>.
        """
        # Tìm phần HTML bắt đầu của response
        start_idx = raw_text.find("<html")
        if start_idx == -1:
            start_idx = raw_text.find("<div")
        if start_idx == -1:
            return ""

        html_part = raw_text[start_idx:]
        end_idx = html_part.rfind("</html>")
        if end_idx != -1:
            html_part = html_part[:end_idx + 7]

        soup = BeautifulSoup(html_part, 'html.parser')

        # Ưu tiên: container Word document chứa toàn văn
        section = soup.find("div", class_="WordSection1")
        if section:
            return section.get_text().strip()

        # Fallback: lấy toàn bộ body
        body = soup.find("body")
        if body:
            return body.get_text().strip()

        return soup.get_text().strip()

    def _extract_metadata(self, raw_text, item_id):
        """Trích xuất metadata từ JSON object cuối response Server Action.

        JSON có dạng: {"id":"142847","docNum":"59/2020/QH14","title":"...","effStatus":{...},...}
        """
        pattern = f'{{"id":"{item_id}"'
        pos = raw_text.find(pattern)
        if pos == -1:
            logger.warning(f"Không tìm thấy JSON metadata cho ItemID {item_id}")
            return None

        # Duyệt từng ký tự để tìm điểm kết thúc JSON object (brace tracking)
        brace_count = 0
        in_string = False
        escape = False

        for i in range(pos, len(raw_text)):
            char = raw_text[i]
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = raw_text[pos:i + 1]
                        try:
                            return json.loads(json_str)
                        except Exception as e:
                            logger.error(f"Lỗi parse JSON metadata: {e}")
                            return None
        return None

    # ─────────────────────────────────────────────────────────────
    # Phân tích AI
    # ─────────────────────────────────────────────────────────────

    def analyze_expiration_with_ai(self, text_content):
        """Dùng LLM phân tích Điều khoản thi hành để tìm luật bị bãi bỏ/thay thế."""
        logger.info("Chạy AI phân tích điều khoản bãi bỏ/thay thế...")
        if not text_content:
            return {"expired_laws": []}

        # Lấy 3000 ký tự cuối – thường chứa điều khoản thi hành
        context = text_content[-3000:]

        prompt = f"""Hãy đọc phần Điều khoản thi hành của văn bản pháp luật dưới đây.
Nhiệm vụ của bạn là trích xuất ra danh sách các số hiệu văn bản pháp luật bị bãi bỏ hoặc bị thay thế hoàn toàn bởi văn bản này.
Yêu cầu đầu ra: Chỉ trả về một chuỗi JSON duy nhất định dạng: {{"expired_laws": ["Số hiệu 1", "Số hiệu 2"]}}
Lưu ý: Chỉ trả về JSON, không thêm bất kỳ văn bản nào khác. Nếu không có văn bản bị bãi bỏ hoặc thay thế, trả về {{"expired_laws": []}}

Đoạn văn bản:
{context}

JSON:"""
        try:
            response_text = generate_complete(prompt)
            cleaned = response_text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{\s*"expired_laws"\s*:\s*\[.*?\]\s*\}', cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Lỗi AI phân tích bãi bỏ: {e}")
            return {"expired_laws": []}

    # ─────────────────────────────────────────────────────────────
    # Luồng chính
    # ─────────────────────────────────────────────────────────────

    def crawl_existing_laws(self):
        """Duyệt qua các file luật trong data_laws và đồng bộ registry từ VBPL."""
        logger.info("Bắt đầu đồng bộ hóa kho dữ liệu luật từ VBPL...")

        root_data_laws = pathlib.Path(os.path.dirname(__file__)).parent.parent / "data_laws"
        chatbot_data_laws = pathlib.Path(os.path.dirname(__file__)).parent / "data_laws"

        # Sao chép file từ thư mục gốc nếu chatbot/data_laws còn trống
        if root_data_laws.exists():
            chatbot_data_laws.mkdir(exist_ok=True)
            if not list(chatbot_data_laws.glob("*")) and list(root_data_laws.glob("*")):
                import shutil
                logger.info("Sao chép file luật từ thư mục gốc sang chatbot/data_laws...")
                for f_path in root_data_laws.glob("*"):
                    if f_path.is_file():
                        try:
                            shutil.copy(f_path, chatbot_data_laws / f_path.name)
                            logger.info(f"Đã sao chép: {f_path.name}")
                        except Exception as e:
                            logger.error(f"Lỗi sao chép {f_path.name}: {e}")

        data_dir = (
            chatbot_data_laws
            if chatbot_data_laws.exists() and list(chatbot_data_laws.glob("*"))
            else root_data_laws
        )
        if not data_dir.exists():
            logger.error("Không tìm thấy thư mục data_laws.")
            return

        logger.info(f"Thư mục dữ liệu: {data_dir.absolute()}")

        files = []
        for ext in ["*.docx", "*.pdf", "*.doc", "*.txt"]:
            files.extend(list(data_dir.glob(ext)))

        logger.info(f"Tìm thấy {len(files)} file cần xử lý.")

        for f_path in files:
            filename = f_path.name
            logger.info(f"─── Đang xử lý: {filename}")

            # Trích xuất số ký hiệu từ tên file
            match = re.search(r'(\d+)[-_](\d+)[-_]([A-Za-zĐđ\-\d]+)', filename)
            if not match:
                if "thuong mai" in filename.lower():
                    keyword = "36/2005/QH11"
                elif "thu nhap doanh nghiep" in filename.lower() or "thuế thu nhập" in filename.lower():
                    keyword = "14/2008/QH12"
                else:
                    logger.warning(f"Bỏ qua - không nhận diện được số ký hiệu từ: {filename}")
                    continue
            else:
                num = match.group(1)
                year = match.group(2)
                symbol = match.group(3).upper().replace("_", "/")
                if "ND" in symbol and "NĐ" not in symbol:
                    symbol = symbol.replace("ND", "NĐ")
                keyword = f"{num}/{year}/{symbol}"

            logger.info(f"Số ký hiệu: {keyword}")

            # 1. Tìm ItemID qua sitemap
            item_id = self.search_law_id(keyword)
            if not item_id:
                time.sleep(1)
                continue

            # 2. Lấy toàn văn + metadata qua Server Action
            full_text, metadata = self.fetch_full_text_and_metadata(item_id)

            if not metadata:
                logger.warning(f"Không lấy được metadata cho {keyword}, bỏ qua.")
                time.sleep(1)
                continue

            # 3. Xây dựng registry entry từ metadata
            normalized_key = keyword.lower()
            file_key = filename.rsplit(".", 1)[0].lower()

            # Xác định trạng thái hiệu lực từ code
            status = "ACTIVE"
            eff_status = metadata.get("effStatus", {})
            if isinstance(eff_status, dict):
                code = eff_status.get("code", "")
                if code == "CHL":         # Còn hiệu lực
                    status = "ACTIVE"
                elif code in ("HHL", "HHLMot"):  # Hết hiệu lực (toàn bộ hoặc một phần)
                    status = "EXPIRED"
                else:
                    status = eff_status.get("name", "ACTIVE")

            # Ngày có hiệu lực (lấy phần YYYY-MM-DD)
            effective_date = (metadata.get("effFrom") or "")[:10] or None

            reg_entry = {
                "status": status,
                "superseded_by": None,
                "url": f"{VBPL_BASE}/van-ban/chi-tiet/{item_id}",
                "effective_date": effective_date,
                "law_number": metadata.get("docNum", keyword),
                "title": metadata.get("title", ""),
            }

            self.registry[normalized_key] = reg_entry
            self.registry[file_key] = reg_entry

            logger.info(f"Đã lưu registry: {keyword} | Status={status} | ID={item_id}")

            # 4. AI phân tích điều khoản bãi bỏ/thay thế
            if full_text:
                ai_result = self.analyze_expiration_with_ai(full_text)
                for expired_law in ai_result.get("expired_laws", []):
                    logger.info(f"AI phát hiện luật bị bãi bỏ: {expired_law}")
                    exp_norm = expired_law.lower().strip()
                    updated = False
                    for key in list(self.registry.keys()):
                        if exp_norm in key or key in exp_norm:
                            self.registry[key]["status"] = "EXPIRED"
                            self.registry[key]["superseded_by"] = keyword
                            logger.info(f"Đã đánh dấu EXPIRED: {key}")
                            updated = True

                    if not updated:
                        self.registry[exp_norm] = {
                            "status": "EXPIRED",
                            "superseded_by": keyword,
                            "url": "",
                            "effective_date": None,
                        }

            self.save_registry()
            time.sleep(2)  # Lịch sự với server

        logger.info("✅ Hoàn thành đồng bộ hóa kho dữ liệu luật từ VBPL!")

    def crawl_target_sme_laws(self):
        """Crawl danh sách các văn bản hỗ trợ SME chỉ định."""
        logger.info("Bắt đầu crawl các văn bản hỗ trợ SME...")
        chatbot_data_laws = pathlib.Path(os.path.dirname(__file__)).parent / "data_laws"
        chatbot_data_laws.mkdir(exist_ok=True)
        
        target_laws = [
            {"keyword": "04/2017/QH14", "name": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa"},
            {"keyword": "10-NQ/TW", "name": "Nghị quyết 10-NQ/TW của Ban Chấp hành Trung ương"},
            {"keyword": "11-NQ/TW", "name": "Nghị quyết 11-NQ/TW của Ban Chấp hành Trung ương"},
            {"keyword": "68-NQ/TW", "name": "Nghị quyết 68-NQ/TW của Bộ Chính trị"},
            {"keyword": "198/2025/QH15", "name": "Nghị quyết 198/2025/QH15 của Quốc hội"},
            {"keyword": "80/2021/NĐ-CP", "name": "Nghị định 80/2021/NĐ-CP"},
            {"keyword": "55/2019/NĐ-CP", "name": "Nghị định 55/2019/NĐ-CP"},
            {"keyword": "20/2026/NĐ-CP", "name": "Nghị định 20/2026/NĐ-CP"},
            {"keyword": "57/2018/NĐ-CP", "name": "Nghị định 57/2018/NĐ-CP"},
            {"keyword": "121/2025/NĐ-CP", "name": "Nghị định 121/2025/NĐ-CP"},
            {"keyword": "07/2020/TT-BKHCN", "name": "Thông tư 07/2020/TT-BKHCN"},
            {"keyword": "14/2025/TT-NHNN", "name": "Thông tư 14/2025/TT-NHNN"},
            {"keyword": "133/2016/TT-BTC", "name": "Thông tư 133/2016/TT-BTC"},
            {"keyword": "58/2026/TT-BTC", "name": "Thông tư 58/2026/TT-BTC"},
            {"keyword": "52/2023/TT-BTC", "name": "Thông tư 52/2023/TT-BTC"},
            {"keyword": "523/QĐ-BTP", "name": "Quyết định 523/QĐ-BTP"},
            {"keyword": "84/QĐ-TTg", "name": "Quyết định 84/QĐ-TTg"},
            {"keyword": "2326/QĐ-TTg", "name": "Quyết định 2326/QĐ-TTg"},
            {"keyword": "3896/CT-CS", "name": "Công văn 3896/CT-CS"},
            {"keyword": "3897/CT-CS", "name": "Công văn 3897/CT-CS"},
            {"keyword": "59/2020/QH14", "name": "Luật Doanh nghiệp số 59/2020/QH14"},
            {"keyword": "38/2019/QH14", "name": "Luật Quản lý thuế số 38/2019/QH14"},
            
            # Văn bản chuyên ngành mới bổ sung
            {"keyword": "19/2018/QĐ-TTg", "name": "Quyết định số 19/2018/QĐ-TTg về tiêu chí công nhận doanh nghiệp nông nghiệp ứng dụng công nghệ cao"},
            {"keyword": "1738/QĐ-BNNMT", "name": "Quyết định số 1738/QĐ-BNNMT công bố thủ tục hành chính về doanh nghiệp nông nghiệp ứng dụng công nghệ cao"},
            {"keyword": "111/2015/NĐ-CP", "name": "Nghị định số 111/2015/NĐ-CP về phát triển công nghiệp hỗ trợ"},
            {"keyword": "10/2021/QĐ-TTg", "name": "Quyết định số 10/2021/QĐ-TTg quy định tiêu chí xác định doanh nghiệp công nghệ cao"},
            {"keyword": "55/2010/QĐ-TTg", "name": "Quyết định số 55/2010/QĐ-TTg về thẩm quyền chứng nhận doanh nghiệp công nghệ cao"},
            {"keyword": "18/2019/QĐ-TTg", "name": "Quyết định số 18/2019/QĐ-TTg quy định nhập khẩu máy móc thiết bị dây chuyền công nghệ đã qua sử dụng"},
            {"keyword": "28/2022/QĐ-TTg", "name": "Quyết định số 28/2022/QĐ-TTg sửa đổi Quyết định 18/2019/QĐ-TTg"},
            {"keyword": "66/2024/NĐ-CP", "name": "Nghị định số 66/2024/NĐ-CP quản lý nhập khẩu hàng hóa tân trang theo Hiệp định EVFTA, UKVFTA"}
        ]
        
        def keyword_to_filename(kw):
            norm = kw.lower().replace('đ', 'd')
            norm = norm.replace("nq/tw", "nq-tw")
            norm = norm.replace("nq-tw", "nq-tw")
            safe_name = re.sub(r'[^a-z0-9]', '-', norm)
            safe_name = re.sub(r'-+', '-', safe_name).strip('-')
            return f"{safe_name}.txt"

        store = None
        try:
            from chatbot.database.vector_store import build_or_load_store
            store = build_or_load_store()
        except Exception as e:
            logger.error(f"Không thể khởi tạo Vector Store: {e}")

        for item in target_laws:
            keyword = item["keyword"]
            filename = keyword_to_filename(keyword)
            output_path = chatbot_data_laws / filename
            
            logger.info(f"Đang xử lý SME law: {keyword} ({item['name']}) -> {filename}")
            
            # 1. Tìm Item ID
            item_id = self.search_law_id(keyword)
            if not item_id:
                logger.warning(f"Không tìm thấy ItemID cho {keyword}")
                time.sleep(1.5)
                continue
                
            # 2. Lấy toàn văn + metadata
            full_text, metadata = self.fetch_full_text_and_metadata(item_id)
            if not metadata or not full_text:
                logger.warning(f"Không tải được nội dung cho {keyword} (ID={item_id})")
                time.sleep(1.5)
                continue
                
            # 3. Lưu file văn bản
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            logger.info(f"Đã lưu file: {filename}")
            
            # 4. Lưu registry
            normalized_key = keyword.lower()
            file_key = filename.rsplit(".", 1)[0].lower()
            
            status = "ACTIVE"
            eff_status = metadata.get("effStatus", {})
            if isinstance(eff_status, dict):
                code = eff_status.get("code", "")
                if code == "CHL":
                    status = "ACTIVE"
                elif code in ("HHL", "HHLMot"):
                    status = "EXPIRED"
                else:
                    status = eff_status.get("name", "ACTIVE")
                    
            effective_date = (metadata.get("effFrom") or "")[:10] or None
            
            reg_entry = {
                "status": status,
                "superseded_by": None,
                "url": f"{VBPL_BASE}/van-ban/chi-tiet/{item_id}",
                "effective_date": effective_date,
                "law_number": metadata.get("docNum", keyword),
                "title": metadata.get("title", item["name"]),
            }
            
            self.registry[normalized_key] = reg_entry
            self.registry[file_key] = reg_entry
            self.save_registry()
            
            # 5. Cập nhật Vector Store RAG
            try:
                if store:
                    is_indexed = any(meta.get("source_file") == filename for meta in store.corpus_meta)
                    if not is_indexed:
                        logger.info(f"Đang index file {filename} vào Vector DB...")
                        success = store.update_index(output_path)
                        if success:
                            logger.info(f"Đã index thành công {filename} vào Vector DB.")
                        else:
                            logger.warning(f"Lỗi index {filename}.")
                    else:
                        logger.info(f"File {filename} đã được index trước đó.")
            except Exception as ev:
                logger.error(f"Lỗi khi cập nhật Vector Store: {ev}")
                
            time.sleep(1.5)

    def run_daily_crawl(self):
        """Khởi chạy crawl dữ liệu."""
        self.crawl_target_sme_laws()
        self.crawl_existing_laws()


if __name__ == "__main__":
    crawler = VbplCrawler()
    crawler.run_daily_crawl()

