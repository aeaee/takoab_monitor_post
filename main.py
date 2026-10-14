import sys
import time
import random
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

from config import (
    POST_URL, CHECK_INTERVAL, GEMINI_API_KEY, USE_AI,
    OPERATING_HOURS, SEND_IDLE_STATUS, is_within_operating_hours
)
from fb_scraper import get_browser_context, manual_login, extract_comments_from_page
from analyzer import analyze_comments
from notifier import (
    load_cache, save_cache, notify_unreplied_order, 
    play_alert_sound, send_system_banner, show_modal_dialog, send_telegram_status
)

def test_notification():
    """ทดสอบระบบแจ้งเตือนและเสียง (รองรับทั้ง Windows และ macOS)"""
    print("[*] กำลังทดสอบส่งการแจ้งเตือนและเล่นเสียง...")
    play_alert_sound()
    send_system_banner(
        title="🚨 ทดสอบแจ้งเตือนออเดอร์",
        subtitle="ระบบ Facebook Group Monitor",
        message="ถ้าคุณเห็นป๊อปอัปและได้ยินเสียง แสดงว่าระบบแจ้งเตือนพร้อมทำงาน 100%!"
    )
    show_modal_dialog(
        customer_name="คุณสมชาย (ทดสอบ)",
        message="สั่งทาโกะยากิ 2 กล่อง\n(ทดสอบระบบหน้าต่างแจ้งเตือน)",
        duration=15
    )
    send_telegram_status("🧪 <b>ทดสอบข้อความสถานะปกติ (แบบไร้เสียง)</b> สำเร็จเรียบร้อย!")
    print("[✓] ส่งการแจ้งเตือนทดสอบเรียบร้อยแล้ว!")

def run_monitor(once: bool = False):
    """รันระบบเฝ้าดูคอมเมนต์ในโพสต์"""
    if not POST_URL or "facebook.com" not in POST_URL:
        print("\n[!] ยังไม่ได้ระบุ POST_URL หรือ URL ไม่ถูกต้อง")
        print("👉 กรุณาเปิดไฟล์ .env แล้วใส่ URL ของโพสต์ที่ต้องการเฝ้าดู เช่น:")
        print("   POST_URL=https://www.facebook.com/groups/xxxx/posts/yyyy/\n")
        return

    print("\n" + "="*60)
    print("🚀 เริ่มระบบเฝ้าดูคอมเมนต์โพสต์ Facebook")
    print(f"📌 ลิงก์โพสต์: {POST_URL}")
    print(f"⏱️ รอบการตรวจสอบ: ทุกๆ ~{CHECK_INTERVAL} วินาที")
    if OPERATING_HOURS:
        print(f"⏰ เวลาทำการร้าน: {OPERATING_HOURS}")
    if SEND_IDLE_STATUS:
        print("📱 อัปเดตสถานะเข้า Telegram: ส่งทุกรอบ (แบบไร้เสียง)")
    if USE_AI and GEMINI_API_KEY:
        print("🤖 โหมดการวิเคราะห์: AI (Google Gemini Flash)")
    else:
        print("🔍 โหมดการวิเคราะห์: Rule-based (ตรวจจับคำว่า 'รับออเดอร์' ในเครื่อง)")
    print("="*60 + "\n")

    notified_cache = load_cache()
    print(f"[*] โหลดประวัติที่เคยแจ้งเตือนแล้ว: {len(notified_cache)} รายการ")

    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.new_page()

        try:
            print("[*] กำลังเปิดหน้าโพสต์ Facebook...")
            page.goto(POST_URL, wait_until="domcontentloaded")
            time.sleep(3)

            # ตรวจสอบเบื้องต้นว่าติดหน้า Login หรือไม่
            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("\n[!] ระบบพบว่าบัญชีของคุณยังไม่ได้ล็อกอิน Facebook")
                print("👉 กรุณารันคำสั่ง: python main.py --login เพื่อล็อกอินก่อน 1 ครั้งครับ\n")
                return

            round_count = 1
            while True:
                # 1. ตรวจสอบเวลาเปิด-ปิดร้าน
                if not is_within_operating_hours():
                    now_str = datetime.now().strftime("%H:%M:%S")
                    print(f"🌙 [{now_str}] ขณะนี้อยู่นอกเวลาเปิดร้าน ({OPERATING_HOURS}) พักการตรวจชั่วคราว...")
                    time.sleep(120)
                    continue

                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"\n🔄 [รอบที่ {round_count} - {now_str}] กำลังตรวจเช็คโพสต์...")

                # 2. ดึงคอมเมนต์
                post_author, comments = extract_comments_from_page(page)
                print(f"   📊 ตรวจพบ {len(comments)} เธรดคอมเมนต์ (เจ้าของโพสต์: {post_author or 'ตรวจจับอัตโนมัติ'})")
                for c in comments:
                    snippet = c.get('text', '').replace('\n', ' ')[:45]
                    r_count = len(c.get('replies', []))
                    print(f"      💬 [{c.get('author', 'ลูกค้า')}] \"{snippet}\" (คำตอบกลับ: {r_count})")

                if comments:
                    # 3. วิเคราะห์หาออเดอร์ที่ยังไม่ได้รับ
                    unreplied_orders = analyze_comments(comments, post_author=post_author)
                    
                    new_alerts = 0
                    for item in unreplied_orders:
                        c_id = item.get("id")
                        if c_id not in notified_cache:
                            notify_unreplied_order(
                                customer_name=item.get("customer_name", "ลูกค้า"),
                                comment_text=item.get("text", ""),
                                reason=item.get("reason", "")
                            )
                            notified_cache.add(c_id)
                            new_alerts += 1

                    if new_alerts > 0:
                        save_cache(notified_cache)
                        print(f"   🚨 แจ้งเตือนออเดอร์ค้างตอบ: {new_alerts} รายการ")
                    else:
                        print("   ✅ ตรวจสอบแล้ว: ออเดอร์ทั้งหมดได้รับการตอบรับแล้ว หรือไม่มีออเดอร์ใหม่")
                        # ส่งข้อความสถานะปกติเข้า Telegram (แบบไร้เสียง ไม่รบกวนมือถือ)
                        if SEND_IDLE_STATUS:
                            short_time = datetime.now().strftime("%H:%M")
                            send_telegram_status(f"✅ ตรวจสอบแล้ว ({short_time}): ไม่มีออเดอร์ใหม่")

                if once:
                    print("\n[✓] ตรวจสอบรอบเดียวเรียบร้อยแล้ว ปิดการทำงาน")
                    break

                # สุ่มหน่วงเวลาเล็กน้อยเพื่อความปลอดภัย ป้องกัน Bot Detection
                jitter = random.randint(-5, 10)
                sleep_time = max(30, CHECK_INTERVAL + jitter)
                print(f"   ⏳ รออีก {sleep_time} วินาทีก่อนตรวจเช็ครอบถัดไป... (กด Ctrl+C เพื่อหยุด)")
                time.sleep(sleep_time)

                # รีเฟรชหน้าโพสต์
                page.reload(wait_until="domcontentloaded")
                round_count += 1

        except KeyboardInterrupt:
            print("\n[!] ผู้ใช้สั่งหยุดการทำงาน (Ctrl+C)")
        finally:
            context.close()
            print("[*] ปิดเบราว์เซอร์เรียบร้อยแล้ว")

def clear_cache():
    """ล้างประวัติการแจ้งเตือนเพื่อเริ่มตรวจนับใหม่ทั้งหมด"""
    from config import CACHE_FILE
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    print("[✓] ล้างประวัติการแจ้งเตือน (notified_cache.json) เรียบร้อยแล้ว")

def setup_telegram():
    """ค้นหา Chat ID ของผู้ใช้อัตโนมัติและบันทึกลง .env"""
    import re
    import requests
    from config import TELEGRAM_BOT_TOKEN, BASE_DIR

    if not TELEGRAM_BOT_TOKEN:
        print("[!] ยังไม่ได้ระบุ TELEGRAM_BOT_TOKEN ในไฟล์ .env")
        return

    print("\n" + "="*60)
    print("🤖 กำลังเชื่อมต่อกับ Telegram Bot (@takoab_alert_bot)...")
    print("👉 หากยังไม่ได้กด ให้เปิดแอป Telegram ค้นหา @takoab_alert_bot แล้วกด [Start]")
    print("="*60)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    for attempt in range(1, 11):
        try:
            resp = requests.get(url, timeout=10).json()
            results = resp.get("result", [])
            if results:
                latest = results[-1]
                msg = latest.get("message", {}) or latest.get("my_chat_member", {})
                chat = msg.get("chat", {})
                chat_id = str(chat.get("id", ""))
                user_name = chat.get("first_name", "") or chat.get("username", "")

                if chat_id:
                    print(f"\n[✓] ตรวจพบ Chat ID ของคุณแล้ว! (ผู้ใช้: {user_name} | ID: {chat_id})")
                    
                    env_path = BASE_DIR / ".env"
                    if env_path.exists():
                        content = env_path.read_text(encoding="utf-8")
                        if "TELEGRAM_CHAT_ID=" in content:
                            content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", content)
                        else:
                            content += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
                        env_path.write_text(content, encoding="utf-8")
                        print("[✓] บันทึก TELEGRAM_CHAT_ID ลงในไฟล์ .env เรียบร้อยแล้ว!")

                    test_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    requests.post(test_url, json={
                        "chat_id": chat_id,
                        "text": "🎉 <b>เชื่อมต่อระบบแจ้งเตือนสำเร็จ!</b>\n\nเมื่อมีลูกค้าสั่งออเดอร์ใหม่ในกลุ่ม Facebook ระบบจะส่งข้อความแจ้งเตือนเข้า Telegram นี้ทันทีครับ",
                        "parse_mode": "HTML"
                    }, timeout=10)
                    print("[✓] ส่งข้อความทดสอบเข้า Telegram บนมือถือของคุณเรียบร้อยแล้ว!")
                    return
        except Exception:
            pass
        
        print(f"[*] กำลังรอข้อความจากคุณใน Telegram... ({attempt}/10) [กรุณากด Start ที่ @takoab_alert_bot]")
        time.sleep(3)

    print("\n[!] ยังไม่พบข้อความเข้า กรุณาเปิด Telegram เข้าไปที่ @takoab_alert_bot แล้วกด Start จากนั้นรันคำสั่งนี้ใหม่อีกครั้งครับ")

def main():
    parser = argparse.ArgumentParser(description="Facebook Group Post Order Monitor")
    parser.add_argument("--login", action="store_true", help="เปิดเบราว์เซอร์เพื่อล็อกอิน Facebook ครั้งแรก")
    parser.add_argument("--watch", action="store_true", help="เริ่มเฝ้าดูโพสต์และแจ้งเตือนออเดอร์")
    parser.add_argument("--check-once", action="store_true", help="ตรวจเช็คเพียง 1 รอบแล้วแสดงผลลัพธ์")
    parser.add_argument("--test-notify", action="store_true", help="ทดสอบระบบเสียงและการแจ้งเตือนบน Mac")
    parser.add_argument("--clear-cache", action="store_true", help="ล้างประวัติคอมเมนต์ที่เคยแจ้งเตือนแล้ว")
    parser.add_argument("--telegram-setup", action="store_true", help="เชื่อมต่อและค้นหา Telegram Chat ID อัตโนมัติ")

    args = parser.parse_args()

    if args.login:
        manual_login()
    elif args.test_notify:
        test_notification()
    elif args.clear_cache:
        clear_cache()
    elif args.telegram_setup:
        setup_telegram()
    elif args.check_once:
        run_monitor(once=True)
    elif args.watch:
        run_monitor(once=False)
    else:
        parser.print_help()
        print("\nตัวอย่างคำสั่งใช้งาน:")
        print("  1. python main.py --login           # ล็อกอิน Facebook ครั้งแรก")
        print("  2. python main.py --telegram-setup  # เชื่อมต่อ Telegram Chat ID อัตโนมัติ")
        print("  3. python main.py --watch           # เริ่มเฝ้าดูโพสต์และแจ้งเตือน")

if __name__ == "__main__":
    main()
