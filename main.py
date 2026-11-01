import sys
import time
import random
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    POST_URL, POST_URLS, CHECK_INTERVAL, GEMINI_API_KEY, USE_AI,
    OPERATING_HOURS, SEND_IDLE_STATUS, is_within_operating_hours,
    TRIGGER_FILE, get_post_urls, get_check_interval,
    ENABLE_AUTO_REPLY, AUTO_REPLY_MESSAGE, get_auto_reply_settings
)
from fb_scraper import get_browser_context, manual_login, extract_comments_from_page, reply_to_facebook_comment
from analyzer import analyze_comments
from notifier import (
    load_cache, save_cache, notify_unreplied_order, 
    play_alert_sound, send_system_banner, show_modal_dialog, send_telegram_status,
    send_telegram_alert, send_pos_draft_order
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
    print("[*] กำลังส่งแจ้งเตือนออเดอร์ทดสอบเข้า Telegram...")
    send_telegram_alert(
        customer_name="คุณสมชาย (ทดสอบระบบ)",
        message="สั่งทาโกะยากิ 2 กล่อง\n(ข้อความทดสอบแจ้งเตือนจาก Takoab Monitor)",
        reason="ทดสอบระบบการแจ้งเตือน",
        sync=True
    )
    send_telegram_status("🧪 <b>ทดสอบข้อความสถานะปกติ (แบบไร้เสียง)</b> สำเร็จเรียบร้อย!", sync=True)
    print("[✓] ส่งการแจ้งเตือนทดสอบเรียบร้อยแล้ว!")

def test_order(customer_name: str = "", comment_text: str = ""):
    """ทดสอบส่งออเดอร์เข้า Telegram เพื่อทดสอบการทำงานของคำถามโต้ตอบและร่างออเดอร์"""
    name = customer_name.strip() or "ทดสอบ ลูกค้า Facebook"
    comment = comment_text.strip() or "มาม่าไก่กรอบคลุกซอส ไม่เผ็ด (แยกสาหร่าย) 2 ไก่กรอบคลุกซอสเกาหลี 1 194/119 ซ.6/2 ใช้ไทยพลัสค่ะ"

    print("\n" + "=" * 60)
    print("🧪 เริ่มทดสอบส่งออเดอร์เข้า Telegram")
    print(f"👤 ชื่อลูกค้า: {name}")
    print(f"💬 ข้อความคอมเมนต์: {comment}")
    print("=" * 60)
    print("[*] กำลังส่งข้อมูลไปยัง POS Telegram Draft API...")

    res = send_pos_draft_order(customer_name=name, comment_text=comment, reason="ทดสอบระบบ Telegram Draft", sync=True)
    if res and res.get("success"):
        draft_id = res.get("draft_id", "-")
        print(f"\n[✓] สร้างร่างออเดอร์เข้า Telegram สำเร็จ! (Draft ID: {draft_id})")
        print("👉 กรุณาเปิดแอป Telegram เพื่อทดสอบตอบคำถามและยืนยันออเดอร์ได้ทันที")
    else:
        err = res.get("error") if res else "เกิดข้อผิดพลาด"
        print(f"\n[!] ส่งออเดอร์ทดสอบไม่สำเร็จ: {err}")


def run_monitor(once: bool = False):
    """รันระบบเฝ้าดูคอมเมนต์ในโพสต์ (รองรับหลายโพสต์ และรองรับเปลี่ยน/สลับลิงก์ทันทีแบบ Realtime)"""
    active_urls = get_post_urls(reload_env=True)
    if not active_urls:
        active_urls = POST_URLS

    if not active_urls:
        print("\n[!] ยังไม่ได้ระบุ POST_URL หรือไม่มี URL ที่ถูกต้อง")
        print("👉 กรุณาเปิดไฟล์ .env หรือระบุลิงก์ในหน้าต่างโปรแกรม (GUI) แล้วบันทึก/อัปเดต\n")
        return

    print("\n" + "="*60)
    print("🚀 เริ่มระบบเฝ้าดูคอมเมนต์โพสต์ Facebook")
    print(f"📌 จำนวนโพสต์ที่เฝ้าดู: {len(active_urls)} โพสต์")
    for idx, p_url in enumerate(active_urls, 1):
        print(f"   [{idx}] {p_url}")
    print(f"⏱️ รอบการตรวจสอบ: ทุกๆ ~{CHECK_INTERVAL} วินาที")
    if OPERATING_HOURS:
        print(f"⏰ เวลาทำการร้าน: {OPERATING_HOURS}")
    if SEND_IDLE_STATUS:
        print("📱 อัปเดตสถานะเข้า Telegram: ส่งทุกรอบ (แบบไร้เสียง)")
    if USE_AI and GEMINI_API_KEY:
        print("🤖 โหมดการวิเคราะห์: AI (Google Gemini Flash)")
    else:
        print("🔍 โหมดการวิเคราะห์: Rule-based (ตรวจจับคำว่า 'รับออเดอร์' ในเครื่อง)")

    # เริ่มเธรดเฝ้ารับคำสั่งจาก Telegram ในโหมด watch
    if not once:
        def _bg_tg_listener():
            import time
            from telegram_bridge import check_pending_post_command, execute_telegram_post_task
            time.sleep(5)
            while True:
                try:
                    task = check_pending_post_command()
                    if task:
                        print(f"\n[*] 🤖 ได้รับคำสั่งสร้างโพสต์จาก Telegram ({task.get('command')} ปิด {task.get('close_time', '20.00')} น.)...")
                        res = execute_telegram_post_task(task)
                        if res.get("success"):
                            print("[✓] อัปเดตโพสต์ใหม่เรียบร้อยแล้ว กำลังสลับไปเฝ้าดูโพสต์ใหม่...")
                except Exception:
                    pass
                time.sleep(6)
        import threading
        threading.Thread(target=_bg_tg_listener, daemon=True).start()
    auto_reply_on, auto_reply_txt = get_auto_reply_settings(reload_env=True)
    if auto_reply_on:
        print(f"💬 ตอบกลับอัตโนมัติบน FB: เปิดใช้งาน (ข้อความ: \"{auto_reply_txt}\")")
    else:
        print("💬 ตอบกลับอัตโนมัติบน FB: ปิดการใช้งาน")
    print("="*60 + "\n")

    notified_cache = load_cache()
    print(f"[*] โหลดประวัติที่เคยแจ้งเตือนแล้ว: {len(notified_cache)} รายการ")

    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.new_page()

        try:
            # ตรวจสอบเบื้องต้นว่าติดหน้า Login หรือไม่ด้วยโพสต์แรก
            first_url = active_urls[0] if active_urls else "https://www.facebook.com"
            print("[*] กำลังเปิดหน้า Facebook เพื่อตรวจสอบสถานะการล็อกอิน...")
            page.goto(first_url, wait_until="domcontentloaded")
            time.sleep(3)

            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("\n[!] ระบบพบว่าบัญชีของคุณยังไม่ได้ล็อกอิน Facebook")
                print("👉 กรุณารันคำสั่ง: python main.py --login เพื่อล็อกอินก่อน 1 ครั้งครับ\n")
                return

            round_count = 1
            while True:
                try:
                    # ตรวจสอบและเคลียร์ Trigger Flag หากมีค้างอยู่
                    if TRIGGER_FILE.exists():
                        try:
                            TRIGGER_FILE.unlink(missing_ok=True)
                        except Exception:
                            pass

                    # โหลดรายการ URL ล่าสุดจาก .env ทุกรอบ
                    latest_urls = get_post_urls(reload_env=True)
                    if latest_urls:
                        if latest_urls != active_urls:
                            print("\n" + "="*60)
                            print("🔄 [ตรวจพบลำดับลิงก์โพสต์ใหม่จาก GUI / .env!]")
                            print(f"📌 อัปเดตจำนวนโพสต์ใหม่: {len(latest_urls)} โพสต์")
                            for idx, p_url in enumerate(latest_urls, 1):
                                print(f"   [{idx}] {p_url}")
                            print("="*60)
                            active_urls = latest_urls
                    elif not active_urls:
                        print("\n[!] ยังไม่มี URL โพสต์ที่ถูกต้อง กำลังรอ URL จากหน้าต่างโปรแกรม...")
                        time.sleep(3)
                        continue

                    # 1. ตรวจสอบเวลาเปิด-ปิดร้าน
                    if not is_within_operating_hours():
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"🌙 [{now_str}] ขณะนี้อยู่นอกเวลาเปิดร้าน ({OPERATING_HOURS}) พักการตรวจชั่วคราว...")
                        for _ in range(120):
                            if TRIGGER_FILE.exists():
                                break
                            time.sleep(1)
                        continue

                    now_str = datetime.now().strftime("%H:%M:%S")
                    print(f"\n🔄 [รอบที่ {round_count} - {now_str}] เริ่มตรวจเช็คทั้งหมด {len(active_urls)} โพสต์...")

                    total_new_alerts = 0
                    interrupted_during_posts = False

                    for p_idx, post_url in enumerate(active_urls, 1):
                        # ตรวจสอบระหว่างโพสต์ว่ามีคำสั่งสลับลิงก์ด่วนหรือไม่
                        if TRIGGER_FILE.exists():
                            print("\n⚡ [ตรวจพบสัญญาณขอสลับลิงก์ทันที] กำลังเปลี่ยนไปยังโพสต์ชุดใหม่...")
                            interrupted_during_posts = True
                            break

                        prefix = f"[โพสต์ที่ {p_idx}/{len(active_urls)}]" if len(active_urls) > 1 else ""
                        print(f"\n   📄 {prefix} กำลังตรวจโพสต์: {post_url}")

                        try:
                            page.goto(post_url, timeout=45000, wait_until="domcontentloaded")
                        except Exception as err:
                            print(f"      [!] เปิดหน้าโพสต์ไม่สำเร็จ ({err}) ข้ามไปยังโพสต์ถัดไป...")
                            continue

                        # 2. ดึงคอมเมนต์
                        post_author, comments = extract_comments_from_page(page, post_url=post_url)
                        print(f"      📊 ตรวจพบ {len(comments)} เธรดคอมเมนต์ (เจ้าของโพสต์: {post_author or 'ตรวจจับอัตโนมัติ'})")
                        for c in comments:
                            snippet = c.get('text', '').replace('\n', ' ')[:45]
                            r_count = len(c.get('replies', []))
                            print(f"         💬 [{c.get('author', 'ลูกค้า')}] \"{snippet}\" (คำตอบกลับ: {r_count})")

                        if comments:
                            # 3. วิเคราะห์หาออเดอร์ที่ยังไม่ได้รับ
                            unreplied_orders = analyze_comments(comments, post_author=post_author)
                            for item in unreplied_orders:
                                c_id = item.get("id")
                                if c_id not in notified_cache:
                                    notify_unreplied_order(
                                        customer_name=item.get("customer_name", "ลูกค้า"),
                                        comment_text=item.get("text", ""),
                                        reason=item.get("reason", ""),
                                        post_url=post_url
                                    )
                                    notified_cache.add(c_id)
                                    total_new_alerts += 1

                                    # ตอบรับออเดอร์อัตโนมัติบน Facebook (ถ้าเปิดใช้งาน)
                                    auto_reply_enabled, auto_reply_template = get_auto_reply_settings(reload_env=True)
                                    if auto_reply_enabled:
                                        print(f"      💬 กำลังตอบกลับคอมเมนต์ลูกค้า \"{item.get('customer_name')}\" บน Facebook...")
                                        replied = reply_to_facebook_comment(
                                            page=page,
                                            customer_name=item.get("customer_name", ""),
                                            comment_text=item.get("text", ""),
                                            reply_message=auto_reply_template
                                        )
                                        if replied:
                                            print(f"      [✓] ตอบกลับคอมเมนต์ลูกค้า \"{item.get('customer_name')}\" บน Facebook เรียบร้อยแล้ว!")
                                        else:
                                            print(f"      [!] ไม่สามารถตอบกลับคอมเมนต์ลูกค้า \"{item.get('customer_name')}\" อัตโนมัติได้")
                                        time.sleep(1.5)

                        if p_idx < len(active_urls):
                            time.sleep(2)

                    if interrupted_during_posts:
                        continue

                    if total_new_alerts > 0:
                        save_cache(notified_cache)
                        print(f"\n   🚨 แจ้งเตือนออเดอร์ค้างตอบใหม่ในรอบนี้: {total_new_alerts} รายการ")
                    else:
                        print(f"\n   ✅ ตรวจสอบครบทุกโพสต์แล้ว: ออเดอร์ทั้งหมดได้รับการตอบรับแล้ว หรือไม่มีออเดอร์ใหม่")
                        if SEND_IDLE_STATUS:
                            short_time = datetime.now().strftime("%H:%M")
                            post_count_str = f" ({len(active_urls)} โพสต์)" if len(active_urls) > 1 else ""
                            send_telegram_status(f"✅ ตรวจสอบแล้ว ({short_time}): ไม่มีออเดอร์ใหม่{post_count_str}")

                    if once:
                        print("\n[✓] ตรวจสอบรอบเดียวเรียบร้อยแล้ว ปิดการทำงาน")
                        break

                    # สุ่มหน่วงเวลาเล็กน้อยเพื่อความปลอดภัย ป้องกัน Bot Detection
                    current_interval = get_check_interval(reload_env=True)
                    jitter = random.randint(-5, 10)
                    sleep_time = max(30, current_interval + jitter)
                    print(f"\n   ⏳ รออีก {sleep_time} วินาทีก่อนตรวจเช็ครอบถัดไป... (แก้ไขลิงก์ใน GUI แล้วกดอัปเดตเพื่อตรวจทันทีได้ตลอดเวลา)")

                    # นับถอยหลังเป็นวินาที พร้อมดักจับ Trigger File หรือ URL Change
                    sleep_start = time.time()
                    last_printed_sec = -1
                    while (time.time() - sleep_start) < sleep_time:
                        if TRIGGER_FILE.exists():
                            try:
                                TRIGGER_FILE.unlink(missing_ok=True)
                            except Exception:
                                pass
                            print("\n⚡ [ตรวจพบสัญญาณอัปเดตจาก GUI] ข้ามเวลารอและเริ่มตรวจโพสต์ใหม่ทันที!")
                            break

                        elapsed = int(time.time() - sleep_start)
                        # เช็ค .env ทุกๆ 3 วินาที เผื่อผู้ใช้บันทึกไฟล์ .env โดยตรง
                        if elapsed > 0 and elapsed % 3 == 0 and elapsed != last_printed_sec:
                            chk_urls = get_post_urls(reload_env=True)
                            if chk_urls and chk_urls != active_urls:
                                print("\n⚡ [ตรวจพบการเปลี่ยน URL ใน .env] ข้ามเวลารอและเริ่มตรวจโพสต์ใหม่ทันที!")
                                break

                        remaining = int(sleep_time - elapsed)
                        if remaining > 0 and remaining % 30 == 0 and remaining != last_printed_sec:
                            last_printed_sec = remaining
                            print(f"      ...จะตรวจรอบถัดไปในอีก {remaining} วินาที... (หรือกดอัปเดตใน GUI เพื่อเริ่มทันที)")

                        time.sleep(1)

                    round_count += 1

                except KeyboardInterrupt:
                    raise
                except Exception as err:
                    print(f"\n[!] เกิดข้อผิดพลาดในการตรวจสอบรอบนี้: {err}")
                    print("   ⏳ รอ 20 วินาทีก่อนลองรอบถัดไป...")
                    for _ in range(20):
                        if TRIGGER_FILE.exists():
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            print("\n[!] ผู้ใช้สั่งหยุดการทำงาน (Ctrl+C)")
        finally:
            try:
                context.close()
            except Exception:
                pass
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
    parser.add_argument("--test-order", action="store_true", help="ส่งทดสอบออเดอร์เข้า Telegram โดยระบุชื่อและคอมเมนต์")
    parser.add_argument("--name", type=str, default="", help="ชื่อลูกค้าสำหรับการทดสอบ (ใช้ร่วมกับ --test-order)")
    parser.add_argument("--comment", type=str, default="", help="ข้อความคอมเมนต์สำหรับการทดสอบ (ใช้ร่วมกับ --test-order)")
    parser.add_argument("--post", "--create-post", dest="create_post", action="store_true", help="สร้างและเผยแพร่โพสต์เปิดร้านลงกลุ่ม Facebook อัตโนมัติ")
    parser.add_argument("--post-date", type=str, default="", help="ระบุวันที่สำหรับโพสต์ (เช่น 'อาทิตย์ 1/11/69') หากไม่ระบุจะใช้วันนี้")
    parser.add_argument("--close-time", type=str, default="20.00", help="ระบุเวลารับออเดอร์ถึง (เช่น '20.00' หรือ '20.30') ค่าเริ่มต้นคือ 20.00")
    parser.add_argument("--post-preview", action="store_true", help="สร้างภาพตัวอย่างโพสต์ลงไฟล์ preview_post.png โดยยังไม่กดเผยแพร่")
    parser.add_argument("--post-group", type=str, default="", help="ระบุ Group ID หรือ URL กลุ่ม Facebook สำหรับโพสต์")
    parser.add_argument("--auto-watch", action="store_true", help="เริ่มเฝ้าดูคอมเมนต์ทันทีหลังจากโพสต์เสร็จสิ้น")
    parser.add_argument("--listen-telegram", action="store_true", help="รันบริการเฝ้ารอรับคำสั่งสร้างโพสต์จาก Telegram เบื้องหลัง")

    args = parser.parse_args()

    if args.login:
        manual_login()
    elif args.test_notify:
        test_notification()
    elif args.clear_cache:
        clear_cache()
    elif args.telegram_setup:
        setup_telegram()
    elif args.test_order:
        test_order(customer_name=args.name, comment_text=args.comment)
    elif args.listen_telegram:
        import time
        from telegram_bridge import check_pending_post_command, execute_telegram_post_task
        print("\n" + "=" * 60)
        print("🤖 เริ่มบริการเฝ้ารอรับคำสั่งสร้างโพสต์จาก Telegram...")
        print("📱 เมื่อพิมพ์ /post ใน Telegram บอทจะทำการสร้างโพสต์ให้อัตโนมัติ")
        print("=" * 60 + "\n")
        while True:
            try:
                task = check_pending_post_command()
                if task:
                    print(f"\n[*] 🤖 ตรวจพบคำสั่งจาก Telegram: {task.get('command')} (ปิด {task.get('close_time', '20.00')} น.)")
                    execute_telegram_post_task(task)
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาด: {e}")
            time.sleep(5)
    elif args.create_post or args.post_preview:
        from fb_poster import (
            get_default_template, format_post_text, get_default_post_images,
            publish_facebook_group_post, update_env_post_url
        )
        from config import GROUP_ID
        group_target = args.post_group.strip() or GROUP_ID or "1111870942162462"
        tmpl = get_default_template()
        content_txt = format_post_text(tmpl, custom_date_str=args.post_date, close_time=args.close_time)
        images = get_default_post_images()

        print("\n" + "=" * 60)
        if args.post_preview:
            print("👁 สร้างภาพตัวอย่างโพสต์ Facebook...")
        else:
            print("📢 กำลังสร้างและเผยแพร่โพสต์ลงกลุ่ม Facebook...")
        print(f"📌 กลุ่มเป้าหมาย: {group_target}")
        print(f"🖼 จำนวนรูปภาพแนบ: {len(images)} รูป")
        print("=" * 60 + "\n")

        res = publish_facebook_group_post(
            group_id_or_url=group_target,
            content=content_txt,
            image_paths=images,
            headless=True,
            preview_only=args.post_preview
        )
        if res.get("success"):
            if args.post_preview:
                print(f"\n[✓] สร้างภาพตัวอย่างสำเร็จ: {res.get('preview_image')}")
            else:
                post_url = res.get("post_url")
                print(f"\n[✓] เผยแพร่โพสต์สำเร็จ! ลิงก์โพสต์: {post_url}")
                if post_url and "posts" in post_url:
                    update_env_post_url(post_url)
                    print("👉 อัปเดต POST_URL ใน .env เรียบร้อยแล้ว")
                if args.auto_watch:
                    print("\n🚀 เริ่มเข้าสู่โหมดเฝ้าดูคอมเมนต์ทันที...")
                    run_monitor(once=False)
        else:
            print(f"\n[!] การโพสต์ไม่สำเร็จ: {res.get('error')}")
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
        print("  4. python main.py --post            # สร้างและโพสต์เปิดร้านลงกลุ่ม Facebook")
        print("  5. python main.py --post-preview    # ดูภาพตัวอย่างโพสต์ก่อนส่งจริง")
        print("  6. python main.py --listen-telegram # เฝ้ารอรับคำสั่ง /post จาก Telegram")
        print("  7. python main.py --test-order      # ทดสอบส่งออเดอร์เข้า Telegram")
        print("  8. python main.py --test-order --name \"คุณสมชาย\" --comment \"ทาโกะยากิ 1 กล่อง\"")

if __name__ == "__main__":
    main()
