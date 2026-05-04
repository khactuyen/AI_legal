# Sử dụng Python 3.11 slim để tối ưu dung lượng image
FROM python:3.11-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết (nếu có)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Xóa các thư mục tạm có thể bị lẫn vào trong quá trình build (tùy chọn)
RUN rm -rf temp_uploads/*

# Expose port 8501 cho Streamlit
EXPOSE 8501

# Lệnh chạy ứng dụng khi container khởi động
CMD ["streamlit", "run", "app_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]
