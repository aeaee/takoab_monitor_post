import os
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
TEMPLATE_PATH = BASE_DIR / "post_template.txt"
ASSETS_DIR = BASE_DIR / "post_assets"

THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

def get_thai_date_string(dt: datetime = None) -> str:
    """แปลง datetime เป็นสตริงวันที่ภาษาไทย เช่น 'อาทิตย์ 1/11/69'"""
    if dt is None:
        dt = datetime.now()
    thai_day = THAI_DAYS[dt.weekday()]
    buddhist_year = (dt.year + 543) % 100
    return f"{thai_day} {dt.day}/{dt.month}/{buddhist_year:02d}"

def get_default_template() -> str:
    """อ่านเทมเพลตข้อความโพสต์จากไฟล์ ถ้าไม่มีให้คืนค่าเริ่มต้น"""
    if TEMPLATE_PATH.exists():
        try:
            return TEMPLATE_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "🐙TAKO AB🐙ทาโกะยากิ🐙\n🐙เปิดรับออเดอร์ {date}\nรับออเดอร์ถึง 20.00\n👉https://takoab.aeaee.one"

def save_template(content: str):
    """บันทึกข้อความเทมเพลตโพสต์"""
    TEMPLATE_PATH.write_text(content.strip(), encoding="utf-8")

def format_post_text(template_text: str, custom_date_str: str = None, close_time: str = None) -> str:
    """แทนที่ {date} และ {close_time} ในเทมเพลตด้วยวันที่และเวลาเป้าหมาย"""
    date_str = custom_date_str.strip() if custom_date_str else get_thai_date_string()
    raw_time = close_time.strip() if close_time else "20.00"
    clean_time = raw_time.replace(":", ".").replace("น.", "").replace("น", "").strip() or "20.00"

    text = template_text
    # 1. แทนที่วันที่
    if "{date}" in text:
        text = text.replace("{date}", date_str)
    elif "{today}" in text:
        text = text.replace("{today}", date_str)
    else:
        text = re.sub(r'(🐙เปิดรับออเดอร์\s+)[^\n]*', rf'\g<1>{date_str}', text)

    # 2. แทนที่เวลาปิดรับออเดอร์
    if "{close_time}" in text:
        text = text.replace("{close_time}", clean_time)
    elif "{time}" in text:
        text = text.replace("{time}", clean_time)
    else:
        text = re.sub(r'(รับออเดอร์ถึง\s*)[^\n]*', rf'\g<1>{clean_time}', text)

    return text

def get_default_post_images() -> list[str]:
    """ดึงรายการรูปภาพเมนูเริ่มต้นจากโฟลเดอร์ post_assets"""
    if not ASSETS_DIR.exists():
        return []
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for item in sorted(ASSETS_DIR.iterdir()):
        if item.is_file() and item.suffix.lower() in valid_exts:
            images.append(str(item))
    return images

def update_env_post_url(new_url: str):
    """อัปเดต POST_URL ในไฟล์ .env ทันที"""
    new_url = new_url.strip()
    if not new_url:
        return
    
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"POST_URL={new_url}\n", encoding="utf-8")
        return

    content = ENV_PATH.read_text(encoding="utf-8")
    if re.search(r"^POST_URL=.*$", content, flags=re.MULTILINE):
        new_content = re.sub(r"^POST_URL=.*$", f"POST_URL={new_url}", content, flags=re.MULTILINE)
    else:
        new_content = f"POST_URL={new_url}\n" + content

    ENV_PATH.write_text(new_content, encoding="utf-8")

def publish_facebook_group_post(
    group_id_or_url: str,
    content: str,
    image_paths: list[str] = None,
    headless: bool = True,
    preview_only: bool = False,
    preview_save_path: str = None,
    progress_cb = None
) -> dict:
    """
    สร้างและเผยแพร่โพสต์ลงในกลุ่ม Facebook อัตโนมัติ (หรือโหมดดูภาพตัวอย่าง)
    รองรับการใส่อีโมจิครบถ้วนและแนบรูปภาพหลายรูป
    """
    from fb_scraper import get_browser_context

    def log(msg: str):
        print(f"[*] {msg}")
        if progress_cb:
            try:
                progress_cb(msg)
            except Exception:
                pass

    # จัดการ URL กลุ่ม
    target = group_id_or_url.strip()
    if not target:
        target = "1111870942162462"
    if not target.startswith("http"):
        group_url = f"https://www.facebook.com/groups/{target}"
        group_id = target
    else:
        group_url = target
        m = re.search(r"/groups/(\d+)", target)
        group_id = m.group(1) if m else "1111870942162462"

    # กรองเฉพาะไฟล์รูปที่มีอยู่จริง
    valid_images = []
    if image_paths:
        for p in image_paths:
            if os.path.exists(p):
                valid_images.append(os.path.abspath(p))

    log(f"กำลังเปิดเบราว์เซอร์เพื่อเข้าสู่กลุ่ม Facebook (ID: {group_id})...")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=headless)
        page = ctx.new_page()

        try:
            log("กำลังโหลดหน้ากลุ่ม Facebook...")
            page.goto(group_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            # ค้นหาปุ่มเปิดกล่องสร้างโพสต์
            log("กำลังค้นหาช่อง 'เขียนอะไรสักหน่อย...'...")
            trigger = page.locator(
                'span:has-text("เขียนอะไรสักหน่อย"), div[role="button"]:has-text("เขียนอะไรสักหน่อย"), '
                'span:has-text("Write something"), div[role="button"]:has-text("Write something"), '
                'span:has-text("คุณกำลังคิดอะไรอยู่"), div[role="button"]:has-text("คุณกำลังคิดอะไรอยู่")'
            ).first

            if trigger.count() == 0 or not trigger.is_visible():
                # ลองค้นหาแบบกว้าง
                trigger = page.get_by_text("เขียนอะไรสักหน่อย").first

            if trigger.count() == 0 or not trigger.is_visible():
                raise RuntimeError("ไม่พบช่องสร้างโพสต์ในกลุ่ม กรุณาตรวจสอบว่าบัญชีนี้เป็นสมาชิกของกลุ่มหรือยัง")

            log("กำลังคลิกเปิดกล่องสร้างโพสต์...")
            trigger.click()
            page.wait_for_timeout(2000)

            dialog = page.locator('div[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=12000)
            log("เปิดหน้าต่างสร้างโพสต์สำเร็จ!")

            # กรอกข้อความ
            log("กำลังกรอกข้อความโพสต์ (พร้อมอีโมจิ)...")
            textbox = dialog.locator('div[role="textbox"][contenteditable="true"]').first
            textbox.click()
            page.wait_for_timeout(500)
            page.keyboard.insert_text(content)
            page.wait_for_timeout(1000)

            # แนบรูปภาพ
            if valid_images:
                log(f"กำลังแนบรูปภาพ {len(valid_images)} รูป...")
                file_input = dialog.locator('input[type="file"]').first
                if file_input.count() > 0:
                    file_input.set_input_files(valid_images)
                else:
                    photo_btn = dialog.locator('div[aria-label="รูปภาพ/วิดีโอ"], div[aria-label="Photo/video"]').first
                    if photo_btn.count() > 0:
                        photo_btn.click()
                        page.wait_for_timeout(1000)
                    file_input = dialog.locator('input[type="file"]').first
                    file_input.set_input_files(valid_images)

                # รอให้รูปภาพอัปโหลดและขึ้นพรีวิวในกล่อง
                log("กำลังประมวลผลรูปภาพ...")
                page.wait_for_timeout(4000)

            # โหมดดูตัวอย่าง (Preview)
            if preview_only:
                save_img = preview_save_path or str(BASE_DIR / "preview_post.png")
                page.screenshot(path=save_img)
                log(f"บันทึกภาพตัวอย่างโพสต์ไว้ที่: {save_img}")
                
                # ปิดกล่องข้อความอย่างปลอดภัย
                log("กำลังปิดกล่องข้อความ...")
                close_btn = dialog.locator('div[aria-label="ปิด"], div[aria-label="Close"], div[aria-label="ปิดกล่องโต้ตอบช่องเขียนข้อความ"]').first
                if close_btn.count() > 0:
                    close_btn.click()
                    page.wait_for_timeout(1000)
                    discard = page.locator('div[role="button"]:has-text("ละทิ้ง"), div[role="button"]:has-text("Discard")').first
                    if discard.count() > 0 and discard.is_visible():
                        discard.click()
                        page.wait_for_timeout(1000)

                ctx.close()
                return {
                    "success": True,
                    "preview": True,
                    "preview_image": save_img,
                    "post_url": None,
                    "error": None
                }

            # ตรวจสอบปุ่มโพสต์
            post_btn = dialog.locator(
                'div[aria-label="โพสต์"][role="button"], div[aria-label="Post"][role="button"], '
                'div[role="button"]:has-text("โพสต์"), div[role="button"]:has-text("Post")'
            ).first

            if post_btn.count() == 0 or not post_btn.is_visible():
                raise RuntimeError("ไม่พบปุ่มกด 'โพสต์' ในหน้าต่าง")

            # ตรวจสอบว่าปุ่มกดได้หรือไม่
            aria_disabled = post_btn.get_attribute("aria-disabled")
            if aria_disabled == "true":
                raise RuntimeError("ปุ่มโพสต์ยังไม่พร้อมทำงาน (ถูกปิดการใช้งาน)")

            log("🚀 กำลังคลิกปุ่ม 'โพสต์' ลงกลุ่ม Facebook...")
            post_btn.click()

            # รอให้กล่องโพสต์ปิดตัวลง (detached)
            try:
                page.wait_for_selector('div[role="dialog"]', state="detached", timeout=35000)
                log("กล่องโพสต์ปิดตัวลงแล้ว โพสต์ถูกส่งเรียบร้อย!")
            except Exception:
                log("รอการปิดของหน้าต่างโพสต์นานผิดปกติ ดำเนินการต่อ...")

            # รอให้อัปเดตในฟีดของกลุ่ม
            page.wait_for_timeout(5000)

            # ค้นหาลิงก์โพสต์ใหม่
            log("กำลังค้นหาลิงก์ (URL) ของโพสต์ใหม่...")
            new_post_url = None

            # 1. ค้นหาในหน้าปัจจุบันก่อน
            found_links = page.evaluate("""(groupId) => {
                const links = Array.from(document.querySelectorAll('a[href*="/posts/"], a[href*="/permalink/"]'));
                return links.map(a => a.href).filter(h => h.includes(groupId));
            }""", group_id)

            if found_links:
                # ทำความสะอาด URL ลบ query params ส่วนเกินออก
                clean_url = found_links[0].split("?")[0]
                if clean_url.endswith("/"):
                    clean_url = clean_url[:-1]
                new_post_url = clean_url
                log(f"[✓] ตรวจพบโพสต์ใหม่: {new_post_url}")

            # 2. หากยังไม่พบ ให้รีเฟรชหน้าแบบเรียงล่าสุด
            if not new_post_url:
                log("กำลังรีเฟรชหน้ารายการล่าสุดเพื่อค้นหาลิงก์โพสต์...")
                page.goto(f"{group_url}?sorting_setting=CHRONOLOGICAL", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)

                found_links = page.evaluate("""(groupId) => {
                    const links = Array.from(document.querySelectorAll('a[href*="/posts/"], a[href*="/permalink/"]'));
                    return links.map(a => a.href).filter(h => h.includes(groupId));
                }""", group_id)

                if found_links:
                    clean_url = found_links[0].split("?")[0]
                    if clean_url.endswith("/"):
                        clean_url = clean_url[:-1]
                    new_post_url = clean_url
                    log(f"[✓] ตรวจพบโพสต์ใหม่: {new_post_url}")

            if not new_post_url:
                # กรณีโพสต์สำเร็จแต่ติดรออนุมัติของแอดมินกลุ่ม หรือ Facebook ยังไม่สร้าง permalink ทันที
                new_post_url = group_url
                log("⚠️ โพสต์เรียบร้อยแล้ว แต่อาจกำลังรอแอดมินกลุ่มอนุมัติ หรือลิงก์ยังไม่แสดงบนฟีดทันที")

            ctx.close()
            return {
                "success": True,
                "preview": False,
                "post_url": new_post_url,
                "error": None
            }

        except Exception as e:
            err_msg = str(e)
            log(f"[!] เกิดข้อผิดพลาดในการโพสต์: {err_msg}")
            try:
                page.screenshot(path=str(BASE_DIR / "error_post.png"))
            except Exception:
                pass
            ctx.close()
            return {
                "success": False,
                "preview": False,
                "post_url": None,
                "error": err_msg
            }

