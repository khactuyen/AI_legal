FROM node:18-alpine

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép các tệp cấu hình package
COPY package*.json ./

# Cài đặt thư viện phụ thuộc
RUN npm install

# Sao chép toàn bộ mã nguồn frontend
COPY . .

# Mở cổng 2000 cho Vite
EXPOSE 2000

# Khởi chạy server phát triển của Vite
CMD ["npm", "run", "dev"]
