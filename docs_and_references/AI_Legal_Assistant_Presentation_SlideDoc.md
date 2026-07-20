# ⚖️ TÀI LIỆU TRÌNH BÀY DỰ ÁN (SLIDE-DOC)
## HỆ THỐNG TRỢ LÝ AI PHÁP LÝ DOANH NGHIỆP (AI LEGAL ASSISTANT)

Tài liệu này được thiết kế theo phong cách trực quan, gãy gọn như các trang slide thuyết trình, nhằm tóm tắt đầy đủ các đột phá công nghệ và kiến trúc thực tế của hệ thống.

---

### 🏷️ Slide 1: Tổng Quan Dự Án & Tầm Nhìn Sản Phẩm
**"Giải pháp AI RAG chuyên sâu hỗ trợ tra cứu luật và phân tích tài liệu pháp lý tự động cho doanh nghiệp SME."**

*   **Thực Trạng Thị Trường:**
    *   Doanh nghiệp nhỏ và vừa (SME) tại Việt Nam thường không có phòng ban pháp chế riêng vì chi phí vận hành quá lớn.
    *   Việc tra cứu quy định pháp luật hoặc rà soát hợp đồng thủ công tốn nhiều thời gian và dễ xảy ra rủi ro do thiếu chuyên môn.
*   **Giải Pháp Đột Phá:**
    *   Xây dựng trợ lý ảo thông minh giúp tự động hóa quá trình tra cứu quy định pháp luật doanh nghiệp.
    *   Hỗ trợ đọc hiểu, phân tích tài liệu và phát hiện các rủi ro pháp lý tiềm ẩn tức thì.
*   **Công Nghệ Chủ Đạo:**
    *   FastAPI (Backend) + React (Frontend) + Google Gemini AI.

---

### 🔗 Slide 2: Giải Pháp Lai BookRAG và LightRAG
**"Kết hợp trục dọc (Phân cấp cấu trúc văn bản) và trục ngang (Mối quan hệ thực thể liên kết chéo)."**

*   **BookRAG (Trục Dọc - Hierarchical Tree):**
    *   *Tính chất văn bản luật:* Có cấu trúc cây mục lục nghiêm ngặt (Chương $\rightarrow$ Điều $\rightarrow$ Khoản $\rightarrow$ Điểm).
    *   *Giải pháp:* Lập chỉ mục tài liệu theo đúng cấu trúc hình cây của Bộ luật. Giúp AI luôn định vị chính xác phạm vi điều khoản đang đọc, giữ nguyên vẹn ngữ cảnh phân cấp gốc mà không bị phân mảnh thông tin.
*   **LightRAG (Trục Ngang - Knowledge Graph):**
    *   *Tính chất quan hệ:* Các điều luật ở các chương khác nhau (hoặc các bộ luật khác nhau) thường liên kết và bổ trợ cho nhau.
    *   *Giải pháp:* Tạo đồ thị liên kết chéo giữa các khái niệm, thực thể pháp lý.
*   **Sự Phối Hợp Hoàn Hảo:**
    *   **BookRAG** đóng vai trò tìm kiếm dọc (xác định chính xác Điều/Khoản luật áp dụng).
    *   **LightRAG** thực hiện tìm kiếm ngang (quét các mối liên kết chéo sang các Nghị định, Thông tư hoặc Bộ luật liên quan).

---

### 🧠 Slide 3: Kiến Trúc RAG & Sức Mạnh Của Hyper-Extract
**"Sử dụng Siêu đồ thị (Hypergraph), Tuyến tính thời gian và lai ghép dữ liệu tìm kiếm."**

*   **Hyper-Extract (Siêu đồ thị - Hypergraph):**
    *   Khác với đồ thị nhị phân thông thường, Hyper-Extract tạo ra các **Siêu cạnh (Hyperedge)** (sử dụng cấu trúc Bipartite Graph trong NetworkX) kết nối $N$ thực thể cùng tham gia một sự kiện pháp lý phức tạp (Bên A + Bên B + Tài sản thế chấp + Ngân hàng bảo lãnh) để chống đứt gãy ngữ cảnh.
*   **Temporal Log (Dòng thời gian sự kiện):**
    *   Trích xuất và sắp xếp các mốc thời gian hiệu lực của văn bản luật hoặc tiến trình thực hiện hợp đồng theo trình tự thời gian tuyến tính.
*   **Tìm kiếm Lai (Hybrid Search) & RRF Fusion:**
    *   Hòa trộn kết quả tìm kiếm ngữ nghĩa Dense (Qdrant) và tìm kiếm từ khóa Sparse (BM25Okapi + ViTokenizer) bằng công thức Reciprocal Rank Fusion (RRF).
*   **Lọc Hiệu Lực Luật tự động:**
    *   Tra cứu `law_registry.json` loại bỏ văn bản trạng thái **EXPIRED** và tự động lọc giữ bản mới nhất theo năm ban hành.

---

### ⚙️ Slide 4: Kiến Trúc Hệ Thống (System Architecture) & 2 Chế Độ Vận Hành
**"Sự khác biệt rõ ràng giữa Instant Mode và Deep Thinking Mode bám sát Source Code."**

#### Chế độ Thường (Instant Mode - `process_user_message_stream`):
1.  **Lọc chitchat:** Quét `check_conversational_query()` chào hỏi/cảm ơn để trả lời ngay mà không cần chạy RAG.
2.  **RAG Tìm Kiếm Nhanh:** Gọi `store.search(use_query_expansion=False)` tìm kiếm lai không dùng mở rộng truy vấn.
3.  **ONNX Reranker:** Chạy mô hình `bge-reranker-base` cục bộ lấy Top 5 chunks tốt nhất.
4.  **Hậu kiểm nguồn:** Chạy xác thực trích dẫn qua `GroundingGuardrail` và tự sửa lỗi ngầm `generate_self_correction`.

#### Chế độ Phân Tích Sâu (Deep Thinking Mode - `process_user_message_deep_stream`):
1.  **Query Expansion:** Chạy `generate_search_queries()` phân tích từ đồng nghĩa, dịch teencode/từ lóng thành từ khóa luật chuẩn.
2.  **HyDE Document:** Chạy `generate_hyde_document()` để sinh văn bản giả định mang văn phong luật làm phong phú vector tìm kiếm.
3.  **Double Reranking:** Tái xếp hạng bằng Cross-Encoder trên ONNX, tiếp tục chạy **LLM Rerank** (`rerank_with_llm`) lấy Top 15 chunks hoàn hảo nhất.
4.  **Phân Tích Đa Chiều:** Quét siêu đồ thị và timeline để sinh Bản ý kiến tư vấn pháp lý chuyên sâu qua `call_gemini_deep_qa_stream`.

---

### 🔐 Slide 5: Cơ Chiế Bảo Vệ & Chống Ảo Giác AI
**"Đảm bảo tính chính xác và an toàn tuyệt đối cho các quyết định pháp lý của doanh nghiệp."**

*   **Grounding Guardrail:**
    *   Trước khi trả câu hỏi cho người dùng, hệ thống sẽ tự động quét toàn bộ các trích dẫn pháp lý (số hiệu Điều, Khoản, Luật, Nghị định) trong câu trả lời và đối chiếu chéo với cơ sở dữ liệu gốc để xác thực.
*   **Tự Sửa Lỗi Ngầm (Self-Correction LLM Engine):**
    *   Nếu phát hiện trích dẫn sai luật (ảo giác AI), hệ thống tự động yêu cầu LLM viết lại câu trả lời sạch dựa trên nguồn dữ liệu luật nội bộ mà **không hiển thị cảnh báo lỗi** ra màn hình, giữ trải nghiệm mượt mà cho khách hàng.
*   **Bảo Mật Dữ Liệu Doanh Nghiệp (Redaction Module):**
    *   Tự động che giấu các dữ liệu nhạy cảm (tên riêng, số tài khoản ngân hàng, thông tin giao dịch) trước khi gửi qua API bên ngoài.

---

### 📊 Slide 6: Kiểm Sốat Chất Lượng & Phản Hồi Từ Thực Tế
**"Vòng lặp tối ưu hóa chất lượng hệ thống dựa trên đánh giá của người dùng."**

*   **Implicit Feedback API:**
    *   Người dùng có thể trực tiếp đánh giá câu trả lời thông qua các nút **[👍 Hữu ích]**, **[👎 Sai kiến thức]** hoặc **[📋 Copy]** trên giao diện chat. Dữ liệu này được lưu trực tiếp vào cơ sở dữ liệu để phục vụ cải tiến.
*   **Admin Audit Job (`admin_audit_job.py`):**
    *   Tập lệnh định kỳ dành cho quản trị viên/luật sư nội bộ của doanh nghiệp quét toàn bộ cơ sở dữ liệu để tìm ra các phiên chat bị đánh giá thấp (Thumbs down), xuất báo cáo Markdown chi tiết để kiểm tra và tinh chỉnh Prompt/Database.
