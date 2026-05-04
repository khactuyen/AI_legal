import streamlit as st
import pathlib
import json
import re

# Import các hàm logic từ Chatbot.py
from Chatbot import (
    build_or_load_store,
    analyze_contract_file,
    read_contract_file,
    draft_new_contract,
    auto_delete_temp_files,
    process_user_message  # Hàm xử lý thông minh (NLP + CoT + RAG)
)

# ============================================================
# 1. CẤU HÌNH TRANG
# ============================================================
st.set_page_config(
    page_title="AI Legal Assistant",
    page_icon="⚖️",
    layout="centered"
)

# ============================================================
# 2. CSS TÙY CHỈNH (LIGHT PROFESSIONAL STYLE)
# ============================================================
FINAL_CSS = """
<style>
    /* 1. NỀN TRANG */
    .stApp {
        background-color: #FDFCF0;
        color: #333;
    }
    
    /* Font chữ chung */
    h1, h2, h3, p, div {
        font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    }

    /* 2. THANH CHAT INPUT */
    .stChatInput {
        position: fixed !important;
        bottom: 30px !important;
        left: 80px !important;   
        width: calc(100% - 100px) !important;
        z-index: 1000;
        background: transparent !important;
    }
    
    [data-testid="stChatInput"] {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D1D1 !important;
        border-radius: 25px !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        color: #333 !important;
    }

    /* 3. NÚT UPLOAD (GÓC TRÁI) */
    [data-testid="stPopover"] {
        position: fixed !important;
        bottom: 40px !important;
        left: 25px !important;
        width: 45px !important;
        height: 45px !important;
        z-index: 9999 !important;
    }

    [data-testid="stPopover"] > button {
        width: 45px !important;
        height: 45px !important;
        border-radius: 50% !important;
        background-color: #FFFFFF !important;
        color: #0E3B6C !important;
        border: 2px solid #0E3B6C !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.3rem !important;
        transition: transform 0.2s !important;
    }
    
    [data-testid="stPopover"] > button:hover {
        transform: scale(1.1) !important;
        background-color: #0E3B6C !important;
        color: white !important;
    }

    /* Nút Gửi tin nhắn */
    [data-testid="stChatInputSubmitButton"] {
        background-color: #0E3B6C !important;
        color: white !important;
        border-radius: 50% !important;
    }

    /* Ẩn Sidebar & Footer */
    [data-testid="stSidebar"] { display: none; }
    footer {visibility: hidden;}
    
    /* Đẩy nội dung lên cao */
    .main .block-container {
        padding-bottom: 150px !important;
    }
</style>
"""
st.markdown(FINAL_CSS, unsafe_allow_html=True)

# ============================================================
# 3. KHỞI TẠO STATE
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = [] 

if "store" not in st.session_state:
    with st.spinner("⏳ Đang khởi động hệ thống Legal AI..."):
        st.session_state.store = build_or_load_store()

if "current_contract_text" not in st.session_state:
    st.session_state.current_contract_text = ""
if "current_contract_path" not in st.session_state:
    st.session_state.current_contract_path = ""

# ============================================================
# 4. NÚT UPLOAD (POPOVER)
# ============================================================
with st.popover("📎", help="Tải tài liệu"):
    st.markdown("##### 📂 Chọn tài liệu")
    
    u_contract = st.file_uploader("Chọn file", type=["docx", "txt"], key="u_contract", label_visibility="collapsed")
    
    if u_contract:
        temp_dir = pathlib.Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        c_path = temp_dir / u_contract.name
        
        if str(c_path) != st.session_state.current_contract_path:
            with open(c_path, "wb") as f:
                f.write(u_contract.getbuffer())
            
            st.session_state.current_contract_path = str(c_path)
            st.session_state.current_contract_text = read_contract_file(c_path)
            
            st.toast(f"Đã nhận: {u_contract.name}", icon="✅")
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"Tôi đã tiếp nhận file **{u_contract.name}**. Bạn muốn tôi **Phân tích rủi ro**, **Chấm điểm** hay hỏi chi tiết về điều khoản nào?"
            })
            st.rerun()

    if st.button("🗑️ Xóa đoạn chat", use_container_width=True):
        auto_delete_temp_files()
        st.session_state.messages = []
        st.session_state.current_contract_text = ""
        st.rerun()

# ============================================================
# 5. MÀN HÌNH CHÍNH
# ============================================================
if not st.session_state.messages:
    st.markdown("""
        <div style="margin-top: 50px; text-align: center;">
            <div style="font-size: 4rem; margin-bottom: 10px;">⚖️</div>
            <h1 style="color: #0E3B6C; margin-bottom: 10px;">AI Legal Assistant</h1>
            <p style="color: #555; font-size: 1.1rem;">
                Trợ lý Pháp lý Doanh nghiệp Thông minh.<br>
                Hỗ trợ Tra cứu Luật, Soạn thảo & Thẩm định Hợp đồng.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    st.markdown("""<style>div.stButton > button {width: 100%; border-radius: 15px; border: 1px solid #DDD; background: white; color: #0E3B6C;}</style>""", unsafe_allow_html=True)

    with c1:
        if st.button("📝 Soạn Hợp đồng"):
            st.session_state.messages.append({"role": "user", "content": "Soạn thảo hợp đồng mua bán hàng hóa"})
            st.rerun()
    with c2:
        if st.button("🛡️ Check Rủi ro"):
            st.session_state.messages.append({"role": "user", "content": "Phân tích rủi ro hợp đồng này"})
            st.rerun()
    with c3:
        if st.button("🔍 Tra cứu Luật"):
            st.session_state.messages.append({"role": "user", "content": "Thủ tục thành lập công ty TNHH"})
            st.rerun()

# ============================================================
# 6. HIỂN THỊ LỊCH SỬ CHAT
# ============================================================
else:
    for msg in st.session_state.messages:
        avatar = "👤" if msg["role"] == "user" else "⚖️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

# ============================================================
# 7. THANH CHAT & LOGIC TRẢ LỜI
# ============================================================
if prompt := st.chat_input("Nhập nội dung cần tư vấn..."):
    
    # 1. Lưu tin nhắn user
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 2. Hiển thị ngay lập tức
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)

    # 3. Gọi AI xử lý ngay
    with st.chat_message("assistant", avatar="⚖️"):
        with st.spinner("AI đang phân tích..."):
            response_text = ""
            
            # --- LOGIC A: CÓ FILE HỢP ĐỒNG (Ưu tiên Phân tích File) ---
            # (Chỉ chạy khi có file VÀ từ khóa liên quan đến phân tích)
            if st.session_state.current_contract_text and any(k in prompt.lower() for k in ["phân tích", "soát", "điểm", "rủi ro", "review", "kiểm tra"]):
                raw_res = analyze_contract_file(
                    st.session_state.store,
                    st.session_state.current_contract_path,
                    checklist_text=None, 
                    safe_mode=True
                )
                
                # Xử lý hiển thị thẻ điểm (JSON Score)
                json_match = re.search(r'```json\n({.*?})\n```', raw_res, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        score = data.get('score', 0)
                        color = "#2E7D32" if score >= 80 else "#F9A825" if score >= 50 else "#C62828"
                        
                        st.markdown(f"""
                        <div style="border: 1px solid #DDD; border-radius: 8px; padding: 15px; background: #FFF; border-left: 6px solid {color}; margin-bottom: 15px;">
                            <h3 style="margin:0; color: {color};">Điểm an toàn: {score}/100</h3>
                            <p style="margin:5px 0 0 0; color: #555;">Mức độ rủi ro: <b>{data.get('risk_level')}</b></p>
                            <p style="font-style: italic; font-size: 0.9rem; color: #777;">"{data.get('risk_summary')}"</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        response_text = raw_res.replace(json_match.group(0), "")
                    except:
                        response_text = raw_res
                else:
                    response_text = raw_res

            # --- LOGIC B: CHAT THƯỜNG (Hỏi đáp Luật / Soạn thảo) ---
            else:
                # Gọi hàm thông minh process_user_message (đã có NLP sửa lỗi + CoT)
                response_text = process_user_message(
                    st.session_state.store,
                    prompt,
                    safe_mode=True
                )
            
            # Hiển thị kết quả
            st.markdown(response_text)
            
    # 4. Lưu kết quả vào Session State
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    
    # 5. Rerun nếu là tin nhắn đầu tiên để xóa màn hình Welcome
    if len(st.session_state.messages) == 2:
        st.rerun()