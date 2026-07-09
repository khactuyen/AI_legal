import re
import logging
from typing import List, Dict, Any
from pyvi import ViTokenizer, ViPosTagger

logger = logging.getLogger("chatbot.utils.text_processing")

def redact_sensitive_data(text: str) -> str:
    text = re.sub(r'\b(0\d{9,10})\b', "[SĐT ĐÃ CHE]", text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "[EMAIL ĐÃ CHE]", text)
    text = re.sub(r'\b(\d{9}|\d{12})\b', "[ID ĐÃ CHE]", text)
    return text

def correct_teencode_local(text: str) -> str:
    """Sửa các từ viết tắt, teencode thông dụng trong tiếng Việt bằng từ điển tĩnh."""
    if not text:
        return text
    
    mapping = {
        r'\bhđ\b': 'hợp đồng',
        r'\btndn\b': 'thu nhập doanh nghiệp',
        r'\bgtgt\b': 'giá trị gia tăng',
        r'\bnv\b': 'nhân viên',
        r'\bk\b': 'không',
        r'\bko\b': 'không',
        r'\bđk\b': 'đăng ký',
        r'\bbhxh\b': 'bảo hiểm xã hội',
        r'\btnhh\b': 'trách nhiệm hữu hạn',
        r'\bdn\b': 'doanh nghiệp',
        r'\bkh\b': 'khách hàng',
        r'\bhđlđ\b': 'hợp đồng lao động',
        r'\bkd\b': 'kinh doanh',
        r'\bpl\b': 'pháp luật',
        r'\bqđ\b': 'quy định',
        r'\btt\b': 'thủ tục',
        r'\bblđ\b': 'bộ luật lao động',
        r'\bld\b': 'lao động',
        r'\bdt\b': 'doanh thu',
        r'\bcp\b': 'chi phí',
        r'\bth\b': 'trường hợp'
    }
    
    corrected = text
    for pattern, replacement in mapping.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    
    return corrected

def extract_keywords_local(text: str) -> str:
    try:
        cross_refs = re.findall(r'(Điều \d+|khoản \d+ Điều \d+|Chương [IVXLCDM]+)', text)
        thresholds = re.findall(r'(\d+ ngày|\d+ tháng|\d+ năm|\d+%|\d+ triệu|\d+ tỷ)', text)
        
        tokens, tags = ViPosTagger.postagging(ViTokenizer.tokenize(text))
        keywords = [t.replace("_", " ") for t, tag in zip(tokens, tags) if tag in ("N", "Np", "Nc", "V")]
        
        final_entities = []
        if cross_refs: final_entities.extend(cross_refs)
        if thresholds: final_entities.extend(thresholds)
        final_entities.extend(keywords[:15])
        
        seen = set()
        return ", ".join([x for x in final_entities if not (x.lower() in seen or seen.add(x.lower()))])
    except Exception as e:
        logger.error(f"Lỗi extract keywords: {e}")
        return ""

def get_year_from_filename(filename: str) -> int:
    match = re.search(r'\b(19|20)\d{2}\b', filename)
    return int(match.group(0)) if match else 0

def get_law_base_name(filename: str) -> str:
    base = filename.lower().replace(".docx", "").replace(".pdf", "").replace(".doc", "").replace(".txt", "")
    base = re.sub(r'-\d+.*$', '', base)
    base = re.sub(r' \d{4}.*$', '', base)
    return base.strip()

def chunk_text(text: str, law_name: str) -> List[Dict[str, Any]]:
    article_pattern = r'(?:\n|^)(Điều\s+\d+[:\.].*)'
    chapter_pattern = r'(?:\n|^)(Chương\s+[IVXLCDM]+[:\.].*)'
    section_pattern = r'(?:\n|^)(Mục\s+\d+[:\.].*)'
    
    chunks = []
    current_chapter = "Quy định chung"
    current_section = "Quy định chung"
    
    parts = re.split(r'(?:\n|^)(Điều\s+\d+[:\.])', text)
    if len(parts) <= 1:
        raw_chunks = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]
        return [{"text": c, "book": law_name, "chapter": "None", "section": "None", "article": "None"} for c in raw_chunks]

    titles = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        title_line = content.split('\n')[0].strip() if content else ""
        titles.append(f"{header} {title_line}")
        
    for idx, i in enumerate(range(1, len(parts), 2)):
        header = parts[i].strip()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        
        chap_matches = re.findall(chapter_pattern, parts[i-1])
        if chap_matches: 
            current_chapter = chap_matches[-1].strip()
            current_section = "Quy định chung" 
            
        sec_matches = re.findall(section_pattern, parts[i-1])
        if sec_matches: 
            current_section = sec_matches[-1].strip()

        prev_title = titles[idx-1] if idx > 0 else ""
        next_title = titles[idx+1] if idx + 1 < len(titles) else ""
        
        full_article = f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} {content}"
        
        if len(full_article) > 2000:
            clause_parts = re.split(r'(?:\n|^)(\d+\.\s)', content)
            if len(clause_parts) > 1:
                intro = clause_parts[0].strip()
                for j in range(1, len(clause_parts), 2):
                    c_header = clause_parts[j].strip()
                    c_content = clause_parts[j+1].strip() if j+1 < len(clause_parts) else ""
                    sub_text = f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} {intro}\n{c_header} {c_content}"
                    chunks.append({
                        "text": sub_text, "book": law_name, "chapter": current_chapter, 
                        "section": current_section, "article": header,
                        "prev_title": prev_title, "next_title": next_title
                    })
            else:
                sub_chunks = [p for p in full_article.split("\n") if p.strip()]
                for j, sub in enumerate(sub_chunks):
                    chunks.append({
                        "text": f"[{law_name}] → [{current_chapter}] → [{current_section}]\n{header} (Phần {j+1}): {sub}", 
                        "book": law_name, "chapter": current_chapter, "section": current_section, 
                        "article": header, "prev_title": prev_title, "next_title": next_title
                    })
        else:
            chunks.append({
                "text": full_article, "book": law_name, "chapter": current_chapter, 
                "section": current_section, "article": header,
                "prev_title": prev_title, "next_title": next_title
            })
            
    return chunks
