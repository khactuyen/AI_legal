import React, { useState, useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";

// --- Types ---
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
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

const ArrowLeftIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="19" y1="12" x2="5" y2="12"></line>
    <polyline points="12 19 5 12 12 5"></polyline>
  </svg>
);

const NewChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
  </svg>
);

const BellIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
  </svg>
);

const UserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
    <circle cx="12" cy="7" r="4"></circle>
  </svg>
);

const FileTextIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1967D2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
  </svg>
);

const ShieldAlertIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1967D2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
  </svg>
);

const BriefcaseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1967D2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
  </svg>
);

const ThemeToggleIcon = ({ theme }: { theme: "light" | "dark" }) => {
  if (theme === "light") {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
      </svg>
    );
  }
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"></circle>
      <line x1="12" y1="1" x2="12" y2="3"></line>
      <line x1="12" y1="21" x2="12" y2="23"></line>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
      <line x1="1" y1="12" x2="3" y2="12"></line>
      <line x1="21" y1="12" x2="23" y2="12"></line>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
    </svg>
  );
};

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
                <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700" }}>Thẻ Điểm Rủi Ro</h3>
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
  } catch (e) { }

  if (remainingText.startsWith("*") && remainingText.endsWith("*") && remainingText.includes("Đang")) {
    return <em style={{ color: "var(--text-muted)" }}>{remainingText.slice(1, -1).trim()}</em>;
  }

  // Helper to render inline formatting within a line
  const renderInline = (content: string, keyPrefix: string) => {
    // Strip fake links — only allow /download-template/ paths
    const parts = content.split(/(\*\*.*?\*\*|\*.*?\*|\[.*?\]\(.*?\))/g);
    return parts.map((part, partIdx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={`${keyPrefix}-${partIdx}`}>{part.slice(2, -2)}</strong>;
      } else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return <em key={`${keyPrefix}-${partIdx}`}>{part.slice(1, -1)}</em>;
      } else if (part.startsWith("[") && part.includes("](")) {
        const match = part.match(/\[(.*?)\]\((.*?)\)/);
        if (match) {
          const url = match[2];
          // Only render real internal template download links — block all external fake links
          if (url.startsWith('/download-template/')) {
            const fullUrl = `${API_BASE_URL}${url}?t=${Date.now()}`;
            return (
              <a key={`${keyPrefix}-${partIdx}`} href={fullUrl} target="_blank" rel="noopener noreferrer"
                style={{ color: "var(--primary)", textDecoration: "underline", fontWeight: "600" }}>
                {match[1]}
              </a>
            );
          }
          // Suppress all other links (fake/hallucinated) — just show the label text
          return <span key={`${keyPrefix}-${partIdx}`} style={{ fontWeight: "500" }}>{match[1]}</span>;
        }
      }
      return part;
    });
  };

  const lines = remainingText.split("\n");
  const renderedLines: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // H3 heading: ### or ####
    if (trimmed.startsWith("####")) {
      const headingText = trimmed.replace(/^#{3,}\s*/, "");
      renderedLines.push(
        <div key={i} style={{ fontSize: "0.9rem", fontWeight: "700", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", margin: "18px 0 6px" }}>
          {headingText}
        </div>
      );
    } else if (trimmed.startsWith("###")) {
      const headingText = trimmed.replace(/^#{1,3}\s*/, "");
      renderedLines.push(
        <div key={i} style={{ fontSize: "1.05rem", fontWeight: "700", color: "var(--primary)", margin: "20px 0 8px", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
          {renderInline(headingText, `h-${i}`)}
        </div>
      );
    } else if (trimmed.startsWith("## ")) {
      const headingText = trimmed.replace(/^#{1,2}\s*/, "");
      renderedLines.push(
        <div key={i} style={{ fontSize: "1.15rem", fontWeight: "800", color: "var(--text-main)", margin: "22px 0 8px" }}>
          {renderInline(headingText, `h2-${i}`)}
        </div>
      );
    // Blockquote: lines starting with >
    } else if (trimmed.startsWith(">")) {
      const quoteText = trimmed.replace(/^>\s*/, "");
      renderedLines.push(
        <div key={i} style={{ borderLeft: "3px solid var(--primary-border)", paddingLeft: "12px", margin: "6px 0", color: "var(--text-muted)", fontStyle: "italic", fontSize: "0.92rem" }}>
          {renderInline(quoteText, `bq-${i}`)}
        </div>
      );
    // Horizontal rule
    } else if (trimmed === "---" || trimmed === "___") {
      renderedLines.push(
        <hr key={i} style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "16px 0" }} />
      );
    // Numbered list
    } else if (/^\d+\.\s/.test(trimmed)) {
      const listText = trimmed.replace(/^\d+\.\s*/, "");
      renderedLines.push(
        <div key={i} style={{ display: "flex", gap: "8px", margin: "3px 0", paddingLeft: "4px" }}>
          <span style={{ color: "var(--primary)", fontWeight: "700", minWidth: "20px" }}>
            {trimmed.match(/^(\d+)\./)?.[1]}.
          </span>
          <span>{renderInline(listText, `ol-${i}`)}</span>
        </div>
      );
    // Bullet list
    } else if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      const bulletText = trimmed.replace(/^[*\-]\s+/, "");
      renderedLines.push(
        <div key={i} style={{ display: "flex", gap: "8px", margin: "3px 0", paddingLeft: "4px" }}>
          <span style={{ color: "var(--primary)", fontWeight: "900", minWidth: "14px" }}>•</span>
          <span>{renderInline(bulletText, `ul-${i}`)}</span>
        </div>
      );
    // Empty line
    } else if (trimmed === "") {
      renderedLines.push(<div key={i} style={{ height: "8px" }} />);
    // Normal paragraph
    } else {
      renderedLines.push(
        <div key={i} style={{ margin: "3px 0", lineHeight: "1.7" }}>
          {renderInline(line, `p-${i}`)}
        </div>
      );
    }
    i++;
  }

  return (
    <>
      {jsonNode}
      <div style={{ fontSize: "0.95rem" }}>{renderedLines}</div>
    </>
  );
};

const TEMPLATES_LIST = [
  { id: "Hop_dong_lao_dong.docx", name: "Hợp đồng lao động", desc: "Mẫu hợp đồng lao động chuẩn quy định quyền lợi và nghĩa vụ của người lao động và người sử dụng lao động.", category: "Nhân sự" },
  { id: "Hop_dong_dich_vu.docx", name: "Hợp đồng dịch vụ", desc: "Mẫu hợp đồng cung cấp dịch vụ giữa hai doanh nghiệp hoặc cá nhân và tổ chức.", category: "Thương mại" },
  { id: "Hop_dong_thue_nha.docx", name: "Hợp đồng thuê nhà", desc: "Mẫu hợp đồng thuê nhà ở hoặc văn phòng làm việc với đầy đủ điều khoản bảo vệ bên thuê và cho thuê.", category: "Dân sự" },
  { id: "Hop_dong_mua_ban_hang_hoa.docx", name: "Hợp đồng mua bán hàng hóa", desc: "Mẫu hợp đồng mua bán hàng hóa thương mại chuẩn mực theo Luật Thương mại.", category: "Thương mại" },
  { id: "Hop_dong_vay_tien.docx", name: "Hợp đồng vay tiền", desc: "Mẫu hợp đồng vay tài sản, tiền mặt cá nhân hoặc doanh nghiệp có kèm lãi suất thỏa thuận.", category: "Tài chính" },
  { id: "Hop_dong_dai_ly.docx", name: "Hợp đồng đại lý", desc: "Hợp đồng giao đại lý mua bán hàng hóa, đại lý độc quyền phân phối.", category: "Thương mại" },
  { id: "Hop_dong_uy_quyen.docx", name: "Hợp đồng ủy quyền", desc: "Mẫu hợp đồng ủy quyền thực hiện các công việc pháp lý hoặc thương mại thay mặt bên ủy quyền.", category: "Dân sự" },
  { id: "Hop_dong_gia_cong.docx", name: "Hợp đồng gia công", desc: "Mẫu hợp đồng nhận gia công hàng hóa, nguyên vật liệu chuẩn xác.", category: "Sản xuất" },
  { id: "Hop_dong_hop_tac_kinh_doanh_BCC.docx", name: "Hợp đồng hợp tác kinh doanh (BCC)", desc: "Mẫu hợp đồng hợp tác kinh doanh phân chia lợi nhuận mà không thành lập pháp nhân mới.", category: "Đầu tư" },
  { id: "Hop_dong_lien_ket.docx", name: "Hợp đồng liên kết", desc: "Mẫu hợp đồng liên kết đào tạo hoặc liên kết kinh doanh giữa hai đơn vị.", category: "Đầu tư" },
  { id: "Hop_dong_tin_dung.docx", name: "Hợp đồng tín dụng", desc: "Mẫu hợp đồng cấp hạn mức tín dụng hoặc cho vay của các tổ chức tài chính.", category: "Tài chính" },
  { id: "Hop_dong_bao_lanh.docx", name: "Hợp đồng bảo lãnh", desc: "Mẫu hợp đồng bảo lãnh thực hiện nghĩa vụ thanh toán hoặc nghĩa vụ hợp đồng của bên thứ ba.", category: "Tài chính" },
  { id: "Hop_dong_the_chap.docx", name: "Hợp đồng thế chấp", desc: "Mẫu hợp đồng thế chấp tài sản là bất động sản hoặc động sản đăng ký giao dịch bảo đảm.", category: "Tài chính" },
  { id: "Hop_dong_cam_co.docx", name: "Hợp đồng cầm cố", desc: "Mẫu hợp đồng cầm cố tài sản bảo đảm nghĩa vụ nợ.", category: "Tài chính" },
  { id: "Hop_dong_chuyen_giao_cong_nghe.docx", name: "Hợp đồng chuyển giao công nghệ", desc: "Mẫu hợp đồng chuyển giao quyền sở hữu hoặc quyền sử dụng công nghệ sản xuất.", category: "Sở hữu trí tuệ" },
  { id: "Hop_dong_nhuong_quyen_thuong_mai.docx", name: "Hợp đồng nhượng quyền", desc: "Mẫu hợp đồng nhượng quyền thương mại (Franchise) thương hiệu và mô hình kinh doanh.", category: "Thương mại" },
  { id: "Hop_dong_so_huu_tri_tue.docx", name: "Hợp đồng sở hữu trí tuệ", desc: "Mẫu hợp đồng chuyển nhượng hoặc chuyển quyền sử dụng nhãn hiệu, bản quyền tác giả.", category: "Sở hữu trí tuệ" }
];

// --- Main Component ---
function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Đang phân tích câu hỏi...");
  const [currentFile, setCurrentFile] = useState<FileData | null>(null);
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [isDeepMode, setIsDeepMode] = useState(false);
  const [activeView, setActiveView] = useState<"chat" | "templates">("chat");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("Tất cả");

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
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const toggleTheme = () => setTheme(prev => prev === "light" ? "dark" : "light");

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
        const res = await fetch(`${API_BASE_URL}/notifications`, {
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
      const res = await fetch(`${API_BASE_URL}/sessions?client_id=${clientId}`, {
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

      const res = await fetch(`${API_BASE_URL}/sessions/${sid}?client_id=${clientId}`, {
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
      const response = await fetch(`${API_BASE_URL}/sessions/${sid}?client_id=${clientId}`, {
        method: "DELETE",
        headers: { "X-API-Key": getApiKey() }
      });
      if (!response.ok) {
        console.error("Failed to delete session");
        return;
      }
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

      const response = await fetch(`${API_BASE_URL}/analyze-contract`, {
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
                // Do not update content to keep bubble loadingText active
              } else if (data.type === "content") {
                fullContent += data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: fullContent };
                  return newArr;
                });
              } else if (data.type === "replace_content") {
                fullContent = data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: fullContent };
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
          newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: "Lỗi kết nối tới máy chủ AI.", isError: true };
          return newArr;
        }
        return [...prev, { role: "assistant", content: "Lỗi kết nối tới máy chủ AI.", isError: true }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (textOverride?: string) => {
    if (isLoading) return;
    const userText = textOverride || input;
    if (!userText.trim()) return;

    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userText }]);
    setIsLoading(true);
    setLoadingText("Đang phân tích câu hỏi...");
    
    const loadingTimer = setTimeout(() => {
      setLoadingText("Đang chuẩn bị câu trả lời...");
    }, 1500);

    try {
      let finalMessage = userText;
      if (currentFile && !userText.includes(currentFile.name)) {
        finalMessage = `[Về file ${currentFile.name}] ${userText}`;
      }

      const endpoint = isDeepMode ? `${API_BASE_URL}/chat/deep` : `${API_BASE_URL}/chat`;
      const response = await fetch(endpoint, {
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
                // Do not update content to keep bubble loadingText active
              } else if (data.type === "content") {
                fullContent += data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: fullContent };
                  return newArr;
                });
              } else if (data.type === "replace_content") {
                fullContent = data.text;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: fullContent };
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
          newArr[newArr.length - 1] = { ...newArr[newArr.length - 1], content: "Xin lỗi, máy chủ AI đang gặp sự cố.", isError: true };
          return newArr;
        }
        return [...prev, { role: "assistant", content: "Xin lỗi, máy chủ AI đang gặp sự cố.", isError: true }];
      });
    } finally {
      clearTimeout(loadingTimer);
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
    <div className={`layout ${theme}`}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        
        * { box-sizing: border-box; }
        
        body {
          margin: 0;
          font-family: 'Inter', sans-serif;
          background-color: var(--bg-app);
          color: var(--text-main);
          overflow: hidden;
        }

        .layout.dark {
          --bg-app: #0C0C0F;
          --bg-sidebar: #111115;
          --bg-card: #17171C;
          --border-color: #26262E;
          --text-main: #EDEDF0;
          --text-muted: #7E7E8C;
          --text-opposite: #0C0C0F;
          --bg-opposite: #EDEDF0;
          --primary: #C9A84C;
          --primary-hover: #E2C06A;
          --primary-light: rgba(201, 168, 76, 0.12);
          --primary-border: rgba(201, 168, 76, 0.25);
          --chat-user-bg: #19191F;
          --chat-bot-bg: #141418;
          --chat-input-bg: #16161B;
          --accent-red-hover: #1F1F28;
          --shadow-color: rgba(0,0,0,0.55);
          --active-category-bg: #C9A84C;
          --active-category-text: #0C0C0F;
        }

        .layout.light {
          --bg-app: #F4F6FB;
          --bg-sidebar: #FFFFFF;
          --bg-card: #EAEFF8;
          --border-color: #D3DCF0;
          --text-main: #0E1829;
          --text-muted: #5B6E8E;
          --text-opposite: #FFFFFF;
          --bg-opposite: #0E1829;
          --primary: #9A7A2A;
          --primary-hover: #7A5E1A;
          --primary-light: rgba(154, 122, 42, 0.09);
          --primary-border: rgba(154, 122, 42, 0.18);
          --chat-user-bg: #EBF0FA;
          --chat-bot-bg: #FFFFFF;
          --chat-input-bg: #FFFFFF;
          --accent-red-hover: #E8EEFA;
          --shadow-color: rgba(14,24,41,0.07);
          --active-category-bg: #9A7A2A;
          --active-category-text: #FFFFFF;
        }

        .layout {
          display: flex;
          height: 100vh;
          width: 100vw;
          background-color: var(--bg-app);
          color: var(--text-main);
        }

        /* Sidebar Styling */
        .sidebar {
          width: 260px;
          background-color: var(--bg-sidebar);
          border-right: 1px solid var(--border-color);
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
          justify-content: center;
          gap: 10px;
          width: 100%;
          padding: 12px;
          background: var(--bg-sidebar);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          cursor: pointer;
          font-weight: 500;
          color: var(--text-main);
          transition: all 0.2s;
        }

        .new-chat-btn:hover {
          background: var(--primary-light);
          border-color: var(--primary);
          color: var(--primary);
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
          color: var(--text-main);
          font-size: 0.9rem;
          background: transparent;
          border: none;
          text-align: left;
          transition: background 0.2s;
        }

        .session-item:hover, .session-item.active {
          background: var(--primary-light);
          color: var(--primary);
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
          color: var(--text-muted);
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
          color: var(--primary);
          background: var(--accent-red-hover);
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
          background-color: var(--bg-app);
        }

        .top-nav {
          height: 60px;
          display: flex;
          align-items: center;
          padding: 0 15px;
          border-bottom: 1px solid var(--border-color);
          background-color: var(--bg-app);
        }

        .menu-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 8px;
          display: none;
          color: var(--text-muted);
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
          background: linear-gradient(45deg, var(--primary), var(--primary-hover), #EF4444);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        
        .welcome-subtitle {
          font-size: 1.1rem;
          color: var(--text-muted);
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
          background: var(--bg-sidebar);
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 20px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
          color: var(--text-main);
        }

        .suggestion-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 4px 12px var(--shadow-color);
          border-color: var(--primary);
          background-color: var(--primary-light);
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
          background-color: var(--primary-light);
          color: var(--primary);
        }

        .avatar.user {
          background-color: var(--border-color);
          color: var(--text-muted);
        }

        .message-content {
          padding: 12px 16px;
          border-radius: 18px;
          background-color: var(--chat-bot-bg);
          color: var(--text-main);
          max-width: 80%;
          white-space: pre-wrap;
          border: 1px solid var(--border-color);
        }

        .message.user .message-content {
          background-color: var(--chat-user-bg);
          color: var(--text-main);
          border-color: transparent;
        }

        .message.error .message-content {
          background-color: var(--accent-red-hover);
          color: var(--primary);
          border: 1px solid var(--primary-border);
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
          background: linear-gradient(to top, var(--bg-app) 90%, transparent);
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
          background-color: var(--chat-input-bg);
          border-radius: 28px;
          padding: 5px 5px 5px 20px;
          border: 1px solid var(--border-color);
          transition: all 0.3s ease;
          width: 100%;
        }

        .input-box:focus-within {
          background-color: var(--chat-input-bg);
          border-color: var(--primary);
          box-shadow: 0 2px 8px var(--primary-border);
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
          color: var(--text-main);
        }

        .send-btn {
          background: transparent;
          border: none;
          color: var(--primary);
          padding: 10px;
          cursor: pointer;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.2s;
        }

        .send-btn:hover {
          background-color: var(--primary-light);
        }

        .send-btn:disabled {
          color: var(--text-muted);
          cursor: not-allowed;
          opacity: 0.5;
        }

        /* Disclaimer */
        .disclaimer {
            font-size: 0.75rem;
            color: var(--text-muted);
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
          background: var(--chat-input-bg);
          border: 1px solid var(--border-color);
          color: var(--text-main);
          box-shadow: 0 2px 6px var(--shadow-color);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
        }

        .fab-main:hover {
          background-color: var(--primary-light);
          border-color: var(--primary);
          color: var(--primary);
          transform: scale(1.1);
        }

        .fab-menu {
          position: absolute;
          bottom: 55px;
          left: 0;
          background: var(--bg-sidebar);
          border: 1px solid var(--border-color);
          border-radius: 12px;
          box-shadow: 0 4px 12px var(--shadow-color);
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
          color: var(--text-main);
          background: none;
          border: none;
          text-align: left;
          width: 100%;
        }

        .menu-item:hover {
          background-color: var(--primary-light);
          color: var(--primary);
        }

        .file-badge {
          position: absolute;
          bottom: 75px;
          left: 55px;
          background: var(--primary-light);
          color: var(--primary);
          padding: 6px 12px;
          border-radius: 16px;
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 2px 4px var(--shadow-color);
          animation: slideRight 0.3s ease;
        }

        /* Loader Dots CSS */
        .loader-dots {
          display: flex;
          gap: 4px;
        }
        .dot {
          width: 6px;
          height: 6px;
          background-color: var(--primary);
          border-radius: 50%;
          animation: bounce 1.4s infinite ease-in-out both;
        }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1.0); }
        }

        /* Mobile Adjustments */
        @media (max-width: 768px) {
          .sidebar {
            position: fixed;
            height: 100%;
            left: 0;
            transform: ${isSidebarOpen ? 'translateX(0)' : 'translateX(-100%)'};
            box-shadow: ${isSidebarOpen ? '2px 0 10px rgba(0,0,0,0.3)' : 'none'};
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
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>

      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button className="new-chat-btn" onClick={() => { setActiveView("chat"); createNewChat(); }}>
            <NewChatIcon /> Chat mới
          </button>
          <button 
            className="new-chat-btn" 
            style={{ 
              backgroundColor: activeView === "templates" ? "var(--primary-light)" : "var(--bg-sidebar)", 
              borderColor: activeView === "templates" ? "var(--primary)" : "var(--border-color)",
              color: activeView === "templates" ? "var(--primary)" : "var(--text-main)" 
            }}
            onClick={() => { setActiveView("templates"); if (window.innerWidth <= 768) setIsSidebarOpen(false); }}
          >
            Hợp đồng & Biểu mẫu
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
          {activeView === "templates" ? (
            <button 
              className="menu-btn" 
              onClick={() => setActiveView("chat")} 
              title="Quay lại Trò chuyện"
              style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-main)" }}
            >
              <ArrowLeftIcon />
            </button>
          ) : (
            <button className="menu-btn" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
              <MenuIcon />
            </button>
          )}
          <span style={{ fontWeight: 600, marginLeft: "10px", color: "var(--text-main)" }}>
            {activeView === "chat" ? "Legal AI Assistant" : "Cổng Biểu Mẫu"}
          </span>
          <div style={{ marginLeft: "auto", position: "relative", display: "flex", alignItems: "center", gap: "15px" }}>
            {activeView === "chat" && (
              <button 
                onClick={createNewChat} 
                title="Bắt đầu cuộc trò chuyện mới"
                style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}
              >
                <PlusIcon />
              </button>
            )}
            <button 
              onClick={toggleTheme} 
              style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}
            >
              <ThemeToggleIcon theme={theme} />
            </button>
            <button onClick={() => setShowNotifications(!showNotifications)} style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", position: "relative", color: "var(--text-muted)" }}>
              <BellIcon />
              {notifications.length > 0 && <span style={{ position: "absolute", top: -5, right: -5, background: "red", color: "white", borderRadius: "50%", padding: "2px 6px", fontSize: "0.7rem", fontWeight: "bold" }}>{notifications.length}</span>}
            </button>
            {showNotifications && (
              <div style={{ position: "absolute", top: 30, right: 0, width: 320, background: "var(--bg-sidebar)", border: "1px solid var(--border-color)", borderRadius: "8px", boxShadow: "0 4px 6px var(--shadow-color)", zIndex: 1000, padding: "10px", maxHeight: "400px", overflowY: "auto" }}>
                <h4 style={{ margin: "0 0 10px 0", borderBottom: "1px solid var(--border-color)", paddingBottom: "5px", color: "var(--text-main)" }}>Thông báo hệ thống (Scheduled Agents)</h4>
                {notifications.length === 0 ? <p style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>Không có thông báo nào</p> : notifications.map(n => (
                  <div key={n.id} style={{ marginBottom: "10px", paddingBottom: "10px", borderBottom: "1px solid var(--border-color)", textAlign: "left" }}>
                    <strong style={{ fontSize: "0.9rem", color: "var(--primary)" }}>{n.title}</strong>
                    <p style={{ margin: "5px 0 0 0", fontSize: "0.85rem", color: "var(--text-main)", lineHeight: 1.4 }}>{n.message}</p>
                    <small style={{ color: "var(--text-muted)", display: "block", marginTop: "4px" }}>{new Date(n.timestamp).toLocaleString()}</small>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {activeView === "chat" ? (
          <>
            {messages.length === 0 && (
              <div className="welcome-screen" style={{ animation: "fadeIn 0.6s ease", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "30px 20px" }}>
                <style>{`
                  @keyframes logoFloat {
                    0%, 100% { transform: translateY(0px); }
                    50% { transform: translateY(-8px); }
                  }
                  @keyframes ringPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(201,168,76,0.35), 0 16px 48px rgba(0,0,0,0.4); }
                    50% { box-shadow: 0 0 0 14px rgba(201,168,76,0), 0 16px 48px rgba(0,0,0,0.4); }
                  }
                  .feature-card {
                    background: var(--bg-card);
                    border: 1px solid var(--border-color);
                    border-radius: 16px;
                    padding: 24px;
                    cursor: pointer;
                    position: relative;
                    overflow: hidden;
                    transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
                  }
                  .feature-card::before {
                    content: '';
                    position: absolute;
                    inset: 0;
                    border-radius: 16px;
                    background: linear-gradient(135deg, rgba(201,168,76,0.06) 0%, transparent 60%);
                    opacity: 0;
                    transition: opacity 0.3s ease;
                  }
                  .feature-card:hover {
                    transform: translateY(-6px);
                    border-color: var(--primary);
                    box-shadow: 0 12px 32px var(--shadow-color), 0 0 0 1px var(--primary-border);
                  }
                  .feature-card:hover::before { opacity: 1; }
                  .feature-icon-wrap {
                    width: 48px;
                    height: 48px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 14px;
                    font-size: 22px;
                  }
                `}</style>

                {/* Logo + Brand */}
                <div style={{ animation: "logoFloat 4s ease-in-out infinite", animation: "ringPulse 3s ease-in-out infinite", marginBottom: "28px" }}>
                  <div style={{
                    width: "100px",
                    height: "100px",
                    borderRadius: "24px",
                    overflow: "hidden",
                    boxShadow: "0 0 0 2px var(--primary-border), 0 16px 48px rgba(0,0,0,0.5)",
                  }}>
                    <img src="/logo.png" alt="AI Legal Assistant Logo" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  </div>
                </div>

                <h1 style={{ fontSize: "2.2rem", fontWeight: "900", margin: "12px 0 10px", letterSpacing: "-0.5px",
                  background: "linear-gradient(135deg, var(--text-main) 40%, var(--primary) 100%)",
                  WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
                }}>AI Legal Assistant</h1>

                <p style={{ fontSize: "0.97rem", color: "var(--text-muted)", marginBottom: "40px", maxWidth: "520px", lineHeight: "1.7" }}>
                  Trợ lý pháp lý thông minh — tra cứu luật, rà soát hợp đồng và phân tích rủi ro pháp lý chuyên sâu cho doanh nghiệp SME.
                </p>

              </div>
            )}

            <div className="chat-area" onClick={() => { if (window.innerWidth <= 768) setIsSidebarOpen(false); }}>
              {messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
                  <div className={`avatar ${msg.role}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '50%', padding: 0 }}>
                    {msg.role === 'assistant'
                      ? <img src="/logo.png" alt="AI" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                      : <UserIcon />}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '100%' }}>
                    <div className="message-content">
                      {msg.role === 'assistant' && msg.content === "" ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ display: 'inline-block', animation: 'pulse 1.5s infinite', fontWeight: '500', color: 'var(--text-muted)', fontSize: '0.95rem' }}>{loadingText}</span>
                          <div className="loader-dots">
                            <div className="dot"></div>
                            <div className="dot"></div>
                            <div className="dot"></div>
                          </div>
                        </div>
                      ) : (
                        renderMessageContent(msg.content)
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area (Bottom Fixed) */}
            <div className="input-container">
              <div className="input-wrapper">

                {/* Indicators */}
                {currentFile && (
                  <div className="file-badge">
                    <span>{currentFile.name}</span>
                    <button onClick={() => setCurrentFile(null)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--primary)', padding: 0 }}>✕</button>
                  </div>
                )}

                <div className="input-box" style={{ position: "relative", paddingLeft: "50px" }}>
                  <div className="fab-container" style={{ position: "absolute", bottom: "6px", left: "6px", zIndex: 10 }}>
                    <button className="fab-main" onClick={() => setShowUploadMenu(!showUploadMenu)} style={{ width: '36px', height: '36px', background: 'transparent', border: 'none', boxShadow: 'none', color: 'var(--text-muted)' }}>
                      <PlusIcon />
                    </button>
                    {showUploadMenu && (
                      <div className="fab-menu" style={{ bottom: '45px', left: '0' }}>
                        <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".txt,.md,.csv,.json,.docx,.doc,.pdf" onChange={handleFileChange} />
                        <button className="menu-item" onClick={() => fileInputRef.current?.click()}><UploadIcon /> Tải lên tài liệu</button>
                      </div>
                    )}
                  </div>

                  <input
                    className="input-field"
                    placeholder={currentFile ? `Đang hỏi về: ${currentFile.name}...` : "Nhập câu hỏi pháp lý..."}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyPress}
                    style={{ paddingLeft: '5px' }}
                  />
                  <button className="send-btn" onClick={() => sendMessage()} disabled={!input.trim() || isLoading}>
                    <SendIcon />
                  </button>
                </div>

                {/* Toggle Button cho Deep Mode ở dưới thanh input, CĂN GIỮA */}
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: '12px', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', fontWeight: '500' }}>
                    <span style={{ marginRight: '8px', color: 'var(--text-main)' }}>Mode:</span>
                    <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={isDeepMode}
                        onChange={() => setIsDeepMode(!isDeepMode)}
                        style={{ display: 'none' }}
                      />
                      <span style={{ 
                        marginRight: '8px', 
                        color: !isDeepMode ? 'var(--primary)' : 'var(--text-muted)',
                        transition: 'color 0.3s'
                      }}>Instant</span>
                      
                      {/* Toggle track */}
                      <div style={{ 
                        width: '36px', height: '20px', 
                        background: 'var(--chat-input-bg)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '10px', 
                        position: 'relative', 
                        display: 'flex', alignItems: 'center' 
                      }}>
                        {/* Toggle knob */}
                        <div style={{ 
                          width: '14px', height: '14px', 
                          background: 'var(--primary)', 
                          borderRadius: '50%', 
                          position: 'absolute', 
                          top: '2px', 
                          left: isDeepMode ? '18px' : '2px', 
                          transition: 'left 0.3s' 
                        }} />
                      </div>

                      <span style={{ 
                        marginLeft: '8px', 
                        color: isDeepMode ? 'var(--primary)' : 'var(--text-muted)',
                        transition: 'color 0.3s'
                      }}>Thinking</span>
                    </label>
                  </div>
                </div>

                {/* Disclaimer */}
                <div className="disclaimer">
                  AI Legal Assistant có thể mắc lỗi. Các lời khuyên chỉ mang tính chất tham khảo và không thay thế cho tư vấn từ Luật sư.
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="templates-view" style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column", gap: "20px", overflowY: "auto", paddingBottom: "40px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", borderBottom: "1px solid var(--border-color)", paddingBottom: "12px" }}>
              <button 
                onClick={() => setActiveView("chat")} 
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "var(--chat-input-bg)",
                  color: "var(--text-main)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "8px 16px",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                  fontWeight: "600",
                  transition: "all 0.2s"
                }}
              >
                <ArrowLeftIcon /> Quay lại Trò chuyện
              </button>
              <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: "700", color: "var(--text-main)" }}>Mẫu hợp đồng & Biểu mẫu</h2>
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
              <div style={{ position: "relative", flex: "1", minWidth: "250px" }}>
                <input
                  type="text"
                  placeholder="Tìm kiếm mẫu hợp đồng..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{ width: "100%", padding: "10px 15px", borderRadius: "8px", border: "1px solid var(--border-color)", backgroundColor: "var(--chat-input-bg)", color: "var(--text-main)", fontSize: "0.95rem" }}
                />
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {["Tất cả", "Thương mại", "Nhân sự", "Tài chính", "Sở hữu trí tuệ", "Dân sự", "Đầu tư", "Sản xuất"].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "16px",
                      border: "1px solid",
                      borderColor: selectedCategory === cat ? "var(--primary)" : "var(--border-color)",
                      backgroundColor: selectedCategory === cat ? "var(--primary)" : "var(--bg-sidebar)",
                      color: selectedCategory === cat ? "var(--active-category-text)" : "var(--text-main)",
                      fontSize: "0.85rem",
                      cursor: "pointer",
                      fontWeight: "500",
                      transition: "all 0.2s"
                    }}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
              {TEMPLATES_LIST.filter(t => {
                const matchesSearch = t.name.toLowerCase().includes(searchTerm.toLowerCase()) || t.desc.toLowerCase().includes(searchTerm.toLowerCase());
                const matchesCategory = selectedCategory === "Tất cả" || t.category === selectedCategory;
                return matchesSearch && matchesCategory;
              }).map((t) => (
                <div key={t.id} style={{ background: "var(--bg-sidebar)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "16px", display: "flex", flexDirection: "column", justifyContent: "space-between", height: "190px", boxShadow: "0 2px 4px var(--shadow-color)" }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span style={{ fontSize: "0.75rem", background: "var(--primary-light)", color: "var(--primary)", padding: "2px 8px", borderRadius: "10px", fontWeight: "500" }}>{t.category}</span>
                    </div>
                    <h3 style={{ margin: "0 0 6px 0", fontSize: "1.05rem", fontWeight: "600", color: "var(--text-main)" }}>{t.name}</h3>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: "1.4" }}>{t.desc}</p>
                  </div>
                  <div style={{ marginTop: "12px" }}>
                    <a
                      href={`${API_BASE_URL}/download-template/${t.id}?t=${Date.now()}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: "block", width: "100%", textAlign: "center", padding: "8px 0", fontSize: "0.85rem", background: "var(--primary)", color: "var(--active-category-text)", borderRadius: "6px", textDecoration: "none", fontWeight: "600", transition: "all 0.2s" }}
                    >
                      Tải biểu mẫu
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

const root = createRoot(document.getElementById("app")!);
root.render(<App />);
