# Facade for backward compatibility
# Re-exports all functionality from the modular subpackages without changes in behavior.

import sys
import os
# Đảm bảo thư mục cha được thêm vào sys.path để import tuyệt đối gói chatbot.* thành công
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from chatbot.config import BASE_DIR, DATA_DIR, INDEX_DIR, CONTRACT_DIR, TEMP_UPLOAD_DIR
from chatbot.database.vector_store import LawVectorStore, build_or_load_store
from chatbot.utils.document_loaders import read_docx, read_txt, read_doc, read_pdf, read_contract_file
from chatbot.utils.text_processing import (
    redact_sensitive_data,
    extract_keywords_local,
    get_year_from_filename,
    get_law_base_name,
    chunk_text
)
from chatbot.services.llm_service import (
    get_gemini_model,
    draft_new_contract_stream,
    process_user_message_stream,
    process_user_message_deep_stream,
    analyze_contract_file_stream,
    analyze_contract_file
)