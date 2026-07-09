import os
import sys
import json
import re
import zipfile
import pathlib
import logging

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("generate_results")

# Thêm thư mục cha và thư mục chatbot vào sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
chatbot_dir = os.path.join(parent_dir, "chatbot")
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from chatbot.database.vector_store import build_or_load_store
from chatbot.services.llm_service import generate_complete, CORE_SYSTEM_INSTRUCTION

# Đường dẫn tệp tin
EVAL_FILE = pathlib.Path(parent_dir) / "eval" / "R2AIStage1DATA.json"
OUTPUT_FILE = pathlib.Path(parent_dir) / "results.json"
ZIP_FILE = pathlib.Path(parent_dir) / "results.zip"

# Bảng ánh xạ tệp tin sang Mã văn bản và Tên văn bản chuẩn theo yêu cầu R2AI
LAW_MAPPING = {
    "Luat doanh nghiep-59-2020-QH14.docx": {
        "code": "59/2020/QH14",
        "name": "Luật 59/2020/QH14 Luật Doanh nghiệp"
    },
    "Luat dau tu -61-2020-QH14.docx": {
        "code": "61/2020/QH14",
        "name": "Luật 61/2020/QH14 Luật Đầu tư"
    },
    "Luat thue gia tri gia tang -90-2025-QH15.docx": {
        "code": "90/2025/QH15",
        "name": "Luật 90/2025/QH15 Luật Thuế giá trị gia tăng"
    },
    "Luật quan li thue -38-2019-QH14.docx": {
        "code": "38/2019/QH14",
        "name": "Luật 38/2019/QH14 Luật Quản lý thuế"
    },
    "Luật suadoibosung-03-2022-QH15.docx": {
        "code": "03/2022/QH15",
        "name": "Luật 03/2022/QH15 Luật sửa đổi, bổ sung một số điều của Luật Đầu tư công, Luật Đầu tư theo phương thức đối tác công tư, Luật Đầu tư, Luật Nhà ở, Luật Đấu thầu, Luật Điện lực, Luật Doanh nghiệp, Luật Thuế tiêu thụ đặc biệt và Luật Thi hành án dân sự"
    },
    "Nghị định huong dan luat dau tu -31-2021-NĐ-CP.docx": {
        "code": "31/2021/NĐ-CP",
        "name": "Nghị định 31/2021/NĐ-CP Quy định chi tiết và hướng dẫn thi hành một số điều của Luật Đầu tư"
    },
    "Nghị định quy dinh ve hoa don chung tu  -123-2020-NĐ-CP.docx": {
        "code": "123/2020/NĐ-CP",
        "name": "Nghị định 123/2020/NĐ-CP Quy định về hóa đơn, chứng từ"
    },
    "THUẾ THU NHẬP DOANH NGHIỆP.docx": {
        "code": "14/2008/QH12",
        "name": "Luật 14/2008/QH12 Luật Thuế thu nhập doanh nghiệp"
    },
    "luat thuong mai 36_2005_QH11_2633.doc": {
        "code": "36/2005/QH11",
        "name": "Luật 36/2005/QH11 Luật Thương mại"
    },
    "luật lao động  45-2019-QH14.docx": {
        "code": "45/2019/QH14",
        "name": "Bộ luật 45/2019/QH14 Bộ luật Lao động"
    },
    "suadoibosung luat dautu-2022.docx": {
        "code": "03/2022/QH15",
        "name": "Luật 03/2022/QH15 Luật sửa đổi, bổ sung một số điều của Luật Đầu tư công, Luật Đầu tư theo phương thức đối tác công tư, Luật Đầu tư, Luật Nhà ở, Luật Đấu thầu, Luật Điện lực, Luật Doanh nghiệp, Luật Thuế tiêu thụ đặc biệt và Luật Thi hành án dân sự"
    },
    "thue thu nhap doanh nghiep 14-2008-QH12.docx": {
        "code": "14/2008/QH12",
        "name": "Luật 14/2008/QH12 Luật Thuế thu nhập doanh nghiệp"
    }
}

def clean_article_name(article_name: str) -> str:
    """Chuẩn hóa tên điều luật, ví dụ: 'Điều 15.' -> 'Điều 15'"""
    if not article_name:
        return ""
    cleaned = article_name.strip()
    cleaned = re.sub(r'[:\.\s]+$', '', cleaned)
    match = re.match(r'([Đđ]iều\s+\d+)', cleaned)
    if match:
        val = match.group(1)
        if val.startswith('đ'):
            val = 'Đ' + val[1:]
        return val
    return cleaned

def extract_relevant(relevant_docs_retrieved, generated_answer):
    """
    Trích xuất danh sách văn bản và điều luật thực sự có liên quan
    dựa trên kết quả RAG và nội dung câu trả lời của LLM.
    """
    docs_set = set()
    articles_set = set()
    
    # 1. Trích xuất tất cả các số hiệu điều xuất hiện trong câu trả lời (ví dụ: "Điều 15")
    mentioned_articles = re.findall(r'[Đđ]iều\s+(\d+)', generated_answer)
    mentioned_articles_ints = [int(x) for x in mentioned_articles]
    
    # 2. Tìm các mã văn bản được nhắc tới trong câu trả lời (ví dụ: "59/2020/QH14")
    mentioned_codes = []
    for filename, info in LAW_MAPPING.items():
        code = info["code"]
        if code in generated_answer:
            mentioned_codes.append(code)
            
    # 3. Duyệt qua các chunk trích xuất từ RAG
    for text, meta, score in relevant_docs_retrieved:
        source_file = meta.get("source_file")
        if not source_file or source_file not in LAW_MAPPING:
            continue
            
        info = LAW_MAPPING[source_file]
        code = info["code"]
        name = info["name"]
        
        article_str = meta.get("article", "").strip()
        cleaned_article = clean_article_name(article_str)
        
        is_relevant = False
        
        # Nếu mã văn bản này được nhắc tới trong câu trả lời
        if code in mentioned_codes:
            if cleaned_article:
                art_match = re.search(r'Điều\s+(\d+)', cleaned_article)
                if art_match:
                    art_num = int(art_match.group(1))
                    if art_num in mentioned_articles_ints:
                        is_relevant = True
            else:
                is_relevant = True
                
        # Nếu cụm từ "Điều X" (ví dụ: "Điều 15") xuất hiện trực tiếp trong câu trả lời
        if not is_relevant and cleaned_article and cleaned_article in generated_answer:
            is_relevant = True
            
        if is_relevant:
            docs_set.add(f"{code}|{name}")
            if cleaned_article and cleaned_article.startswith("Điều"):
                articles_set.add(f"{code}|{name}|{cleaned_article}")
                
    # Fallback: Nếu không tìm thấy bất kỳ điều luật nào khớp giữa câu trả lời và RAG,
    # lấy 2 chunk đầu tiên từ RAG làm mặc định
    if not articles_set and relevant_docs_retrieved:
        for text, meta, score in relevant_docs_retrieved[:2]:
            source_file = meta.get("source_file")
            if source_file in LAW_MAPPING:
                info = LAW_MAPPING[source_file]
                code = info["code"]
                name = info["name"]
                docs_set.add(f"{code}|{name}")
                
                article_str = meta.get("article", "").strip()
                cleaned_article = clean_article_name(article_str)
                if cleaned_article and cleaned_article.startswith("Điều"):
                    articles_set.add(f"{code}|{name}|{cleaned_article}")
                    
    # Đảm bảo mọi phần tử trong articles_set đều có văn bản cha tương ứng trong docs_set
    for art in articles_set:
        parts = art.split("|")
        doc_key = f"{parts[0]}|{parts[1]}"
        docs_set.add(doc_key)
        
    return sorted(list(docs_set)), sorted(list(articles_set))

def main():
    logger.info("=== BẮT ĐẦU ĐÁNH GIÁ VÀ XUẤT KẾT QUẢ R2AI STAGE 1 ===")
    
    # 1. Đọc tệp câu hỏi kiểm thử
    if not EVAL_FILE.exists():
        logger.error(f"Không tìm thấy tệp câu hỏi tại {EVAL_FILE}")
        return
        
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
        
    limit = os.getenv("LIMIT_QUESTIONS")
    if limit:
        test_cases = test_cases[:int(limit)]
        logger.info(f"Đang giới hạn kiểm thử ở {limit} câu hỏi đầu tiên theo biến môi trường LIMIT_QUESTIONS.")
    else:
        logger.info(f"Đã đọc {len(test_cases)} câu hỏi kiểm thử.")
        
    # Nạp kết quả cũ (nếu có) để phục hồi tiến độ (Resume)
    completed_ids = set()
    results_dict = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
                for item in existing_results:
                    if item and "id" in item:
                        results_dict[item["id"]] = item
                        completed_ids.add(item["id"])
            logger.info(f"Phát hiện file kết quả cũ {OUTPUT_FILE.name} với {len(completed_ids)} câu đã hoàn thành.")
        except Exception as e:
            logger.warning(f"Không thể đọc file kết quả cũ: {e}. Sẽ chạy lại từ đầu.")
            
    run_test_cases = [case for case in test_cases if case.get("id") not in completed_ids]
    logger.info(f"Số câu hỏi còn lại cần xử lý: {len(run_test_cases)}")
    
    # 1.5. Tự động sao chép các tài liệu luật từ thư mục gốc vào chatbot/data_laws nếu trống
    src_data_laws = pathlib.Path(parent_dir) / "data_laws"
    dst_data_laws = pathlib.Path(parent_dir) / "chatbot" / "data_laws"
    if src_data_laws.exists():
        dst_data_laws.mkdir(exist_ok=True)
        src_files = list(src_data_laws.glob("*"))
        dst_files = list(dst_data_laws.glob("*"))
        if not dst_files and src_files:
            logger.info("Phát hiện chatbot/data_laws đang trống. Đang sao chép tài liệu từ data_laws ở thư mục gốc...")
            import shutil
            for f_path in src_files:
                if f_path.is_file():
                    try:
                        shutil.copy(f_path, dst_data_laws / f_path.name)
                        logger.info(f"Đã sao chép: {f_path.name}")
                    except Exception as e:
                        logger.error(f"Không thể sao chép {f_path.name}: {e}")
            logger.info("Đã sao chép toàn bộ tài liệu luật thành công.")

    # 2. Khởi tạo / Nạp Vector Store
    logger.info("Đang khởi tạo hoặc nạp cơ sở dữ liệu Vector...")
    store = build_or_load_store()
    logger.info("Khởi tạo Vector Store thành công.")

    if not run_test_cases:
        logger.info("Tất cả câu hỏi đã được xử lý xong từ trước!")
        # Nén kết quả thành results.zip dạng phẳng và thoát
        logger.info("Đang nén file kết quả thành results.zip phẳng...")
        try:
            with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zip_f:
                zip_f.write(OUTPUT_FILE, arcname=OUTPUT_FILE.name)
            logger.info(f"Nén thành công! File lưu tại: {ZIP_FILE}")
        except Exception as e:
            logger.error(f"Lỗi khi nén kết quả: {e}")
        logger.info("=== HOÀN THÀNH QUY TRÌNH KIỂM THỬ ===")
        return
        
    import concurrent.futures
    
    max_workers = int(os.getenv("MAX_WORKERS", "1"))
    logger.info(f"Khởi chạy đánh giá song song với max_workers = {max_workers}")
    
    completed_count = 0
    
    def process_case(item):
        idx, case = item
        case_id = case.get("id")
        question = case.get("question")
        
        logger.info(f"Đang xử lý câu hỏi ID {case_id}: '{question[:50]}...'")
        
        # Tìm kiếm các tài liệu liên quan
        relevant_docs = store.search(question, top_k=5, use_reranker=True, use_llm_rerank=False, use_query_expansion=True, use_hyde=True)
        
        # Tạo câu trả lời bằng LLM
        context_str = "\n\n".join([f"- {doc[0]}" for doc in relevant_docs]) if relevant_docs else "Không tìm thấy dữ liệu nội bộ liên quan."
        prompt = f"{CORE_SYSTEM_INSTRUCTION}\n\nCONTEXT (DỮ LIỆU LUẬT MỚI NHẤT TRÍCH XUẤT ĐƯỢC):\n{context_str}\n\nCÂU HỎI HIỆN TẠI:\n{question}"
        
        try:
            answer = generate_complete(prompt)
        except Exception as e:
            logger.error(f"Lỗi khi sinh câu trả lời bằng LLM cho ID {case_id}: {e}")
            answer = "Dữ liệu nội bộ chưa có quy định chi tiết về vấn đề này."
            
        # Trích xuất relevant_docs và relevant_articles từ câu trả lời
        docs_list, articles_list = extract_relevant(relevant_docs, answer)
        
        return case_id, {
            "id": case_id,
            "question": question,
            "answer": answer,
            "relevant_docs": docs_list,
            "relevant_articles": articles_list
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_case, (idx, case)): idx for idx, case in enumerate(run_test_cases)}
        for future in concurrent.futures.as_completed(futures):
            try:
                case_id, res = future.result()
                results_dict[case_id] = res
            except Exception as e:
                logger.error(f"Lỗi trong luồng xử lý: {e}")
                
            completed_count += 1
            
            # Lưu định kỳ sau mỗi 10 câu hỏi để tránh mất dữ liệu
            if completed_count % 10 == 0 or completed_count == len(run_test_cases):
                # Sắp xếp kết quả theo ID tăng dần
                sorted_results = [results_dict[cid] for cid in sorted(results_dict.keys())]
                with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
                    json.dump(sorted_results, out_f, ensure_ascii=False, indent=2)
                logger.info(f"Đã hoàn thành thêm {completed_count}/{len(run_test_cases)} câu. Tổng số câu đã lưu: {len(sorted_results)}")
            
    # 4. Nén kết quả thành results.zip dạng phẳng
    logger.info("Đang nén file kết quả thành results.zip phẳng...")
    try:
        with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zip_f:
            zip_f.write(OUTPUT_FILE, arcname=OUTPUT_FILE.name)
        logger.info(f"Nén thành công! File lưu tại: {ZIP_FILE}")
    except Exception as e:
        logger.error(f"Lỗi khi nén kết quả: {e}")
        
    logger.info("=== HOÀN THÀNH QUY TRÌNH KIỂM THỬ ===")

if __name__ == "__main__":
    main()
