import sqlite3
import logging
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mailer import send_email_notification
from sync_agent import run_sync_job

logger = logging.getLogger("ScheduledAgents")
DB_PATH = "feedback.db"
ADMIN_EMAIL = "admin@company.com" # Sẽ thay bằng email quản trị cấu hình từ .env sau

def calculate_tier_and_should_send(expiration_date_str: str, last_notified_at_str: str, current_tier: str) -> tuple[bool, str]:
    """
    Tính toán xem có nên gửi mail không dựa vào quy tắc:
    - Mốc 6 tháng (180 ngày), 3 tháng (90 ngày), 1 tháng (30 ngày): Gửi 1 lần
    - < 1 tháng (> 7 ngày): Mỗi tuần 1 lần
    - < 7 ngày: Mỗi ngày 1 lần
    Trả về: (should_send, new_tier_to_save)
    """
    if not expiration_date_str:
        return False, current_tier
        
    try:
        exp_date = datetime.strptime(expiration_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (exp_date - today).days
        
        last_notified = None
        if last_notified_at_str:
            last_notified = datetime.strptime(last_notified_at_str[:10], "%Y-%m-%d").date()
            
        days_since_last = (today - last_notified).days if last_notified else 9999
        
        # Đã hết hạn hoặc còn quá xa
        if days_left < 0 or days_left > 185:
            return False, current_tier

        # Tier 6 Tháng
        if 175 <= days_left <= 185:
            if current_tier != "6M": return True, "6M"
            return False, current_tier
            
        # Tier 3 Tháng
        if 85 <= days_left <= 95:
            if current_tier != "3M": return True, "3M"
            return False, current_tier
            
        # Tier 1 Tháng
        if 25 <= days_left <= 35:
            if current_tier != "1M": return True, "1M"
            return False, current_tier
            
        # Tier Weekly (< 1 tháng, > 7 ngày)
        if 7 < days_left < 25:
            if days_since_last >= 7: return True, "WEEKLY"
            return False, current_tier
            
        # Tier Daily (<= 7 ngày)
        if 0 <= days_left <= 7:
            if days_since_last >= 1: return True, "DAILY"
            return False, current_tier

        return False, current_tier
    except Exception as e:
        logger.error(f"Lỗi tính toán tier: {e}")
        return False, current_tier


def check_and_send_alerts():
    logger.info("Escalating Email Agent đang kiểm tra hạn hợp đồng...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, contract_name, partner_name, expiration_date, last_notified_at, notification_tier FROM company_contracts WHERE status = 'ACTIVE'")
    contracts = cursor.fetchall()
    
    for row in contracts:
        c_id, c_name, p_name, exp_date, last_notif, current_tier = row
        
        should_send, new_tier = calculate_tier_and_should_send(exp_date, last_notif, current_tier)
        
        if should_send:
            subject = f"[CẢNH BÁO {new_tier}] Hợp đồng sắp hết hạn: {c_name}"
            body = f"Kính gửi Ban Quản trị,\n\nHợp đồng '{c_name}' ký với đối tác '{p_name}' sẽ hết hạn vào ngày {exp_date}.\nCấp độ cảnh báo: {new_tier}\n\nVui lòng xem xét gia hạn sớm."
            
            # Gửi mail
            success = send_email_notification(ADMIN_EMAIL, subject, body)
            
            if success:
                # Cập nhật UI Notification
                cursor.execute("INSERT INTO notifications (title, message) VALUES (?, ?)", (subject, body))
                
                # Cập nhật trạng thái
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE company_contracts SET last_notified_at = ?, notification_tier = ? WHERE id = ?", (now_str, new_tier, c_id))
                conn.commit()
                
    conn.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    
    # Đồng bộ dữ liệu mỗi 30 phút (dev test 5 phút)
    scheduler.add_job(run_sync_job, 'interval', minutes=5)
    
    # Kiểm tra gửi mail mỗi giờ (dev test 5 phút)
    scheduler.add_job(check_and_send_alerts, 'interval', minutes=5)
    
    scheduler.start()
    logger.info("Đã khởi động Data Sync Agent và Escalating Email Agent.")
