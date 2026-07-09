import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Mailer")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    """Gửi email thông báo qua SMTP. Nếu chưa cấu hình, in ra Log."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP chưa được cấu hình. (Mock Email Mode)")
        logger.info(f"==== MOCK EMAIL TỚI: {to_email} ====\nSubject: {subject}\nBody:\n{body}\n==========================================")
        return False # Trả về False vì email chưa thực sự được gửi

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Đã gửi email thành công tới {to_email}")
        return True
    except Exception as e:
        logger.error(f"Lỗi gửi email: {e}")
        return False
