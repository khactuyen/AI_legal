import os
import pathlib
import logging
import subprocess
from docx import Document
from chatbot.config import TEMP_UPLOAD_DIR

logger = logging.getLogger("chatbot.utils.document_loaders")

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

_OCR_MODEL = None

def get_ocr_model():
    global _OCR_MODEL
    if _OCR_MODEL is None and PaddleOCR is not None:
        try:
            _OCR_MODEL = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
        except Exception as e:
            logger.error(f"Lỗi khởi tạo PaddleOCR: {e}")
    return _OCR_MODEL

def read_docx(path: pathlib.Path) -> str:
    try:
        doc = Document(str(path))
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        logger.error(f"Lỗi đọc DOCX {path}: {e}")
        return ""

def read_txt(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Lỗi đọc TXT {path}: {e}")
        return ""

def read_doc(path: pathlib.Path) -> str:
    try:
        result = subprocess.run(['antiword', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.warning(f"antiword failed cho file .doc, kết quả: {result.stderr}")
            return ""
    except Exception as e:
        logger.error(f"Lỗi đọc DOC {path} (yêu cầu cài antiword): {e}")
        return ""

def read_pdf(path: pathlib.Path) -> str:
    if not fitz:
        logger.warning("Thư viện PyMuPDF (fitz) chưa cài đặt.")
        return ""
    try:
        doc = fitz.open(str(path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
            
        if len(text.strip()) < 50:
            logger.info(f"Phát hiện PDF scan: {path.name}, tiến hành OCR bằng PaddleOCR...")
            ocr_model = get_ocr_model()
            if not ocr_model:
                return text
                
            ocr_text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
                img_bytes = pix.tobytes("png")
                
                temp_img_path = str(TEMP_UPLOAD_DIR / f"temp_ocr_{page_num}.png")
                with open(temp_img_path, "wb") as f:
                    f.write(img_bytes)
                    
                result = ocr_model.ocr(temp_img_path, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        ocr_text += line[1][0] + " "
                ocr_text += "\n"
                
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)
            return ocr_text.strip()
            
        return text.strip()
    except Exception as e:
        logger.error(f"Lỗi đọc PDF {path}: {e}")
        return ""

def read_contract_file(path: pathlib.Path | str) -> str:
    p = pathlib.Path(path)
    if not p.exists(): return ""
    ext = p.suffix.lower()
    if ext == ".docx":
        return read_docx(p)
    elif ext == ".pdf":
        return read_pdf(p)
    elif ext == ".doc":
        return read_doc(p)
    else:
        return read_txt(p)
