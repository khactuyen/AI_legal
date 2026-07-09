# Sử dụng Python 3.11 slim để tối ưu dung lượng image
FROM python:3.11-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements và cài đặt dependencies
COPY chatbot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Xóa các thư mục tạm có thể bị lẫn vào trong quá trình build (tùy chọn)
RUN rm -rf temp_uploads/*

# Expose port 8000 cho FastAPI Backend
EXPOSE 8000

# Lệnh chạy ứng dụng FastAPI khi container khởi động
CMD ["uvicorn", "chatbot.api:app", "--host", "0.0.0.0", "--port", "8000"]
