import os
import platform
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8")

# ตรวจสอบระบบปฏิบัติการ (Windows หรือ macOS)
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

# สัญญาณ IPC สำหรับแจ้งบอทที่กำลังทำงานอยู่ให้อัปเดตลิงก์ทันที
TRIGGER_FILE = BASE_DIR / "trigger_check.flag"

def get_post_urls(reload_env: bool = True) -> list:
    """โหลดรายการ POST_URLS ปัจจุบันจาก .env ใหม่แบบ Realtime"""
    if reload_env:
        load_dotenv(BASE_DIR / ".env", encoding="utf-8", override=True)
    raw_post_urls = (os.getenv("POST_URLS", "") or os.getenv("POST_URL", "")).strip()
    urls = [
        u.strip().strip('"').strip("'") for u in raw_post_urls.replace("\n", ",").split(",") 
        if u.strip() and ("facebook.com" in u or "fb.com" in u or "fb.watch" in u)
    ]
    return urls

def get_check_interval(reload_env: bool = False) -> int:
    """โหลดระยะเวลา CHECK_INTERVAL ล่าสุดจาก .env"""
    if reload_env:
        load_dotenv(BASE_DIR / ".env", encoding="utf-8", override=True)
    try:
        return int(os.getenv("CHECK_INTERVAL", "180"))
    except ValueError:
        return 180

def signal_url_update():
    """ส่งสัญญาณ IPC ให้บอทที่กำลังรันอยู่สลับลิงก์และเริ่มตรวจทันที"""
    try:
        import time
        TRIGGER_FILE.write_text(f"reload:{time.time()}", encoding="utf-8")
    except Exception:
        pass

def get_auto_reply_settings(reload_env: bool = False) -> tuple[bool, str]:
    """โหลดการตั้งค่าตอบกลับคอมเมนต์อัตโนมัติล่าสุดจาก .env"""
    if reload_env:
        load_dotenv(BASE_DIR / ".env", encoding="utf-8", override=True)
    enabled = os.getenv("ENABLE_AUTO_REPLY", "false").strip().lower() == "true"
    msg = os.getenv("AUTO_REPLY_MESSAGE", "รับออเดอร์เรียบร้อยแล้วค่ะ ขอบคุณมากนะคะ 🙏").strip()
    return enabled, msg

# ตั้งค่า URL ของโพสต์เริ่มต้น (เพื่อความเข้ากันได้ย้อนหลังกับโมดูลเดิม)
raw_post_urls = (os.getenv("POST_URLS", "") or os.getenv("POST_URL", "")).strip()
POST_URLS = [
    u.strip().strip('"').strip("'") for u in raw_post_urls.replace("\n", ",").split(",") 
    if u.strip() and ("facebook.com" in u or "fb.com" in u or "fb.watch" in u)
]
POST_URL = POST_URLS[0] if POST_URLS else ""

# รายชื่อโปรไฟล์คนขาย / คนตอบรับออเดอร์ (รองรับหลายคน โดยคั่นด้วยเครื่องหมายจุลภาค , )
raw_authors = os.getenv("POST_AUTHOR_NAME", "").strip()
SELLER_NAMES = [s.strip() for s in raw_authors.split(",") if s.strip()]
POST_AUTHOR_NAME = ", ".join(SELLER_NAMES) if SELLER_NAMES else ""

# ระยะเวลารอระหว่างรอบการตรวจ (วินาที) ค่าเริ่มต้น 180 วินาที (3 นาที)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))

# ช่วงเวลาเปิดร้าน (เช่น 10:00-20:00) ถ้าปล่อยว่างจะตรวจตลอด 24 ชม.
OPERATING_HOURS = os.getenv("OPERATING_HOURS", "10:00-20:00").strip()
# การตอบรับออเดอร์อัตโนมัติบน Facebook
ENABLE_AUTO_REPLY, AUTO_REPLY_MESSAGE = get_auto_reply_settings(reload_env=False)


# ส่งข้อความสถานะปกติทุกรอบแบบไร้เสียง (Silent Telegram Message)
SEND_IDLE_STATUS = os.getenv("SEND_IDLE_STATUS", "true").strip().lower() == "true"

def is_within_operating_hours() -> bool:
    """ตรวจสอบว่าเวลาปัจจุบันอยู่ในเวลาทำการของร้านหรือไม่"""
    if not OPERATING_HOURS or "-" not in OPERATING_HOURS:
        return True
    try:
        from datetime import datetime
        parts = OPERATING_HOURS.split("-")
        start_t = datetime.strptime(parts[0].strip(), "%H:%M").time()
        end_t = datetime.strptime(parts[1].strip(), "%H:%M").time()
        now_t = datetime.now().time()
        if start_t <= end_t:
            return start_t <= now_t <= end_t
        else:
            return now_t >= start_t or now_t <= end_t
    except Exception:
        return True

# รูปแบบการแจ้งเตือน: 'dialog', 'banner', 'both'
NOTIFICATION_STYLE = os.getenv("NOTIFICATION_STYLE", "both").strip().lower()

# ระยะเวลาให้ป๊อปอัปค้างไว้ (วินาที) 0 = ค้างตลอดจนกว่าจะกดปิด
NOTIFICATION_DURATION = int(os.getenv("NOTIFICATION_DURATION", "60"))

# Telegram Notification (รองรับหลาย Chat ID คั่นด้วยจุลภาค , หรือ Group Chat ID)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
raw_chat_ids = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_CHAT_IDS = [cid.strip() for cid in raw_chat_ids.split(",") if cid.strip()]
TELEGRAM_CHAT_ID = TELEGRAM_CHAT_IDS[0] if TELEGRAM_CHAT_IDS else ""

# เปิด/ปิดการใช้งาน AI (true = ใช้ Gemini AI, false = ใช้ตรวจ Keyword ในเครื่อง)
USE_AI = os.getenv("USE_AI", "true").strip().lower() == "true"

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()

# คีย์เวิร์ดยืนยันการรับออเดอร์ (ครอบคลุมทั้ง ครับ และ ค่ะ)
raw_keywords = os.getenv("CONFIRM_KEYWORDS", "รับออเดอร์,รับยอด,เรียบร้อย,รับแล้ว,จดแล้ว,ตอบแชท,ทักแชท,ส่งให้แล้ว,รับออเดอร์ค่ะ,รับออเดอร์ครับ,รับยอดค่ะ,รับยอดครับ,จดแล้วค่ะ,จดแล้วครับ")
CONFIRM_KEYWORDS = [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]

# คีย์เวิร์ดที่แสดงว่าเป็นออเดอร์หรือคำถามสั่งอาหาร
ORDER_KEYWORDS = [
    "เอา", "รับ", "สั่ง", "กล่อง", "ที่", "จาน", "ถุง", "ชุด", "แก้ว", "ชิ้น", "cf", "จอง",
    "โอน", "ราคา", "เท่าไหร่", "กี่บาท", "ส่ง", "มีไหม", "ยังมีไหม", "พร้อมส่ง",
    "รูป", "ตามรูป", "แบบในรูป", "ในรูป", "แบบนี้", "ทาโกะ", "นักเก็ต", "เฟรนฟราย", "ไก่", "เมนู", "แถม"
]

# คีย์เวิร์ดข้อความประกาศ/แจ้งข้อมูลของร้าน (ไม่ใช่การสั่งอาหาร)
ANNOUNCEMENT_KEYWORDS = [
    "พร้อมจัดส่ง", "จัดส่งทุก", "สแกนจ่าย", "เปิดรับออเดอร์", "ปิดรับออเดอร์",
    "ปิดรอบ", "หมดแล้ว", "เปิดร้าน", "ขอบคุณลูกค้า", "ส่งรอบ", "หน้าถุง", "โอนเงินเข้าบัญชี"
]

# ข้อความทักทาย ขอบคุณ หรือคำเชิญชวนสั่งอาหารของคนขาย (ไม่ใช่การสั่งอาหาร)
SELLER_GREETINGS_OR_INVITATIONS = [
    "สั่งได้", "สอบถามได้", "ทักได้", "สั่งมาได้", "แวะมา", "เจอกัน", "พร้อมเสิร์ฟ",
    "ขอบคุณ", "ยินดี", "สวัสดี", "โอเค", "ครับผม", "ค่ะคุณ", "ตามนั้น", "รับตลอด", "รับทราบ"
]

# รายการเมนูอาหารของร้าน
FOOD_ITEMS = [
    "ทาโกะ", "ทาโกะยากิ", "นักเก็ต", "เฟรนฟราย", "เฟรนช์ฟราย", "ไก่", "ชีส",
    "ปลาหมึก", "ทูน่า", "แซลมอน", "กุ้ง", "ปูอัด", "ยำสาหร่าย", "ไส้กรอก", "ไข่กุ้ง", "รวมมิตร"
]

# หน่วยนับ และคำกริยาสั่งอาหาร
UNIT_KEYWORDS = ["กล่อง", "ชุด", "จาน", "ถุง", "ชิ้น", "ลูก", "ที่"]
ORDER_VERBS = ["สั่ง", "เอา", "จอง", "cf", "สั่งให้", "แทน"]

# ค้นหาเส้นทาง Google Chrome ตามระบบปฏิบัติการ
def get_default_chrome_path():
    custom_path = os.getenv("CHROME_PATH", "").strip()
    if custom_path and Path(custom_path).exists():
        return custom_path

    if IS_MAC:
        mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if mac_chrome.exists():
            return str(mac_chrome)
    elif IS_WINDOWS:
        possible_win_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
        ]
        for p in possible_win_paths:
            if Path(p).exists():
                return p
    return ""  # ถ้าไม่พบ ให้ Playwright ใช้ channel="chrome" แทน

CHROME_PATH = get_default_chrome_path()

# โฟลเดอร์เก็บ Session การล็อกอิน Facebook
USER_DATA_DIR = BASE_DIR / "fb_profile"

# ไฟล์บันทึกประวัติคอมเมนต์ที่แจ้งเตือนไปแล้ว
CACHE_FILE = BASE_DIR / "notified_cache.json"
