# ⚖️ AI Legal Assistant

AI Legal Assistant là một trợ lý ảo pháp lý thông minh dành cho doanh nghiệp, được xây dựng dựa trên kiến trúc **RAG (Retrieval-Augmented Generation)**. Hệ thống kết hợp khả năng tìm kiếm ngữ nghĩa của **Vector Database (FAISS)** và sức mạnh suy luận của LLM **Google Gemini 2.5 Flash** để tự động tra cứu luật pháp, soạn thảo và phân tích rủi ro hợp đồng.

---

## ✨ Tính Năng Nổi Bật

1. **🔍 Tra Cứu Luật Thông Minh (RAG)**
   - Hệ thống tự động cắt văn bản luật theo cấu trúc "Điều luật" để giữ nguyên ngữ cảnh.
   - Tìm kiếm Hybrid kết hợp Semantic Search và Chain-of-Thought (CoT) để phân tích câu hỏi người dùng thành các query tối ưu.
2. **📝 Soạn Thảo Hợp Đồng**
   - Soạn thảo hợp đồng mới dựa trên các tiêu chuẩn pháp lý Việt Nam, đảm bảo đầy đủ cấu trúc: Quốc hiệu, Căn cứ pháp lý, Thông tin các bên, Điều khoản, v.v.
3. **🛡️ Thẩm Định & Phân Tích Rủi Ro Hợp Đồng**
   - **Tự động nhận diện (Classification):** Phân loại xem hợp đồng người dùng đưa vào là Bản mẫu (Template) hay Bản chốt (Final).
   - Đánh giá chất lượng biểu mẫu, cảnh báo các điều khoản thiếu hoặc chỉ ra rủi ro pháp lý chi tiết kèm chấm điểm (Score).
4. **🧠 Smart NLP Processor**
   - Nhận diện intent người dùng (Tra cứu, Soạn thảo, Thẩm định) và tự động sửa lỗi chính tả/teencode trước khi xử lý.

---

## 🛠️ Công Nghệ Sử Dụng

- **Frontend UI:** Streamlit (Custom CSS UI)
- **AI / LLM:** Google Generative AI (Gemini 2.5 Flash)
- **Vector Database:** FAISS (Facebook AI Similarity Search)
- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Data Processing:** `python-docx`, Regular Expressions

---

## 📁 Cấu Trúc Thư Mục

```text
├── app_ui.py               # File chính khởi chạy giao diện (Streamlit)
├── Chatbot.py              # Logic xử lý chính (AI, RAG, File, Xử lý văn bản)
├── requirements.txt        # Danh sách các thư viện Python cần thiết
├── data_laws/              # Chứa các file Word/Văn bản luật (Nguồn dữ liệu)
├── index_laws/             # Thư mục lưu trữ Vector DB Index (FAISS)
├── CheckList/              # Chứa các file Checklist tiêu chuẩn dùng để review hợp đồng
├── sample_contracts/       # Chứa các hợp đồng mẫu để tham khảo
├── docs_and_references/    # Tài liệu dự án, file nháp, quy trình bảo mật
└── .env                    # File chứa cấu hình bảo mật (Gemini API Key, GCS...)
```

---

## 🚀 Hướng Dẫn Cài Đặt (Chạy Local)

### Yêu cầu tiên quyết
- Python 3.9 trở lên (Khuyến nghị 3.11).
- API Key của Google Gemini.

### 1. Cài đặt môi trường
Clone kho lưu trữ và tạo môi trường ảo:
```bash
# Tạo và kích hoạt môi trường ảo
python -m venv venv311
# Trên Windows:
venv311\Scripts\activate
# Trên macOS/Linux:
source venv311/bin/activate
```

### 2. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường
Tạo một file `.env` ở thư mục gốc và cung cấp API Key của bạn:
```env
GEMINI_API_KEY="AIzaSyYourGeminiKeyHere..."
# Tùy chọn: GCS_BUCKET_NAME="my-bucket-name"
```

### 4. Khởi chạy ứng dụng
```bash
streamlit run app_ui.py
```
Giao diện sẽ tự động mở lên tại địa chỉ `http://localhost:8501`.

---

## 🐳 Hướng Dẫn Triển Khai Với Docker

Dự án đã được đóng gói sẵn Dockerfile để bạn dễ dàng triển khai lên máy chủ.

### 1. Build Docker Image
```bash
docker build -t ai-legal-assistant .
```

### 2. Chạy Container
Bạn nhớ truyền file `.env` vào container để nhận cấu hình API Key:
```bash
docker run -d -p 8501:8501 --env-file .env --name legal_bot ai-legal-assistant
```

Ứng dụng của bạn giờ đây đã có thể truy cập qua cổng 8501!

---

## 📝 Lưu ý Phát Triển (To-do)
- Tích hợp thêm **Rank_BM25** và **Cross-Encoder** đầy đủ trong hàm `build_from_docs` để tối ưu thứ hạng tìm kiếm (Hybrid Search).
- Bổ sung việc lưu Metadata tự động từ tên file (Năm ban hành, Số hiệu văn bản) để AI trích dẫn chính xác hơn.
- Triển khai FastAPI (hiện đã có trong requirements) nếu muốn tách biệt backend và frontend thành các microservices.
