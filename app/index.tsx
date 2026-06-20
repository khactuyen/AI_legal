import React, { useState, useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";

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

type SessionInfo = {
  session_id: string;
  title: string;
  updated_at: string;
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
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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

const MenuIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="3" y1="12" x2="21" y2="12"></line>
    <line x1="3" y1="6" x2="21" y2="6"></line>
    <line x1="3" y1="18" x2="21" y2="18"></line>
  </svg>
);

const NewChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
  </svg>
);

// Helper function
const renderMessageContent = (text: string) => {
  if (!text) return null;

  let remainingText = text;
  let jsonNode = null;
  
  try {
    const startIdx = text.indexOf("```json");
    if (startIdx !== -1) {
      const endIdx = text.indexOf("```", startIdx + 7);
      if (endIdx !== -1) {
        const jsonStr = text.substring(startIdx + 7, endIdx).trim();
        const data = JSON.parse(jsonStr);
        if (data.score !== undefined && data.risk_level) {
          const isSafe = data.score >= 80;
          const isWarning = data.score >= 50 && data.score < 80;
          const bgColor = isSafe ? "#E6F4EA" : isWarning ? "#FEF7E0" : "#FCE8E6";
          const borderColor = isSafe ? "#34A853" : isWarning ? "#FBBC04" : "#EA4335";
          const textColor = isSafe ? "#137333" : isWarning ? "#B08D00" : "#C5221F";
          
          jsonNode = (
            <div style={{ padding: "16px", margin: "16px 0", borderLeft: `5px solid ${borderColor}`, backgroundColor: bgColor, borderRadius: "10px", color: textColor, boxShadow: "0 2px 6px rgba(0,0,0,0.05)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700" }}>🛡️ Thẻ Điểm Rủi Ro</h3>
                <span style={{ fontSize: "1.6rem", fontWeight: "900" }}>{data.score}/100</span>
              </div>
              <p style={{ margin: "0 0 6px 0", fontWeight: "600" }}>Mức độ rủi ro: {data.risk_level}</p>
              <p style={{ margin: 0, fontStyle: "italic", fontSize: "0.95rem" }}>{data.risk_summary}</p>
            </div>
          );
          remainingText = text.substring(0, startIdx) + text.substring(endIdx + 3);
        }
      }
    }
  } catch (e) {}

  if (remainingText.startsWith("*⏳") && remainingText.endsWith("*")) {
    return <em style={{ color: "#5F6368" }}>⏳ {remainingText.slice(3, -1).trim()}</em>;
  }

  const lines = remainingText.split("\n");
  const renderedLines = lines.map((line, lineIdx) => {
    const isBullet = line.trim().startsWith("* ") || line.trim().startsWith("- ");
    let content = line;
    if (isBullet) content = line.trim().replace(/^[\*\-]\s+/, "");

    const parts = content.split(/(\*\*.*?\*\*|\*.*?\*|\[.*?\]\(.*?\))/g);
    const renderedLine = parts.map((part, partIdx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={partIdx}>{part.slice(2, -2)}</strong>;
      } else if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={partIdx}>{part.slice(1, -1)}</em>;
      } else if (part.startsWith("[") && part.includes("](")) {
        // Render Markdown Links (e.g. for Templates)
        const match = part.match(/\[(.*?)\]\((.*?)\)/);
        if (match) {
            return (
                <a key={partIdx} href={match[2]} target="_blank" rel="noopener noreferrer" style={{ color: "#1967D2", textDecoration: "underline", fontWeight: "500" }}>
                    📥 {match[1]}
                </a>
            );
        }
      }
      return part;
    });

    if (isBullet) {
      return (
        <li key={lineIdx} style={{ marginLeft: "20px", marginBottom: "4px", listStyleType: "disc" }}>
          {renderedLine}
        </li>
      );
    }

    return (
      <div key={lineIdx} style={{ margin: "4px 0", minHeight: "1.2em" }}>
        {renderedLine}
      </div>
    );
  });

  return (
    <>
      {jsonNode}
      {renderedLines}
    </>
  );
};

// --- Main Component ---
function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentFile, setCurrentFile] = useState<FileData | null>(null);
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  
  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  const [clientId] = useState(() => {
    let id = localStorage.getItem("legal_sme_client_id");
    if (!id) {
      id = "client_" + Math.random().toString(36).substring(2, 15);
      localStorage.setItem("legal_sme_client_id", id);
    }
    return id;
  });
  const [sessionId, setSessionId] = useState(() => "sess_" + Math.random().toString(36).substring(2, 12));
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 768);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchSessions();
    const handleResize = () => {
        if (window.innerWidth > 768) setIsSidebarOpen(true);
        else setIsSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const fetchNotifs = async () => {
      try {
        const res = await fetch(`http://localhost:8000/notifications`, {
          headers: { "X-API-Key": getApiKey() }
        });
        if (res.ok) {
          const data = await res.json();
          setNotifications(data.notifications || []);
        }
      } catch (e) {
        console.error("Lỗi tải thông báo", e);
      }
    };
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 30000);
    return () => clearInterval(interval);
  }, []);

  const getApiKey = () => {
    return import.meta.env.VITE_API_KEY || "legal-sme-secret-key-2026";
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch(`http://localhost:8000/sessions?client_id=${clientId}`, {
        headers: { "X-API-Key": getApiKey() }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error("Lỗi tải danh sách session", e);
    }
  };

  const loadSession = async (sid: string) => {
    try {
      setSessionId(sid);
      setMessages([]);
      if (window.innerWidth <= 768) setIsSidebarOpen(false);
      
      const res = await fetch(`http://localhost:8000/sessions/${sid}?client_id=${clientId}`, {
        headers: { "X-API-Key": getApiKey() }
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (e) {
      console.error("Lỗi tải tin nhắn", e);
    }
  };

  const deleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    try {
      await fetch(`http://localhost:8000/sessions/${sid}?client_id=${clientId}`, {
        method: "DELETE",
        headers: { "X-API-Key": getApiKey() }
      });
      if (sessionId === sid) createNewChat();
      fetchSessions();
    } catch (err) {
      console.error("Lỗi xóa session", err);
    }
  };

  const createNewChat = () => {
    setSessionId("sess_" + Math.random().toString(36).substring(2, 12));
    setMessages([]);
    setCurrentFile(null);
    if (window.innerWidth <= 768) setIsSidebarOpen(false);
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setCurrentFile({ name: file.name, content: "Đã tải lên" });
    setMessages(prev => [...prev, { role: "user", content: `(Tải lên file: ${file.name})` }]);
    setIsLoading(true);
    setShowUploadMenu(false);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("http://localhost:8000/analyze-contract", {
        method: "POST",
        headers: { "X-API-Key": getApiKey() },
        body: formData
      });

      if (!response.ok) throw new Error("Lỗi phân tích file");
      if (!response.body) throw new Error("Không lấy được dữ liệu luồng");

      setMessages(prev => [...prev, { role: "assistant", content: "" }]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let fullContent = "";

      while (!done) {
        const { value, done: isDone } = await reader.read();
        done = isDone;
        if (value) {
          const chunkStr = decoder.decode(value, { stream: true });
          const lines = chunkStr.split("\n").filter(l => l.trim() !== "");
          
          for (const line of lines) {
            try {
              const data = JSON.parse(line);
              if (data.type === "status") {
                if (fullContent === "") {
                  setMessages(prev => {
                    const newArr = [...prev];
                    newArr[newArr.length - 1].content = `*⏳ ${data.text}*`;
                    return newArr;
                  });
                }
              } else if (data.type === "content") {
                fullContent += data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1].content = fullContent;
                  return newArr;
                });
              }
            } catch (e) {
              console.error("Lỗi parse dòng stream:", line, e);
            }
          }
        }
      }
      fetchSessions();
    } catch (error) {
      console.error(error);
      setMessages(prev => {
        const newArr = [...prev];
        if (newArr[newArr.length - 1].role === "assistant" && newArr[newArr.length - 1].content === "") {
           newArr[newArr.length - 1].content = "Lỗi kết nối tới máy chủ AI.";
           newArr[newArr.length - 1].isError = true;
           return newArr;
        }
        return [...prev, { role: "assistant", content: "Lỗi kết nối tới máy chủ AI.", isError: true }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (textOverride?: string) => {
    const userText = textOverride || input;
    if (!userText.trim()) return;

    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userText }]);
    setIsLoading(true);

    try {
      let finalMessage = userText;
      if (currentFile && !userText.includes(currentFile.name)) {
          finalMessage = `[Về file ${currentFile.name}] ${userText}`;
      }

      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-API-Key": getApiKey()
        },
        body: JSON.stringify({ message: finalMessage, session_id: sessionId, client_id: clientId })
      });

      if (!response.ok) throw new Error("API request failed");
      if (!response.body) throw new Error("Không lấy được dữ liệu luồng");

      setMessages(prev => [...prev, { role: "assistant", content: "" }]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let fullContent = "";

      while (!done) {
        const { value, done: isDone } = await reader.read();
        done = isDone;
        if (value) {
          const chunkStr = decoder.decode(value, { stream: true });
          const lines = chunkStr.split("\n").filter(l => l.trim() !== "");
          
          for (const line of lines) {
            try {
              const data = JSON.parse(line);
              if (data.type === "status") {
                if (fullContent === "") {
                  setMessages(prev => {
                    const newArr = [...prev];
                    newArr[newArr.length - 1].content = `*⏳ ${data.text}*`;
                    return newArr;
                  });
                }
              } else if (data.type === "content") {
                fullContent += data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1].content = fullContent;
                  return newArr;
                });
              }
            } catch (e) {
              console.error("Lỗi parse dòng stream:", line, e);
            }
          }
        }
      }
      // Gọi fetchSessions để cập nhật lại Sidebar (tiêu đề mới)
      fetchSessions();

    } catch (error) {
      console.error(error);
      setMessages(prev => {
        const newArr = [...prev];
        if (newArr[newArr.length - 1].role === "assistant" && newArr[newArr.length - 1].content === "") {
           newArr[newArr.length - 1].content = "Xin lỗi, máy chủ AI đang gặp sự cố.";
           newArr[newArr.length - 1].isError = true;
           return newArr;
        }
        return [...prev, { role: "assistant", content: "Xin lỗi, máy chủ AI đang gặp sự cố.", isError: true }];
      });
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
    <div className="layout">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        
        * { box-sizing: border-box; }
        
        body {
          margin: 0;
          font-family: 'Inter', sans-serif;
          background-color: #FFFFFF;
          color: #1F1F1F;
          overflow: hidden;
        }

        .layout {
          display: flex;
          height: 100vh;
          width: 100vw;
        }

        /* Sidebar Styling */
        .sidebar {
          width: 260px;
          background-color: #F9F9F9;
          border-right: 1px solid #E5E5E5;
          display: flex;
          flex-direction: column;
          transition: transform 0.3s ease;
          z-index: 1000;
        }

        .sidebar-header {
          padding: 15px;
        }

        .new-chat-btn {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 12px;
          background: #fff;
          border: 1px solid #E5E5E5;
          border-radius: 8px;
          cursor: pointer;
          font-weight: 500;
          color: #1F1F1F;
          transition: background 0.2s;
        }

        .new-chat-btn:hover {
          background: #F0F4F9;
        }

        .session-list {
          flex: 1;
          overflow-y: auto;
          padding: 10px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .session-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px;
          border-radius: 8px;
          cursor: pointer;
          color: #333;
          font-size: 0.9rem;
          background: transparent;
          border: none;
          text-align: left;
          transition: background 0.2s;
        }

        .session-item:hover, .session-item.active {
          background: #E8F0FE;
        }

        .session-title {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          flex: 1;
        }

        .delete-btn {
          background: none;
          border: none;
          color: #9AA0A6;
          cursor: pointer;
          opacity: 0;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
        }

        .session-item:hover .delete-btn {
          opacity: 1;
        }

        .delete-btn:hover {
          color: #D93025;
          background: #FCE8E6;
        }

        /* Main App Container */
        .app-container {
          flex: 1;
          display: flex;
          flex-direction: column;
          position: relative;
          height: 100vh;
          max-width: 900px;
          margin: 0 auto;
        }

        .top-nav {
          height: 60px;
          display: flex;
          align-items: center;
          padding: 0 15px;
          border-bottom: 1px solid #E5E5E5;
        }

        .menu-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 8px;
          display: none;
          color: #5F6368;
        }

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
          padding-bottom: 150px; /* Space for input + disclaimer */
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
          left: ${isSidebarOpen && window.innerWidth > 768 ? '260px' : '0'};
          right: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 10px 20px 5px 20px;
          background: linear-gradient(to top, #FFFFFF 90%, transparent);
          z-index: 100;
          transition: left 0.3s ease;
        }

        .input-wrapper {
            width: 100%;
            max-width: 800px;
            position: relative;
        }

        .input-box {
          display: flex;
          align-items: center;
          background-color: #F0F4F9;
          border-radius: 28px;
          padding: 5px 5px 5px 20px;
          border: 1px solid transparent;
          transition: all 0.3s ease;
          width: 100%;
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

        /* Disclaimer */
        .disclaimer {
            font-size: 0.75rem;
            color: #9AA0A6;
            margin-top: 8px;
            text-align: center;
        }

        /* Floating Action Button */
        .fab-container {
          position: absolute;
          bottom: 75px; 
          left: 0;
          z-index: 1000;
        }

        .fab-main {
          width: 45px;
          height: 45px;
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
          bottom: 55px;
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

        .file-badge {
          position: absolute;
          bottom: 75px;
          left: 55px;
          background: #E8F0FE;
          color: #1967D2;
          padding: 6px 12px;
          border-radius: 16px;
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.05);
          animation: slideRight 0.3s ease;
        }

        /* Mobile Adjustments */
        @media (max-width: 768px) {
          .sidebar {
            position: fixed;
            height: 100%;
            left: 0;
            transform: ${isSidebarOpen ? 'translateX(0)' : 'translateX(-100%)'};
            box-shadow: ${isSidebarOpen ? '2px 0 10px rgba(0,0,0,0.1)' : 'none'};
          }
          .menu-btn {
            display: block;
          }
          .input-container {
             left: 0 !important;
          }
        }

        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popUp { from { opacity: 0; transform: scale(0.8) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        @keyframes slideRight { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
      `}</style>

      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
           <button className="new-chat-btn" onClick={createNewChat}>
             <NewChatIcon /> Chat mới
           </button>
        </div>
        <div className="session-list">
          {sessions.map((s) => (
            <div 
               key={s.session_id} 
               className={`session-item ${s.session_id === sessionId ? 'active' : ''}`}
               onClick={() => loadSession(s.session_id)}
            >
               <span className="session-title">{s.title || "Trò chuyện mới"}</span>
               <button className="delete-btn" onClick={(e) => deleteSession(e, s.session_id)}>
                 <TrashIcon />
               </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="app-container">
        
        {/* Mobile Header */}
        <div className="top-nav">
           <button className="menu-btn" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
             <MenuIcon />
           </button>
           <span style={{ fontWeight: 600, marginLeft: "10px", color: "#5F6368" }}>
             Legal AI Assistant
           </span>
           <div style={{ marginLeft: "auto", position: "relative" }}>
             <button onClick={() => setShowNotifications(!showNotifications)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem", position: "relative" }}>
               🔔
               {notifications.length > 0 && <span style={{ position: "absolute", top: -5, right: -5, background: "red", color: "white", borderRadius: "50%", padding: "2px 6px", fontSize: "0.7rem", fontWeight: "bold" }}>{notifications.length}</span>}
             </button>
             {showNotifications && (
               <div style={{ position: "absolute", top: 30, right: 0, width: 320, background: "white", border: "1px solid #ccc", borderRadius: "8px", boxShadow: "0 4px 6px rgba(0,0,0,0.1)", zIndex: 1000, padding: "10px", maxHeight: "400px", overflowY: "auto" }}>
                 <h4 style={{ margin: "0 0 10px 0", borderBottom: "1px solid #eee", paddingBottom: "5px" }}>Thông báo hệ thống (Scheduled Agents)</h4>
                 {notifications.length === 0 ? <p style={{ fontSize: "0.9rem", color: "#666" }}>Không có thông báo nào</p> : notifications.map(n => (
                   <div key={n.id} style={{ marginBottom: "10px", paddingBottom: "10px", borderBottom: "1px solid #eee", textAlign: "left" }}>
                     <strong style={{ fontSize: "0.9rem", color: "#D93025" }}>{n.title}</strong>
                     <p style={{ margin: "5px 0 0 0", fontSize: "0.85rem", color: "#333", lineHeight: 1.4 }}>{n.message}</p>
                     <small style={{ color: "#999", display: "block", marginTop: "4px" }}>{new Date(n.timestamp).toLocaleString()}</small>
                   </div>
                 ))}
               </div>
             )}
           </div>
        </div>

        {messages.length === 0 && (
          <div className="welcome-screen">
            <div className="welcome-title">AI Legal Assistant</div>
            <div className="welcome-subtitle">Trợ lý pháp lý thông minh cho doanh nghiệp</div>
            
            <div className="suggestion-grid">
              <button className="suggestion-card" onClick={() => sendMessage("Tôi cần xin giấy phép đăng ký kinh doanh")}>
                <span style={{ fontSize: '2rem' }}>📝</span>
                <strong>Thủ tục Đăng ký</strong>
                <span style={{ fontSize: '0.8rem', color: '#666' }}>Hướng dẫn và Biểu mẫu</span>
              </button>
              
              <button className="suggestion-card" onClick={() => sendMessage("Phân tích rủi ro cho hợp đồng mẫu này")}>
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

        <div className="chat-area" onClick={() => { if(window.innerWidth <= 768) setIsSidebarOpen(false); }}>
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
              <div className={`avatar ${msg.role}`}>
                {msg.role === 'assistant' ? <BotIcon /> : '👤'}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '100%' }}>
                <div className="message-content">
                  {renderMessageContent(msg.content)}
                </div>
              </div>
            </div>
          ))}
          {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="message assistant">
               <div className="avatar assistant"><BotIcon /></div>
               <div className="message-content">
                 <span style={{ display: 'inline-block', animation: 'pulse 1s infinite' }}>⏳ AI đang xử lý...</span>
               </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area (Bottom Fixed) */}
        <div className="input-container">
           <div className="input-wrapper">
             
             {/* Indicators */}
             {currentFile && (
                <div className="file-badge">
                <span>📄 {currentFile.name}</span>
                <button onClick={() => setCurrentFile(null)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#1967D2', padding: 0 }}>✕</button>
                </div>
             )}

             <div className="fab-container">
                <button className="fab-main" onClick={() => setShowUploadMenu(!showUploadMenu)}>
                    <PlusIcon />
                </button>
                {showUploadMenu && (
                    <div className="fab-menu">
                        <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".txt,.md,.csv,.json,.docx,.doc,.pdf" onChange={handleFileChange} />
                        <button className="menu-item" onClick={() => fileInputRef.current?.click()}><UploadIcon /> Tải lên tài liệu</button>
                    </div>
                )}
             </div>

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

             {/* Disclaimer */}
             <div className="disclaimer">
                AI Legal Assistant có thể mắc lỗi. Các lời khuyên chỉ mang tính chất tham khảo và không thay thế cho tư vấn từ Luật sư.
             </div>
           </div>
        </div>

      </div>
    </div>
  );
}

const root = createRoot(document.getElementById("app")!);
root.render(<App />);
