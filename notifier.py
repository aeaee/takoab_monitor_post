import os
import sys
import subprocess
import json
import threading
import webbrowser
import requests
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    CACHE_FILE, NOTIFICATION_STYLE, NOTIFICATION_DURATION, 
    POST_URL, IS_WINDOWS, IS_MAC, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_CHAT_IDS
)

def load_cache() -> set:
    """โหลดรายการ comment_id ที่เคยแจ้งเตือนไปแล้ว"""
    if not CACHE_FILE.exists():
        return set()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("notified_ids", []))
    except Exception:
        return set()

def save_cache(notified_ids: set):
    """บันทึกรายการ comment_id ลงไฟล์แคช"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_updated": datetime.now().isoformat(),
                "notified_ids": list(notified_ids)
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] ไม่สามารถบันทึกแคชได้: {e}")

def play_alert_sound():
    """เล่นเสียงแจ้งเตือน (รองรับทั้ง Windows และ macOS)"""
    try:
        if IS_WINDOWS:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        elif IS_MAC:
            sound_path = "/System/Library/Sounds/Glass.aiff"
            subprocess.Popen(["afplay", sound_path], stderr=subprocess.DEVNULL)
    except Exception:
        pass

def send_system_banner(title: str, subtitle: str, message: str):
    """ส่งแบนเนอร์แจ้งเตือนตามระบบปฏิบัติการ"""
    if IS_MAC:
        clean_title = title.replace('"', '\\"')
        clean_sub = subtitle.replace('"', '\\"')
        clean_msg = message.replace('"', '\\"').replace('\n', ' ')
        script = f'display notification "{clean_msg}" with title "{clean_title}" subtitle "{clean_sub}" sound name "Glass"'
        try:
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception:
            pass
    elif IS_WINDOWS:
        # บน Windows ส่งผ่าน PowerShell Toast Notification
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message[:100]}")) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Facebook Group Monitor").Show($toast)
        '''
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script], stderr=subprocess.DEVNULL)
        except Exception:
            pass

def show_modal_dialog(customer_name: str, message: str, duration: int = 60, post_url: str = ""):
    """
    เด้งหน้าต่างแจ้งเตือน Modal ค้างไว้จนกว่าจะกดปุ่ม หรือหมดเวลา
    (รองรับทั้ง Windows MessageBox และ macOS Dialog)
    """
    target_url = post_url or POST_URL

    def _run():
        if IS_MAC:
            clean_name = customer_name.replace('"', '\\"')
            clean_msg = message.replace('"', '\\"').replace('\r', '')[:250]
            dialog_text = f"👤 ลูกค้า: {clean_name}\\n💬 ข้อความ:\\n{clean_msg}"
            if duration > 0:
                dialog_text += f"\\n\\n(หน้าต่างนี้จะปิดอัตโนมัติใน {duration} วินาที หากไม่มีการกดปุ่ม)"

            give_up_part = f" giving up after {duration}" if duration > 0 else ""
            open_cmd = f'open location "{target_url}"' if target_url else ""
            script = f'''
            tell application "System Events"
                activate
                set res to display dialog "{dialog_text}" with title "🚨 มีออเดอร์ใหม่ยังไม่ได้ตอบ!" buttons {{"เปิดดูโพสต์", "รับทราบ"}} default button "รับทราบ" with icon caution{give_up_part}
                if button returned of res is "เปิดดูโพสต์" then
                    {open_cmd}
                end if
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", script], check=False)
            except Exception:
                pass

        elif IS_WINDOWS:
            try:
                import ctypes
                # 0x40 = MB_ICONINFORMATION, 0x1 = MB_OKCANCEL
                clean_text = f"ลูกค้า: {customer_name}\n\nข้อความ:\n{message[:250]}\n\n(กด OK เพื่อเปิดดูโพสต์, Cancel เพื่อปิด)"
                res = ctypes.windll.user32.MessageBoxW(0, clean_text, "🚨 มีออเดอร์ใหม่ยังไม่ได้ตอบ!", 0x40 | 0x1)
                # 1 = IDOK
                if res == 1 and target_url:
                    webbrowser.open(target_url)
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()

def send_telegram_alert(customer_name: str, message: str, reason: str = "", post_url: str = "", sync: bool = False):
    """ส่งการแจ้งเตือนเข้า Telegram ทุกแชท/กลุ่มที่ระบุไว้"""
    if not TELEGRAM_BOT_TOKEN:
        print("[!] ไม่พบ TELEGRAM_BOT_TOKEN ใน .env")
        return
    if not TELEGRAM_CHAT_IDS:
        print("[!] ไม่พบ TELEGRAM_CHAT_ID ใน .env")
        return

    import html
    escaped_msg = html.escape(message)
    escaped_name = html.escape(customer_name)
    post_link_part = f'\n\n👉 <a href="{post_url}">🔗 <b>กดที่นี่เพื่อเปิดดูโพสต์บน Facebook</b></a>' if post_url else ""

    text = (
        f"🚨 <b>มีออเดอร์ใหม่เข้ามาครับ!</b>\n\n"
        f"👤 <b>ลูกค้า:</b> {escaped_name}\n"
        f"💬 <b>รายการที่สั่ง</b>\n"
        f"{escaped_msg}"
        f"{post_link_part}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def _send():
        for cid in TELEGRAM_CHAT_IDS:
            payload = {
                "chat_id": cid,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    print(f"   📱 ส่งแจ้งเตือนเข้า Telegram ({cid}) เรียบร้อยแล้ว!")
                else:
                    print(f"[!] ส่ง Telegram ({cid}) ไม่สำเร็จ ({resp.status_code}): {resp.text}")
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาดในการส่ง Telegram ({cid}): {e}")

    if sync:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()

def send_telegram_status(status_text: str, sync: bool = False):
    """ส่งข้อความสถานะปกติเข้า Telegram ทุกแชทแบบไร้เสียง (Silent Message ไม่สั่น/ไม่ส่งเสียงรบกวน)"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def _send():
        for cid in TELEGRAM_CHAT_IDS:
            payload = {
                "chat_id": cid,
                "text": status_text,
                "parse_mode": "HTML",
                "disable_notification": True
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    print(f"   📱 ส่งสถานะเข้า Telegram ({cid}) เรียบร้อยแล้ว")
                else:
                    print(f"[!] ส่งสถานะ Telegram ({cid}) ไม่สำเร็จ ({resp.status_code}): {resp.text}")
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาดในการส่งสถานะ Telegram ({cid}): {e}")

    if sync:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()


def send_pos_draft_order(customer_name: str, comment_text: str, post_url: str = "", reason: str = ""):
    """
    ส่งข้อมูลออเดอร์ไปที่ Takoab POS เพื่อสร้างร่างออเดอร์เข้า Telegram ในข้อความเดียว
    (รวมทั้งคอมเมนต์ต้นฉบับ ลิงก์โพสต์ รายการอาหาร และปุ่มกดอนุมัติเข้าครัว/ไม่อนุมัติ)
    หากเชื่อมต่อ POS ไม่สำเร็จ จะ fallback ส่งแบบแจ้งเตือนธรรมดาแทนอัตโนมัติ
    """
    pos_api_url = os.getenv("POS_DRAFT_API_URL", "https://takoab-api.aeaee.one/api/orders/telegram-draft").strip()

    def _send():
        target_cids = TELEGRAM_CHAT_IDS if TELEGRAM_CHAT_IDS else ([TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else [])
        if not target_cids:
            return

        success = False
        for cid in target_cids:
            payload = {
                "comment": comment_text,
                "customer_name": customer_name,
                "post_url": post_url,
                "bot_token": TELEGRAM_BOT_TOKEN,
                "chat_id": cid
            }
            try:
                resp = requests.post(
                    pos_api_url,
                    json=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "TakoabMonitor/1.0"},
                    timeout=15
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    print(f"   🤖 ส่งร่างออเดอร์เข้า Telegram ({cid}) เรียบร้อย (Draft ID: {res_data.get('draft_id')})")
                    success = True
                else:
                    print(f"[!] POS Draft API ตอบกลับสถานะ {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาดในการส่งร่างออเดอร์ไปที่ POS ({cid}): {e}")

        if not success:
            print("   ⚠️ ส่งร่างออเดอร์เข้า POS ไม่สำเร็จ กำลัง fallback ส่งการแจ้งเตือนปกติแทน...")
            send_telegram_alert(customer_name, comment_text, reason=reason, post_url=post_url, sync=True)

    threading.Thread(target=_send, daemon=True).start()


def notify_unreplied_order(customer_name: str, comment_text: str, reason: str = "", post_url: str = ""):
    """ส่งการแจ้งเตือนเมื่อพบออเดอร์ที่ยังไม่มีการตอบรับ"""
    now_str = datetime.now().strftime("%H:%M:%S")
    title = "🚨 มีออเดอร์ใหม่ยังไม่ได้รับ!"
    subtitle = f"ลูกค้า: {customer_name} ({now_str})"

    print("\n" + "="*50)
    print(f"🔔 [{now_str}] แจ้งเตือนออเดอร์ที่ยังไม่ได้รับ:")
    print(f"   👤 ลูกค้า: {customer_name}")
    print(f"   💬 ข้อความ: {comment_text}")
    if reason:
        print(f"   ℹ️ เหตุผล: {reason}")
    if post_url:
        print(f"   🔗 โพสต์: {post_url}")
    print("="*50 + "\n")

    # 1. เล่นเสียงเตือน
    play_alert_sound()

    # 2. ส่งแบนเนอร์มุมจอ
    if NOTIFICATION_STYLE in ["banner", "both"]:
        send_system_banner(title, subtitle, comment_text)

    # 3. เด้งหน้าต่างค้างไว้บนหน้าจอ
    if NOTIFICATION_STYLE in ["dialog", "both"]:
        show_modal_dialog(customer_name, comment_text, duration=NOTIFICATION_DURATION, post_url=post_url)

    # 4. รวมการแจ้งเตือนเข้า Telegram เหลือข้อความเดียว (พร้อมคอมเมนต์ต้นฉบับ ลิงก์โพสต์ และปุ่มอนุมัติ)
    send_pos_draft_order(customer_name, comment_text, post_url=post_url, reason=reason)
