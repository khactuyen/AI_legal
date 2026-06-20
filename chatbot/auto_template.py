import os
import pathlib
from docx import Document

def fill_template(template_name: str, context: dict) -> str:
    """
    Điền dữ liệu vào file template .docx
    Trả về đường dẫn file output đã được điền.
    """
    base_dir = pathlib.Path(__file__).parent
    template_path = base_dir / "templates" / f"{template_name}.docx"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Không tìm thấy template: {template_name}.docx")
        
    doc = Document(str(template_path))
    
    # Hàm đệ quy thay thế text trong các đoạn văn
    for p in doc.paragraphs:
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in p.text:
                # python-docx không hỗ trợ replace trực tiếp text bảo toàn format dễ dàng
                # Cần lặp qua các run
                for run in p.runs:
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, str(value))
                        
    # Thay thế trong bảng
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for key, value in context.items():
                        placeholder = f"{{{{{key}}}}}"
                        if placeholder in p.text:
                            for run in p.runs:
                                if placeholder in run.text:
                                    run.text = run.text.replace(placeholder, str(value))

    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    import uuid
    output_filename = f"filled_{template_name}_{uuid.uuid4().hex[:8]}.docx"
    output_path = output_dir / output_filename
    
    doc.save(str(output_path))
    return str(output_path)
