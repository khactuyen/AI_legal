from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import sys
import pathlib
import shutil
import logging
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# Add the chatbot folder to Python path to allow imports of local modules (Chatbot, guardrails)
# Trigger reload: 2026-07-18 14:36
chatbot_dir = str(pathlib.Path(__file__).parent)
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Cấu hình Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("api")

# Import logic từ Chatbot.py
from Chatbot import build_or_load_store, process_user_message_stream, analyze_contract_file, process_user_message_deep_stream
from auto_template import fill_template
from scheduled_agents import start_scheduler
from guardrails import PromptGuardrail

load_dotenv()
API_KEY = os.getenv("API_KEY", "legal-sme-secret-key-2026")
header_scheme = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(header_scheme)):
    if api_key != API_KEY:
        logger.warning("Truy cập từ chối: Sai API Key")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid API Key")
    return api_key

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AI Legal Assistant API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup_event():
    global vector_store
    try:
        logger.info("Đang khởi tạo Hệ thống AI Legal Assistant...")
        vector_store = build_or_load_store()
        logger.info("Hệ thống đã sẵn sàng!")
    except Exception as e:
        logger.error(f"Lỗi khởi tạo hệ thống RAG: {e}", exc_info=True)
        vector_store = None
    start_scheduler()

# Khóa CORS để an toàn
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:2000", "http://localhost:3007", "http://localhost:5173", "http://localhost:8501",
        "http://127.0.0.1:3000", "http://127.0.0.1:2000", "http://127.0.0.1:3007"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from chatbot.config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Bảng lưu tin nhắn
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            client_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Bảng quản lý session
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            client_id TEXT,
            title TEXT,
            summary TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Bảng lưu feedback của user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT, 
            message_content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Bảng lưu cảnh báo (Scheduled Agents)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Bảng lưu thông tin hợp đồng đồng bộ từ Data Connectors
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT UNIQUE,
            filename TEXT,
            contract_name TEXT,
            partner_name TEXT,
            expiration_date DATE,
            status TEXT DEFAULT 'ACTIVE',
            last_notified_at DATETIME,
            notification_tier TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def create_or_update_session(session_id: str, client_id: str, message_content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    if not row:
        title = message_content[:30] + "..." if len(message_content) > 30 else message_content
        cursor.execute("INSERT INTO sessions (session_id, client_id, title) VALUES (?, ?, ?)", (session_id, client_id, title))
    else:
        cursor.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def log_to_db(session_id: str, client_id: str, role: str, content: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (session_id, client_id, role, content) VALUES (?, ?, ?, ?)", 
                       (session_id, client_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Log Error: {e}")

def get_session_history_db(session_id: str, client_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM conversations WHERE session_id = ? AND client_id = ? ORDER BY id ASC", (session_id, client_id))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

# Bộ nhớ ngắn hạn (Short-term memory)
session_memory = {}

vector_store = None

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    client_id: str = "default_client"

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Legal Assistant API is running securely."}

@app.post("/chat")
@limiter.limit("15/minute")
def chat_endpoint(request: Request, body: ChatRequest, api_key: str = Depends(verify_api_key)):
    # Guardrail Layer 1: Chặn Jailbreak / Prompt Injection
    is_safe, refusal_reason = PromptGuardrail.check(body.message)
    if not is_safe:
        logger.warning(f"[Guardrail] Blocked message from {body.client_id}: {body.message[:50]}...")
        raise HTTPException(status_code=400, detail=refusal_reason)
    
    if vector_store is None:
        logger.error("API gọi RAG nhưng system down.")
        raise HTTPException(status_code=500, detail="Hệ thống AI chưa sẵn sàng.")
    
    session_id = body.session_id
    client_id = body.client_id
    
    # Lấy lịch sử từ DB thay vì RAM
    db_history = get_session_history_db(session_id, client_id)
    
    # Logic Rolling Summary (tạm thời lấy 10 tin mới nhất để giữ ngữ cảnh nhanh)
    history_for_ai = db_history[-10:] if len(db_history) > 10 else db_history
    
    # Cập nhật Session info
    create_or_update_session(session_id, client_id, body.message)
    
    def save_to_history(ai_response_text: str):
        log_to_db(session_id, client_id, "user", body.message)
        log_to_db(session_id, client_id, "assistant", ai_response_text)
        
    logger.info(f"Session '{session_id}' | User request: {body.message[:50]}...")
    
    return StreamingResponse(
        process_user_message_stream(vector_store, body.message, safe_mode=True, history=history_for_ai, on_complete=save_to_history), 
        media_type="text/event-stream"
    )

@app.post("/chat/deep")
@limiter.limit("5/minute")
def chat_deep_endpoint(request: Request, body: ChatRequest, api_key: str = Depends(verify_api_key)):
    # Guardrail Layer 1: Chặn Jailbreak / Prompt Injection
    is_safe, refusal_reason = PromptGuardrail.check(body.message)
    if not is_safe:
        logger.warning(f"[Guardrail] Blocked deep message from {body.client_id}: {body.message[:50]}...")
        raise HTTPException(status_code=400, detail=refusal_reason)
    
    if vector_store is None:
        logger.error("API gọi RAG nhưng system down.")
        raise HTTPException(status_code=500, detail="Hệ thống AI chưa sẵn sàng.")
    
    session_id = body.session_id
    client_id = body.client_id
    
    db_history = get_session_history_db(session_id, client_id)
    history_for_ai = db_history[-10:] if len(db_history) > 10 else db_history
    
    create_or_update_session(session_id, client_id, body.message)
    
    def save_to_history(ai_response_text: str):
        log_to_db(session_id, client_id, "user", body.message)
        log_to_db(session_id, client_id, "assistant", ai_response_text)
        
    logger.info(f"Session '{session_id}' DEEP MODE | User request: {body.message[:50]}...")
    
    return StreamingResponse(
        process_user_message_deep_stream(vector_store, body.message, safe_mode=True, history=history_for_ai, on_complete=save_to_history), 
        media_type="text/event-stream"
    )

# --- Các Endpoint Quản lý Lịch sử Chat ---

@app.get("/sessions")
def get_sessions(client_id: str, api_key: str = Depends(verify_api_key)):
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client_id")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, title, updated_at FROM sessions WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        rows = cursor.fetchall()
        conn.close()
        return {"sessions": [{"session_id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi tải lịch sử")

@app.get("/sessions/{session_id}")
def get_session_detail(session_id: str, client_id: str, api_key: str = Depends(verify_api_key)):
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client_id")
    history = get_session_history_db(session_id, client_id)
    return {"messages": history}

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, client_id: str, api_key: str = Depends(verify_api_key)):
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client_id")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Xác thực quyền sở hữu
        cursor.execute("SELECT 1 FROM sessions WHERE session_id = ? AND client_id = ?", (session_id, client_id))
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Forbidden or Not Found")
        
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi xóa phiên")

class FeedbackRequest(BaseModel):
    session_id: str
    action: str
    message_content: str = ""

@app.post("/feedback")
@limiter.limit("30/minute")
def feedback_endpoint(request: Request, body: FeedbackRequest, api_key: str = Depends(verify_api_key)):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO feedback_logs (session_id, action, message_content) VALUES (?, ?, ?)",
                       (body.session_id, body.action, body.message_content))
        conn.commit()
        conn.close()
        logger.info(f"Feedback nhận được: Session {body.session_id} - {body.action}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Lỗi lưu feedback: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

class AutoTemplateRequest(BaseModel):
    template_name: str
    context: dict

@app.post("/auto-template")
@limiter.limit("10/minute")
def auto_template_endpoint(request: Request, body: AutoTemplateRequest, api_key: str = Depends(verify_api_key)):
    try:
        output_path = fill_template(body.template_name, body.context)
        return FileResponse(path=output_path, filename=os.path.basename(output_path), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Lỗi generate auto-template: {e}")
        raise HTTPException(status_code=500, detail="Lỗi xử lý template")

@app.get("/download-template/{filename}")
def download_template_endpoint(filename: str):
    # Endpoint mở không cần API key để user có thể tải trực tiếp từ trình duyệt
    base_dir = pathlib.Path(__file__).parent
    file_path = base_dir / "templates" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(file_path), 
        filename=filename, 
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )


@app.get("/notifications")
def get_notifications(api_key: str = Depends(verify_api_key)):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, message, is_read, timestamp FROM notifications ORDER BY timestamp DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        return {"notifications": [{"id": r[0], "title": r[1], "message": r[2], "is_read": bool(r[3]), "timestamp": r[4]} for r in rows]}
    except Exception as e:
        logger.error(f"Lỗi fetch notifications: {e}")
        raise HTTPException(status_code=500, detail="Lỗi database")

@app.post("/analyze-contract")
@limiter.limit("5/minute")
async def analyze_contract_endpoint(request: Request, file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    if vector_store is None:
        raise HTTPException(status_code=500, detail="Hệ thống AI chưa sẵn sàng.")
        
    temp_dir = pathlib.Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Bắt đầu phân tích file: {file.filename}")
        
        from Chatbot import analyze_contract_file_stream
        
        # Generator function để stream response và tự dọn file sau khi xong
        async def stream_generator():
            try:
                for chunk in analyze_contract_file_stream(vector_store, file_path, safe_mode=True):
                    yield chunk
            finally:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info(f"Đã xóa file tạm {file.filename} để bảo mật.")
                    except Exception as ex:
                        logger.warning(f"Không thể xóa file {file.filename}: {ex}")
                        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Lỗi hệ thống với file {file.filename}: {str(e)}", exc_info=True)
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi phân tích hợp đồng.")

        logger.error(f"Lỗi hệ thống với file {file.filename}: {str(e)}", exc_info=True)
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi phân tích hợp đồng.")

import shutil
import os
try:
    src = r"C:\Users\LENOVO\.gemini\antigravity-ide\brain\56716e67-a122-44e7-9fa4-b1fe87eff0ad\legal_logo_elegant_vector_1784361103910.png"
    dst = r"d:\Project Save\chatbot law\app\public\logo.png"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
except Exception as e:
    print(f"Error copying logo: {e}")
