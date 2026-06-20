import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_PATH = "../chatbot/feedback.db"
OUTPUT_DIR = "reports"

def generate_audit_report():
    print("Bắt đầu chạy tiến trình Admin Audit Workflow...")
    
    if not os.path.exists(DB_PATH):
        print(f"Lỗi: Không tìm thấy Database tại {DB_PATH}")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    conn = sqlite3.connect(DB_PATH)
    
    # Lấy danh sách các session có bad feedback
    query_bad_sessions = """
        SELECT DISTINCT session_id
        FROM feedback_logs
        WHERE action = 'thumbs_down'
    """
    bad_sessions = pd.read_sql_query(query_bad_sessions, conn)
    
    if bad_sessions.empty:
        print("Tuyệt vời! Không có session nào bị cắm cờ (thumbs_down) trong thời gian qua.")
        conn.close()
        return
        
    report_lines = []
    report_lines.append(f"# Báo Cáo Kiểm Duyệt Hệ Thống AI Legal - {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append("\n**Mục đích:** Báo cáo này liệt kê các đoạn hội thoại mà người dùng đánh giá KHÔNG TỐT (báo cáo sai kiến thức, ảo giác). Các luật sư cần kiểm tra lại Vector DB hoặc thay đổi System Prompt.")
    
    for session_id in bad_sessions['session_id']:
        report_lines.append(f"\n## Session: `{session_id}`")
        
        # Lấy lịch sử chat của session này
        query_chat = f"SELECT role, content FROM conversations WHERE session_id = '{session_id}' ORDER BY timestamp ASC"
        chat_history = pd.read_sql_query(query_chat, conn)
        
        for _, row in chat_history.iterrows():
            role = "🧑 Khách hàng" if row['role'] == "user" else "🤖 AI"
            report_lines.append(f"**{role}:** {row['content']}")
            report_lines.append("---")
            
    report_content = "\n".join(report_lines)
    
    output_file = os.path.join(OUTPUT_DIR, f"audit_report_{datetime.now().strftime('%Y%m%d')}.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Đã xuất báo cáo kiểm duyệt ra file: {output_file}")
    conn.close()

if __name__ == "__main__":
    generate_audit_report()
