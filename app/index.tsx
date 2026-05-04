
import React, { useState, useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { GoogleGenAI } from "@google/genai";

// Initialize Gemini API
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

// --- Types ---
type Message = {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
};

type FileData = {
  name: string;
  content: string;
};

// --- Icons ---
const UploadIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
    <polyline points="17 8 12 3 7 8"></polyline>
    <line x1="12" y1="3" x2="12" y2="15"></line>
  </svg>
);

const SendIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"></line>
    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
  </svg>
);

const BotIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#4285F4' }}>
    <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"></path>
    <path d="M4 10a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6z"></path>
    <path d="M8 14h.01"></path>
    <path d="M16 14h.01"></path>
    <path d="M6 20v2"></path>
    <path d="M18 20v2"></path>
  </svg>
);

const TrashIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"></polyline>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
  </svg>
);

const PlusIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"></line>
    <line x1="5" y1="12" x2="19" y2="12"></line>
  </svg>
);

// --- Main Component ---
function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentFile, setCurrentFile] = useState<FileData | null>(null);
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Simple text file reading for demo purposes
    // In a real app, you'd use libraries for DOCX parsing on the client or server
    const reader = new FileReader();
    reader.onload = async (e) => {
      const text = e.target?.result as string;
      setCurrentFile({
        name: file.name,
        content: text
      });
      
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Đã nhận file **${file.name}**. Bạn cần tôi **Chấm điểm**, **Phân tích rủi ro** hay **Tóm tắt** tài liệu này?`
      }]);
      setShowUploadMenu(false);
    };
    reader.readAsText(file);
  };

  const clearSession = () => {
    setMessages([]);
    setCurrentFile(null);
    setShowUploadMenu(false);
  };

  const sendMessage = async (textOverride?: string) => {
    const userText = textOverride || input;
    if (!userText.trim()) return;

    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userText }]);
    setIsLoading(true);

    try {
      // Construct prompt with context
      let finalPrompt = userText;
      let systemInstruction = "Bạn là trợ lý pháp lý AI chuyên nghiệp (AI Legal Assistant). Bạn hỗ trợ soạn thảo hợp đồng, rà soát rủi ro và tư vấn luật (Lao động, Thuế, Dân sự, Doanh nghiệp) tại Việt Nam. Trả lời ngắn gọn, chính xác, có cấu trúc markdown đẹp mắt. Nếu được yêu cầu chấm điểm, hãy đưa ra thang điểm 100 và lý do.";

      if (currentFile) {
        systemInstruction += `\n\nCONTEXT DOCUMENT:\nFilename: ${currentFile.name}\nContent:\n${currentFile.content}\n\nNếu người dùng hỏi về 'tài liệu này' hoặc 'hợp đồng này', hãy dùng nội dung trên để trả lời.`;
      }

      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: finalPrompt,
        config: {
          systemInstruction: systemInstruction,
        }
      });

      setMessages(prev => [...prev, { role: "assistant", content: response.text || "Không có phản hồi." }]);

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: "assistant", content: "Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu của bạn.", isError: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app-container">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        
        * { box-sizing: border-box; }
        
        body {
          margin: 0;
          font-family: 'Inter', sans-serif;
          background-color: #FFFFFF;
          color: #1F1F1F;
        }

        .app-container {
          display: flex;
          flex-direction: column;
          height: 100vh;
          max-width: 800px;
          margin: 0 auto;
          position: relative;
        }

        /* Welcome Screen */
        .welcome-screen {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 20px;
          animation: fadeIn 0.5s ease;
        }
        
        .welcome-title {
          font-size: 2.5rem;
          font-weight: 700;
          margin-bottom: 10px;
          background: linear-gradient(45deg, #4285F4, #DB4437, #F4B400, #0F9D58);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        
        .welcome-subtitle {
          font-size: 1.1rem;
          color: #5F6368;
          margin-bottom: 40px;
        }

        .suggestion-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
          width: 100%;
          max-width: 700px;
        }

        .suggestion-card {
          background: #fff;
          border: 1px solid #E0E0E0;
          border-radius: 12px;
          padding: 20px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
        }

        .suggestion-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          border-color: #4285F4;
        }

        /* Chat Area */
        .chat-area {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
          padding-bottom: 100px; /* Space for input */
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .message {
          display: flex;
          gap: 15px;
          max-width: 100%;
          line-height: 1.5;
          animation: slideIn 0.3s ease;
        }

        .message.user {
          flex-direction: row-reverse;
        }

        .avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          font-size: 1.2rem;
        }

        .avatar.assistant {
          background-color: #E8F0FE;
          color: #4285F4;
        }

        .avatar.user {
          background-color: #F1F3F4;
          color: #5F6368;
        }

        .message-content {
          padding: 12px 16px;
          border-radius: 18px;
          background-color: #F8F9FA;
          max-width: 80%;
          white-space: pre-wrap;
        }

        .message.user .message-content {
          background-color: #E8F0FE;
          color: #1F1F1F;
        }

        .message.error .message-content {
          background-color: #FEF7F7;
          color: #D93025;
          border: 1px solid #FAD2CF;
        }

        /* Input Area */
        .input-container {
          position: fixed;
          bottom: 0;
          left: 50%;
          transform: translateX(-50%);
          width: 100%;
          max-width: 800px;
          padding: 20px;
          background: linear-gradient(to top, #FFFFFF 80%, transparent);
          z-index: 100;
        }

        .input-box {
          display: flex;
          align-items: center;
          background-color: #F0F4F9;
          border-radius: 28px;
          padding: 5px 5px 5px 20px;
          border: 1px solid transparent;
          transition: all 0.3s ease;
        }

        .input-box:focus-within {
          background-color: #fff;
          border-color: #4285F4;
          box-shadow: 0 2px 8px rgba(66,133,244,0.15);
        }

        .input-field {
          flex: 1;
          border: none;
          background: transparent;
          padding: 10px;
          font-size: 1rem;
          font-family: inherit;
          outline: none;
          resize: none;
          max-height: 120px;
        }

        .send-btn {
          background: transparent;
          border: none;
          color: #4285F4;
          padding: 10px;
          cursor: pointer;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.2s;
        }

        .send-btn:hover {
          background-color: #E8F0FE;
        }

        .send-btn:disabled {
          color: #DADCE0;
          cursor: not-allowed;
        }

        /* Floating Action Button */
        .fab-container {
          position: absolute;
          bottom: 85px; /* Above input */
          left: 20px;
          z-index: 1000;
        }

        .fab-main {
          width: 50px;
          height: 50px;
          border-radius: 50%;
          background: #F0F4F9;
          border: none;
          color: #1F1F1F;
          box-shadow: 0 2px 6px rgba(0,0,0,0.2);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
        }

        .fab-main:hover {
          background-color: #E2E6EA;
          transform: scale(1.1);
        }

        .fab-menu {
          position: absolute;
          bottom: 60px;
          left: 0;
          background: white;
          border-radius: 12px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          padding: 10px;
          width: 200px;
          display: flex;
          flex-direction: column;
          gap: 5px;
          animation: popUp 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .menu-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px;
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.9rem;
          color: #333;
          background: none;
          border: none;
          text-align: left;
          width: 100%;
        }

        .menu-item:hover {
          background-color: #F1F3F4;
        }

        .menu-item.danger {
          color: #D93025;
        }

        .file-badge {
          position: absolute;
          bottom: 85px;
          left: 80px;
          background: #E8F0FE;
          color: #1967D2;
          padding: 8px 12px;
          border-radius: 16px;
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.05);
          animation: slideRight 0.3s ease;
        }

        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popUp { from { opacity: 0; transform: scale(0.8) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        @keyframes slideRight { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
      `}</style>

      {messages.length === 0 && (
        <div className="welcome-screen">
          <div className="welcome-title">AI Legal Assistant</div>
          <div className="welcome-subtitle">Trợ lý pháp lý thông minh cho doanh nghiệp</div>
          
          <div className="suggestion-grid">
            <button className="suggestion-card" onClick={() => sendMessage("Soạn thảo hợp đồng lao động cho nhân viên kinh doanh")}>
              <span style={{ fontSize: '2rem' }}>📝</span>
              <strong>Soạn HĐ Lao động</strong>
              <span style={{ fontSize: '0.8rem', color: '#666' }}>Tạo hợp đồng chuẩn chỉnh</span>
            </button>
            
            <button className="suggestion-card" onClick={() => sendMessage("Phân tích rủi ro cho hợp đồng mẫu")}>
              <span style={{ fontSize: '2rem' }}>🛡️</span>
              <strong>Chấm điểm Hợp đồng</strong>
              <span style={{ fontSize: '0.8rem', color: '#666' }}>Tìm rủi ro & gợi ý sửa đổi</span>
            </button>
            
            <button className="suggestion-card" onClick={() => sendMessage("Quy định mới về thuế TNDN 2025 là gì?")}>
              <span style={{ fontSize: '2rem' }}>⚖️</span>
              <strong>Hỏi Luật Thuế</strong>
              <span style={{ fontSize: '0.8rem', color: '#666' }}>Cập nhật quy định mới nhất</span>
            </button>
          </div>
        </div>
      )}

      <div className="chat-area">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
            <div className={`avatar ${msg.role}`}>
              {msg.role === 'assistant' ? <BotIcon /> : '👤'}
            </div>
            <div className="message-content">
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
             <div className="avatar assistant"><BotIcon /></div>
             <div className="message-content">
               <span style={{ display: 'inline-block', animation: 'pulse 1s infinite' }}>⏳ AI đang xử lý...</span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* File Badge Indicator */}
      {currentFile && (
        <div className="file-badge">
          <span>📄 {currentFile.name}</span>
          <button 
            onClick={() => setCurrentFile(null)} 
            style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#1967D2', padding: 0 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Floating Upload Button */}
      <div className="fab-container">
        <button className="fab-main" onClick={() => setShowUploadMenu(!showUploadMenu)}>
          <PlusIcon />
        </button>

        {showUploadMenu && (
          <div className="fab-menu">
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              accept=".txt,.md,.csv,.json" // Limiting to text-readable types for client-side demo
              onChange={handleFileChange}
            />
            <button className="menu-item" onClick={() => fileInputRef.current?.click()}>
              <UploadIcon /> Tải lên tài liệu (.txt)
            </button>
            <div style={{ height: '1px', background: '#EEE', margin: '5px 0' }}></div>
            <button className="menu-item danger" onClick={clearSession}>
              <TrashIcon /> Xóa hội thoại
            </button>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="input-container">
        <div className="input-box">
          <input
            className="input-field"
            placeholder={currentFile ? `Đang hỏi về: ${currentFile.name}...` : "Nhập câu hỏi pháp lý..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isLoading}
          />
          <button className="send-btn" onClick={() => sendMessage()} disabled={!input.trim() || isLoading}>
            <SendIcon />
          </button>
        </div>
      </div>

    </div>
  );
}

const root = createRoot(document.getElementById("app")!);
root.render(<App />);
