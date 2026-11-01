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
    """เธ—เธ”เธชเธญเธเธฃเธฐเธเธเนเธเนเธเน€เธ•เธทเธญเธเนเธฅเธฐเน€เธชเธตเธขเธ (เธฃเธญเธเธฃเธฑเธเธ—เธฑเนเธ Windows เนเธฅเธฐ macOS)"""
    print("[*] เธเธณเธฅเธฑเธเธ—เธ”เธชเธญเธเธชเนเธเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธเนเธฅเธฐเน€เธฅเนเธเน€เธชเธตเธขเธ...")
    play_alert_sound()
    send_system_banner(
        title="๐จ เธ—เธ”เธชเธญเธเนเธเนเธเน€เธ•เธทเธญเธเธญเธญเน€เธ”เธญเธฃเน",
        subtitle="เธฃเธฐเธเธ Facebook Group Monitor",
        message="เธ–เนเธฒเธเธธเธ“เน€เธซเนเธเธเนเธญเธเธญเธฑเธเนเธฅเธฐเนเธ”เนเธขเธดเธเน€เธชเธตเธขเธ เนเธชเธ”เธเธงเนเธฒเธฃเธฐเธเธเนเธเนเธเน€เธ•เธทเธญเธเธเธฃเนเธญเธกเธ—เธณเธเธฒเธ 100%!"
    )
    show_modal_dialog(
        customer_name="เธเธธเธ“เธชเธกเธเธฒเธข (เธ—เธ”เธชเธญเธ)",
        message="เธชเธฑเนเธเธ—เธฒเนเธเธฐเธขเธฒเธเธด 2 เธเธฅเนเธญเธ\n(เธ—เธ”เธชเธญเธเธฃเธฐเธเธเธซเธเนเธฒเธ•เนเธฒเธเนเธเนเธเน€เธ•เธทเธญเธ)",
        duration=15
    )
    print("[*] เธเธณเธฅเธฑเธเธชเนเธเนเธเนเธเน€เธ•เธทเธญเธเธญเธญเน€เธ”เธญเธฃเนเธ—เธ”เธชเธญเธเน€เธเนเธฒ Telegram...")
    send_telegram_alert(
        customer_name="เธเธธเธ“เธชเธกเธเธฒเธข (เธ—เธ”เธชเธญเธเธฃเธฐเธเธ)",
        message="เธชเธฑเนเธเธ—เธฒเนเธเธฐเธขเธฒเธเธด 2 เธเธฅเนเธญเธ\n(เธเนเธญเธเธงเธฒเธกเธ—เธ”เธชเธญเธเนเธเนเธเน€เธ•เธทเธญเธเธเธฒเธ Takoab Monitor)",
        reason="เธ—เธ”เธชเธญเธเธฃเธฐเธเธเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธ",
        sync=True
    )
    send_telegram_status("๐งช <b>เธ—เธ”เธชเธญเธเธเนเธญเธเธงเธฒเธกเธชเธ–เธฒเธเธฐเธเธเธ•เธด (เนเธเธเนเธฃเนเน€เธชเธตเธขเธ)</b> เธชเธณเน€เธฃเนเธเน€เธฃเธตเธขเธเธฃเนเธญเธข!", sync=True)
    print("[โ“] เธชเนเธเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธเธ—เธ”เธชเธญเธเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")

def test_order(customer_name: str = "", comment_text: str = ""):
    """เธ—เธ”เธชเธญเธเธชเนเธเธญเธญเน€เธ”เธญเธฃเนเน€เธเนเธฒ Telegram เน€เธเธทเนเธญเธ—เธ”เธชเธญเธเธเธฒเธฃเธ—เธณเธเธฒเธเธเธญเธเธเธณเธ–เธฒเธกเนเธ•เนเธ•เธญเธเนเธฅเธฐเธฃเนเธฒเธเธญเธญเน€เธ”เธญเธฃเน"""
    name = customer_name.strip() or "เธ—เธ”เธชเธญเธ เธฅเธนเธเธเนเธฒ Facebook"
    comment = comment_text.strip() or "เธกเธฒเธกเนเธฒเนเธเนเธเธฃเธญเธเธเธฅเธธเธเธเธญเธช เนเธกเนเน€เธเนเธ” (เนเธขเธเธชเธฒเธซเธฃเนเธฒเธข) 2 เนเธเนเธเธฃเธญเธเธเธฅเธธเธเธเธญเธชเน€เธเธฒเธซเธฅเธต 1 194/119 เธ.6/2 เนเธเนเนเธ—เธขเธเธฅเธฑเธชเธเนเธฐ"

    print("\n" + "=" * 60)
    print("๐งช เน€เธฃเธดเนเธกเธ—เธ”เธชเธญเธเธชเนเธเธญเธญเน€เธ”เธญเธฃเนเน€เธเนเธฒ Telegram")
    print(f"๐‘ค เธเธทเนเธญเธฅเธนเธเธเนเธฒ: {name}")
    print(f"๐’ฌ เธเนเธญเธเธงเธฒเธกเธเธญเธกเน€เธกเธเธ•เน: {comment}")
    print("=" * 60)
    print("[*] เธเธณเธฅเธฑเธเธชเนเธเธเนเธญเธกเธนเธฅเนเธเธขเธฑเธ POS Telegram Draft API...")

    res = send_pos_draft_order(customer_name=name, comment_text=comment, reason="เธ—เธ”เธชเธญเธเธฃเธฐเธเธ Telegram Draft", sync=True)
    if res and res.get("success"):
        draft_id = res.get("draft_id", "-")
        print(f"\n[โ“] เธชเธฃเนเธฒเธเธฃเนเธฒเธเธญเธญเน€เธ”เธญเธฃเนเน€เธเนเธฒ Telegram เธชเธณเน€เธฃเนเธ! (Draft ID: {draft_id})")
        print("๐‘ เธเธฃเธธเธ“เธฒเน€เธเธดเธ”เนเธญเธ Telegram เน€เธเธทเนเธญเธ—เธ”เธชเธญเธเธ•เธญเธเธเธณเธ–เธฒเธกเนเธฅเธฐเธขเธทเธเธขเธฑเธเธญเธญเน€เธ”เธญเธฃเนเนเธ”เนเธ—เธฑเธเธ—เธต")
    else:
        err = res.get("error") if res else "เน€เธเธดเธ”เธเนเธญเธเธดเธ”เธเธฅเธฒเธ”"
        print(f"\n[!] เธชเนเธเธญเธญเน€เธ”เธญเธฃเนเธ—เธ”เธชเธญเธเนเธกเนเธชเธณเน€เธฃเนเธ: {err}")


def run_monitor(once: bool = False):
    """เธฃเธฑเธเธฃเธฐเธเธเน€เธเนเธฒเธ”เธนเธเธญเธกเน€เธกเธเธ•เนเนเธเนเธเธชเธ•เน (เธฃเธญเธเธฃเธฑเธเธซเธฅเธฒเธขเนเธเธชเธ•เน เนเธฅเธฐเธฃเธญเธเธฃเธฑเธเน€เธเธฅเธตเนเธขเธ/เธชเธฅเธฑเธเธฅเธดเธเธเนเธ—เธฑเธเธ—เธตเนเธเธ Realtime)"""
    active_urls = get_post_urls(reload_env=True)
    if not active_urls:
        active_urls = POST_URLS

    if not active_urls:
        print("\n[!] เธขเธฑเธเนเธกเนเนเธ”เนเธฃเธฐเธเธธ POST_URL เธซเธฃเธทเธญเนเธกเนเธกเธต URL เธ—เธตเนเธ–เธนเธเธ•เนเธญเธ")
        print("๐‘ เธเธฃเธธเธ“เธฒเน€เธเธดเธ”เนเธเธฅเน .env เธซเธฃเธทเธญเธฃเธฐเธเธธเธฅเธดเธเธเนเนเธเธซเธเนเธฒเธ•เนเธฒเธเนเธเธฃเนเธเธฃเธก (GUI) เนเธฅเนเธงเธเธฑเธเธ—เธถเธ/เธญเธฑเธเน€เธ”เธ•\n")
        return

    print("\n" + "="*60)
    print("๐€ เน€เธฃเธดเนเธกเธฃเธฐเธเธเน€เธเนเธฒเธ”เธนเธเธญเธกเน€เธกเธเธ•เนเนเธเธชเธ•เน Facebook")
    print(f"๐“ เธเธณเธเธงเธเนเธเธชเธ•เนเธ—เธตเนเน€เธเนเธฒเธ”เธน: {len(active_urls)} เนเธเธชเธ•เน")
    for idx, p_url in enumerate(active_urls, 1):
        print(f"   [{idx}] {p_url}")
    print(f"โฑ๏ธ เธฃเธญเธเธเธฒเธฃเธ•เธฃเธงเธเธชเธญเธ: เธ—เธธเธเน ~{CHECK_INTERVAL} เธงเธดเธเธฒเธ—เธต")
    if OPERATING_HOURS:
        print(f"โฐ เน€เธงเธฅเธฒเธ—เธณเธเธฒเธฃเธฃเนเธฒเธ: {OPERATING_HOURS}")
    if SEND_IDLE_STATUS:
        print("๐“ฑ เธญเธฑเธเน€เธ”เธ•เธชเธ–เธฒเธเธฐเน€เธเนเธฒ Telegram: เธชเนเธเธ—เธธเธเธฃเธญเธ (เนเธเธเนเธฃเนเน€เธชเธตเธขเธ)")
    if USE_AI and GEMINI_API_KEY:
        print("๐ค– เนเธซเธกเธ”เธเธฒเธฃเธงเธดเน€เธเธฃเธฒเธฐเธซเน: AI (Google Gemini Flash)")
    else:
        print("๐” เนเธซเธกเธ”เธเธฒเธฃเธงเธดเน€เธเธฃเธฒเธฐเธซเน: Rule-based (เธ•เธฃเธงเธเธเธฑเธเธเธณเธงเนเธฒ 'เธฃเธฑเธเธญเธญเน€เธ”เธญเธฃเน' เนเธเน€เธเธฃเธทเนเธญเธ)")
    auto_reply_on, auto_reply_txt = get_auto_reply_settings(reload_env=True)
    if auto_reply_on:
        print(f"๐’ฌ เธ•เธญเธเธเธฅเธฑเธเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเธเธ FB: เน€เธเธดเธ”เนเธเนเธเธฒเธ (เธเนเธญเธเธงเธฒเธก: \"{auto_reply_txt}\")")
    else:
        print("๐’ฌ เธ•เธญเธเธเธฅเธฑเธเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเธเธ FB: เธเธดเธ”เธเธฒเธฃเนเธเนเธเธฒเธ")
    print("="*60 + "\n")

    notified_cache = load_cache()
    print(f"[*] เนเธซเธฅเธ”เธเธฃเธฐเธงเธฑเธ•เธดเธ—เธตเนเน€เธเธขเนเธเนเธเน€เธ•เธทเธญเธเนเธฅเนเธง: {len(notified_cache)} เธฃเธฒเธขเธเธฒเธฃ")

    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.new_page()

        try:
            # เธ•เธฃเธงเธเธชเธญเธเน€เธเธทเนเธญเธเธ•เนเธเธงเนเธฒเธ•เธดเธ”เธซเธเนเธฒ Login เธซเธฃเธทเธญเนเธกเนเธ”เนเธงเธขเนเธเธชเธ•เนเนเธฃเธ
            first_url = active_urls[0] if active_urls else "https://www.facebook.com"
            print("[*] เธเธณเธฅเธฑเธเน€เธเธดเธ”เธซเธเนเธฒ Facebook เน€เธเธทเนเธญเธ•เธฃเธงเธเธชเธญเธเธชเธ–เธฒเธเธฐเธเธฒเธฃเธฅเนเธญเธเธญเธดเธ...")
            page.goto(first_url, wait_until="domcontentloaded")
            time.sleep(3)

            if "login" in page.url or page.locator("input[name='email']").is_visible():
                print("\n[!] เธฃเธฐเธเธเธเธเธงเนเธฒเธเธฑเธเธเธตเธเธญเธเธเธธเธ“เธขเธฑเธเนเธกเนเนเธ”เนเธฅเนเธญเธเธญเธดเธ Facebook")
                print("๐‘ เธเธฃเธธเธ“เธฒเธฃเธฑเธเธเธณเธชเธฑเนเธ: python main.py --login เน€เธเธทเนเธญเธฅเนเธญเธเธญเธดเธเธเนเธญเธ 1 เธเธฃเธฑเนเธเธเธฃเธฑเธ\n")
                return

            round_count = 1
            while True:
                try:
                    # เธ•เธฃเธงเธเธชเธญเธเนเธฅเธฐเน€เธเธฅเธตเธขเธฃเน Trigger Flag เธซเธฒเธเธกเธตเธเนเธฒเธเธญเธขเธนเน
                    if TRIGGER_FILE.exists():
                        try:
                            TRIGGER_FILE.unlink(missing_ok=True)
                        except Exception:
                            pass

                    # เนเธซเธฅเธ”เธฃเธฒเธขเธเธฒเธฃ URL เธฅเนเธฒเธชเธธเธ”เธเธฒเธ .env เธ—เธธเธเธฃเธญเธ
                    latest_urls = get_post_urls(reload_env=True)
                    if latest_urls:
                        if latest_urls != active_urls:
                            print("\n" + "="*60)
                            print("๐” [เธ•เธฃเธงเธเธเธเธฅเธณเธ”เธฑเธเธฅเธดเธเธเนเนเธเธชเธ•เนเนเธซเธกเนเธเธฒเธ GUI / .env!]")
                            print(f"๐“ เธญเธฑเธเน€เธ”เธ•เธเธณเธเธงเธเนเธเธชเธ•เนเนเธซเธกเน: {len(latest_urls)} เนเธเธชเธ•เน")
                            for idx, p_url in enumerate(latest_urls, 1):
                                print(f"   [{idx}] {p_url}")
                            print("="*60)
                            active_urls = latest_urls
                    elif not active_urls:
                        print("\n[!] เธขเธฑเธเนเธกเนเธกเธต URL เนเธเธชเธ•เนเธ—เธตเนเธ–เธนเธเธ•เนเธญเธ เธเธณเธฅเธฑเธเธฃเธญ URL เธเธฒเธเธซเธเนเธฒเธ•เนเธฒเธเนเธเธฃเนเธเธฃเธก...")
                        time.sleep(3)
                        continue

                    # 1. เธ•เธฃเธงเธเธชเธญเธเน€เธงเธฅเธฒเน€เธเธดเธ”-เธเธดเธ”เธฃเนเธฒเธ
                    if not is_within_operating_hours():
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"๐ [{now_str}] เธเธ“เธฐเธเธตเนเธญเธขเธนเนเธเธญเธเน€เธงเธฅเธฒเน€เธเธดเธ”เธฃเนเธฒเธ ({OPERATING_HOURS}) เธเธฑเธเธเธฒเธฃเธ•เธฃเธงเธเธเธฑเนเธงเธเธฃเธฒเธง...")
                        for _ in range(120):
                            if TRIGGER_FILE.exists():
                                break
                            time.sleep(1)
                        continue

                    now_str = datetime.now().strftime("%H:%M:%S")
                    print(f"\n๐” [เธฃเธญเธเธ—เธตเน {round_count} - {now_str}] เน€เธฃเธดเนเธกเธ•เธฃเธงเธเน€เธเนเธเธ—เธฑเนเธเธซเธกเธ” {len(active_urls)} เนเธเธชเธ•เน...")

                    total_new_alerts = 0
                    interrupted_during_posts = False

                    for p_idx, post_url in enumerate(active_urls, 1):
                        # เธ•เธฃเธงเธเธชเธญเธเธฃเธฐเธซเธงเนเธฒเธเนเธเธชเธ•เนเธงเนเธฒเธกเธตเธเธณเธชเธฑเนเธเธชเธฅเธฑเธเธฅเธดเธเธเนเธ”เนเธงเธเธซเธฃเธทเธญเนเธกเน
                        if TRIGGER_FILE.exists():
                            print("\nโก [เธ•เธฃเธงเธเธเธเธชเธฑเธเธเธฒเธ“เธเธญเธชเธฅเธฑเธเธฅเธดเธเธเนเธ—เธฑเธเธ—เธต] เธเธณเธฅเธฑเธเน€เธเธฅเธตเนเธขเธเนเธเธขเธฑเธเนเธเธชเธ•เนเธเธธเธ”เนเธซเธกเน...")
                            interrupted_during_posts = True
                            break

                        prefix = f"[เนเธเธชเธ•เนเธ—เธตเน {p_idx}/{len(active_urls)}]" if len(active_urls) > 1 else ""
                        print(f"\n   ๐“ {prefix} เธเธณเธฅเธฑเธเธ•เธฃเธงเธเนเธเธชเธ•เน: {post_url}")

                        try:
                            page.goto(post_url, timeout=45000, wait_until="domcontentloaded")
                        except Exception as err:
                            print(f"      [!] เน€เธเธดเธ”เธซเธเนเธฒเนเธเธชเธ•เนเนเธกเนเธชเธณเน€เธฃเนเธ ({err}) เธเนเธฒเธกเนเธเธขเธฑเธเนเธเธชเธ•เนเธ–เธฑเธ”เนเธ...")
                            continue

                        # 2. เธ”เธถเธเธเธญเธกเน€เธกเธเธ•เน
                        post_author, comments = extract_comments_from_page(page, post_url=post_url)
                        print(f"      ๐“ เธ•เธฃเธงเธเธเธ {len(comments)} เน€เธเธฃเธ”เธเธญเธกเน€เธกเธเธ•เน (เน€เธเนเธฒเธเธญเธเนเธเธชเธ•เน: {post_author or 'เธ•เธฃเธงเธเธเธฑเธเธญเธฑเธ•เนเธเธกเธฑเธ•เธด'})")
                        for c in comments:
                            snippet = c.get('text', '').replace('\n', ' ')[:45]
                            r_count = len(c.get('replies', []))
                            print(f"         ๐’ฌ [{c.get('author', 'เธฅเธนเธเธเนเธฒ')}] \"{snippet}\" (เธเธณเธ•เธญเธเธเธฅเธฑเธ: {r_count})")

                        if comments:
                            # 3. เธงเธดเน€เธเธฃเธฒเธฐเธซเนเธซเธฒเธญเธญเน€เธ”เธญเธฃเนเธ—เธตเนเธขเธฑเธเนเธกเนเนเธ”เนเธฃเธฑเธ
                            unreplied_orders = analyze_comments(comments, post_author=post_author)
                            for item in unreplied_orders:
                                c_id = item.get("id")
                                if c_id not in notified_cache:
                                    notify_unreplied_order(
                                        customer_name=item.get("customer_name", "เธฅเธนเธเธเนเธฒ"),
                                        comment_text=item.get("text", ""),
                                        reason=item.get("reason", ""),
                                        post_url=post_url
                                    )
                                    notified_cache.add(c_id)
                                    total_new_alerts += 1

                                    # เธ•เธญเธเธฃเธฑเธเธญเธญเน€เธ”เธญเธฃเนเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเธเธ Facebook (เธ–เนเธฒเน€เธเธดเธ”เนเธเนเธเธฒเธ)
                                    auto_reply_enabled, auto_reply_template = get_auto_reply_settings(reload_env=True)
                                    if auto_reply_enabled:
                                        print(f"      ๐’ฌ เธเธณเธฅเธฑเธเธ•เธญเธเธเธฅเธฑเธเธเธญเธกเน€เธกเธเธ•เนเธฅเธนเธเธเนเธฒ \"{item.get('customer_name')}\" เธเธ Facebook...")
                                        replied = reply_to_facebook_comment(
                                            page=page,
                                            customer_name=item.get("customer_name", ""),
                                            comment_text=item.get("text", ""),
                                            reply_message=auto_reply_template
                                        )
                                        if replied:
                                            print(f"      [โ“] เธ•เธญเธเธเธฅเธฑเธเธเธญเธกเน€เธกเธเธ•เนเธฅเธนเธเธเนเธฒ \"{item.get('customer_name')}\" เธเธ Facebook เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")
                                        else:
                                            print(f"      [!] เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เธ•เธญเธเธเธฅเธฑเธเธเธญเธกเน€เธกเธเธ•เนเธฅเธนเธเธเนเธฒ \"{item.get('customer_name')}\" เธญเธฑเธ•เนเธเธกเธฑเธ•เธดเนเธ”เน")
                                        time.sleep(1.5)

                        if p_idx < len(active_urls):
                            time.sleep(2)

                    if interrupted_during_posts:
                        continue

                    if total_new_alerts > 0:
                        save_cache(notified_cache)
                        print(f"\n   ๐จ เนเธเนเธเน€เธ•เธทเธญเธเธญเธญเน€เธ”เธญเธฃเนเธเนเธฒเธเธ•เธญเธเนเธซเธกเนเนเธเธฃเธญเธเธเธตเน: {total_new_alerts} เธฃเธฒเธขเธเธฒเธฃ")
                    else:
                        print(f"\n   โ… เธ•เธฃเธงเธเธชเธญเธเธเธฃเธเธ—เธธเธเนเธเธชเธ•เนเนเธฅเนเธง: เธญเธญเน€เธ”เธญเธฃเนเธ—เธฑเนเธเธซเธกเธ”เนเธ”เนเธฃเธฑเธเธเธฒเธฃเธ•เธญเธเธฃเธฑเธเนเธฅเนเธง เธซเธฃเธทเธญเนเธกเนเธกเธตเธญเธญเน€เธ”เธญเธฃเนเนเธซเธกเน")
                        if SEND_IDLE_STATUS:
                            short_time = datetime.now().strftime("%H:%M")
                            post_count_str = f" ({len(active_urls)} เนเธเธชเธ•เน)" if len(active_urls) > 1 else ""
                            send_telegram_status(f"โ… เธ•เธฃเธงเธเธชเธญเธเนเธฅเนเธง ({short_time}): เนเธกเนเธกเธตเธญเธญเน€เธ”เธญเธฃเนเนเธซเธกเน{post_count_str}")

                    if once:
                        print("\n[โ“] เธ•เธฃเธงเธเธชเธญเธเธฃเธญเธเน€เธ”เธตเธขเธงเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง เธเธดเธ”เธเธฒเธฃเธ—เธณเธเธฒเธ")
                        break

                    # เธชเธธเนเธกเธซเธเนเธงเธเน€เธงเธฅเธฒเน€เธฅเนเธเธเนเธญเธขเน€เธเธทเนเธญเธเธงเธฒเธกเธเธฅเธญเธ”เธ เธฑเธข เธเนเธญเธเธเธฑเธ Bot Detection
                    current_interval = get_check_interval(reload_env=True)
                    jitter = random.randint(-5, 10)
                    sleep_time = max(30, current_interval + jitter)
                    print(f"\n   โณ เธฃเธญเธญเธตเธ {sleep_time} เธงเธดเธเธฒเธ—เธตเธเนเธญเธเธ•เธฃเธงเธเน€เธเนเธเธฃเธญเธเธ–เธฑเธ”เนเธ... (เนเธเนเนเธเธฅเธดเธเธเนเนเธ GUI เนเธฅเนเธงเธเธ”เธญเธฑเธเน€เธ”เธ•เน€เธเธทเนเธญเธ•เธฃเธงเธเธ—เธฑเธเธ—เธตเนเธ”เนเธ•เธฅเธญเธ”เน€เธงเธฅเธฒ)")

                    # เธเธฑเธเธ–เธญเธขเธซเธฅเธฑเธเน€เธเนเธเธงเธดเธเธฒเธ—เธต เธเธฃเนเธญเธกเธ”เธฑเธเธเธฑเธ Trigger File เธซเธฃเธทเธญ URL Change
                    sleep_start = time.time()
                    last_printed_sec = -1
                    while (time.time() - sleep_start) < sleep_time:
                        if TRIGGER_FILE.exists():
                            try:
                                TRIGGER_FILE.unlink(missing_ok=True)
                            except Exception:
                                pass
                            print("\nโก [เธ•เธฃเธงเธเธเธเธชเธฑเธเธเธฒเธ“เธญเธฑเธเน€เธ”เธ•เธเธฒเธ GUI] เธเนเธฒเธกเน€เธงเธฅเธฒเธฃเธญเนเธฅเธฐเน€เธฃเธดเนเธกเธ•เธฃเธงเธเนเธเธชเธ•เนเนเธซเธกเนเธ—เธฑเธเธ—เธต!")
                            break

                        elapsed = int(time.time() - sleep_start)
                        # เน€เธเนเธ .env เธ—เธธเธเน 3 เธงเธดเธเธฒเธ—เธต เน€เธเธทเนเธญเธเธนเนเนเธเนเธเธฑเธเธ—เธถเธเนเธเธฅเน .env เนเธ”เธขเธ•เธฃเธ
                        if elapsed > 0 and elapsed % 3 == 0 and elapsed != last_printed_sec:
                            chk_urls = get_post_urls(reload_env=True)
                            if chk_urls and chk_urls != active_urls:
                                print("\nโก [เธ•เธฃเธงเธเธเธเธเธฒเธฃเน€เธเธฅเธตเนเธขเธ URL เนเธ .env] เธเนเธฒเธกเน€เธงเธฅเธฒเธฃเธญเนเธฅเธฐเน€เธฃเธดเนเธกเธ•เธฃเธงเธเนเธเธชเธ•เนเนเธซเธกเนเธ—เธฑเธเธ—เธต!")
                                break

                        remaining = int(sleep_time - elapsed)
                        if remaining > 0 and remaining % 30 == 0 and remaining != last_printed_sec:
                            last_printed_sec = remaining
                            print(f"      ...เธเธฐเธ•เธฃเธงเธเธฃเธญเธเธ–เธฑเธ”เนเธเนเธเธญเธตเธ {remaining} เธงเธดเธเธฒเธ—เธต... (เธซเธฃเธทเธญเธเธ”เธญเธฑเธเน€เธ”เธ•เนเธ GUI เน€เธเธทเนเธญเน€เธฃเธดเนเธกเธ—เธฑเธเธ—เธต)")

                        time.sleep(1)

                    round_count += 1

                except KeyboardInterrupt:
                    raise
                except Exception as err:
                    print(f"\n[!] เน€เธเธดเธ”เธเนเธญเธเธดเธ”เธเธฅเธฒเธ”เนเธเธเธฒเธฃเธ•เธฃเธงเธเธชเธญเธเธฃเธญเธเธเธตเน: {err}")
                    print("   โณ เธฃเธญ 20 เธงเธดเธเธฒเธ—เธตเธเนเธญเธเธฅเธญเธเธฃเธญเธเธ–เธฑเธ”เนเธ...")
                    for _ in range(20):
                        if TRIGGER_FILE.exists():
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            print("\n[!] เธเธนเนเนเธเนเธชเธฑเนเธเธซเธขเธธเธ”เธเธฒเธฃเธ—เธณเธเธฒเธ (Ctrl+C)")
        finally:
            try:
                context.close()
            except Exception:
                pass
            print("[*] เธเธดเธ”เน€เธเธฃเธฒเธงเนเน€เธเธญเธฃเนเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง")

def clear_cache():
    """เธฅเนเธฒเธเธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธเน€เธเธทเนเธญเน€เธฃเธดเนเธกเธ•เธฃเธงเธเธเธฑเธเนเธซเธกเนเธ—เธฑเนเธเธซเธกเธ”"""
    from config import CACHE_FILE
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    print("[โ“] เธฅเนเธฒเธเธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธ (notified_cache.json) เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง")

def setup_telegram():
    """เธเนเธเธซเธฒ Chat ID เธเธญเธเธเธนเนเนเธเนเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเนเธฅเธฐเธเธฑเธเธ—เธถเธเธฅเธ .env"""
    import re
    import requests
    from config import TELEGRAM_BOT_TOKEN, BASE_DIR

    if not TELEGRAM_BOT_TOKEN:
        print("[!] เธขเธฑเธเนเธกเนเนเธ”เนเธฃเธฐเธเธธ TELEGRAM_BOT_TOKEN เนเธเนเธเธฅเน .env")
        return

    print("\n" + "="*60)
    print("๐ค– เธเธณเธฅเธฑเธเน€เธเธทเนเธญเธกเธ•เนเธญเธเธฑเธ Telegram Bot (@takoab_alert_bot)...")
    print("๐‘ เธซเธฒเธเธขเธฑเธเนเธกเนเนเธ”เนเธเธ” เนเธซเนเน€เธเธดเธ”เนเธญเธ Telegram เธเนเธเธซเธฒ @takoab_alert_bot เนเธฅเนเธงเธเธ” [Start]")
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
                    print(f"\n[โ“] เธ•เธฃเธงเธเธเธ Chat ID เธเธญเธเธเธธเธ“เนเธฅเนเธง! (เธเธนเนเนเธเน: {user_name} | ID: {chat_id})")
                    
                    env_path = BASE_DIR / ".env"
                    if env_path.exists():
                        content = env_path.read_text(encoding="utf-8")
                        if "TELEGRAM_CHAT_ID=" in content:
                            content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", content)
                        else:
                            content += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
                        env_path.write_text(content, encoding="utf-8")
                        print("[โ“] เธเธฑเธเธ—เธถเธ TELEGRAM_CHAT_ID เธฅเธเนเธเนเธเธฅเน .env เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")

                    test_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    requests.post(test_url, json={
                        "chat_id": chat_id,
                        "text": "๐ <b>เน€เธเธทเนเธญเธกเธ•เนเธญเธฃเธฐเธเธเนเธเนเธเน€เธ•เธทเธญเธเธชเธณเน€เธฃเนเธ!</b>\n\nเน€เธกเธทเนเธญเธกเธตเธฅเธนเธเธเนเธฒเธชเธฑเนเธเธญเธญเน€เธ”เธญเธฃเนเนเธซเธกเนเนเธเธเธฅเธธเนเธก Facebook เธฃเธฐเธเธเธเธฐเธชเนเธเธเนเธญเธเธงเธฒเธกเนเธเนเธเน€เธ•เธทเธญเธเน€เธเนเธฒ Telegram เธเธตเนเธ—เธฑเธเธ—เธตเธเธฃเธฑเธ",
                        "parse_mode": "HTML"
                    }, timeout=10)
                    print("[โ“] เธชเนเธเธเนเธญเธเธงเธฒเธกเธ—เธ”เธชเธญเธเน€เธเนเธฒ Telegram เธเธเธกเธทเธญเธ–เธทเธญเธเธญเธเธเธธเธ“เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")
                    return
        except Exception:
            pass
        
        print(f"[*] เธเธณเธฅเธฑเธเธฃเธญเธเนเธญเธเธงเธฒเธกเธเธฒเธเธเธธเธ“เนเธ Telegram... ({attempt}/10) [เธเธฃเธธเธ“เธฒเธเธ” Start เธ—เธตเน @takoab_alert_bot]")
        time.sleep(3)

    print("\n[!] เธขเธฑเธเนเธกเนเธเธเธเนเธญเธเธงเธฒเธกเน€เธเนเธฒ เธเธฃเธธเธ“เธฒเน€เธเธดเธ” Telegram เน€เธเนเธฒเนเธเธ—เธตเน @takoab_alert_bot เนเธฅเนเธงเธเธ” Start เธเธฒเธเธเธฑเนเธเธฃเธฑเธเธเธณเธชเธฑเนเธเธเธตเนเนเธซเธกเนเธญเธตเธเธเธฃเธฑเนเธเธเธฃเธฑเธ")

def main():
    parser = argparse.ArgumentParser(description="Facebook Group Post Order Monitor")
    parser.add_argument("--login", action="store_true", help="เน€เธเธดเธ”เน€เธเธฃเธฒเธงเนเน€เธเธญเธฃเนเน€เธเธทเนเธญเธฅเนเธญเธเธญเธดเธ Facebook เธเธฃเธฑเนเธเนเธฃเธ")
    parser.add_argument("--watch", action="store_true", help="เน€เธฃเธดเนเธกเน€เธเนเธฒเธ”เธนเนเธเธชเธ•เนเนเธฅเธฐเนเธเนเธเน€เธ•เธทเธญเธเธญเธญเน€เธ”เธญเธฃเน")
    parser.add_argument("--check-once", action="store_true", help="เธ•เธฃเธงเธเน€เธเนเธเน€เธเธตเธขเธ 1 เธฃเธญเธเนเธฅเนเธงเนเธชเธ”เธเธเธฅเธฅเธฑเธเธเน")
    parser.add_argument("--test-notify", action="store_true", help="เธ—เธ”เธชเธญเธเธฃเธฐเธเธเน€เธชเธตเธขเธเนเธฅเธฐเธเธฒเธฃเนเธเนเธเน€เธ•เธทเธญเธเธเธ Mac")
    parser.add_argument("--clear-cache", action="store_true", help="เธฅเนเธฒเธเธเธฃเธฐเธงเธฑเธ•เธดเธเธญเธกเน€เธกเธเธ•เนเธ—เธตเนเน€เธเธขเนเธเนเธเน€เธ•เธทเธญเธเนเธฅเนเธง")
    parser.add_argument("--telegram-setup", action="store_true", help="เน€เธเธทเนเธญเธกเธ•เนเธญเนเธฅเธฐเธเนเธเธซเธฒ Telegram Chat ID เธญเธฑเธ•เนเธเธกเธฑเธ•เธด")
    parser.add_argument("--test-order", action="store_true", help="เธชเนเธเธ—เธ”เธชเธญเธเธญเธญเน€เธ”เธญเธฃเนเน€เธเนเธฒ Telegram เนเธ”เธขเธฃเธฐเธเธธเธเธทเนเธญเนเธฅเธฐเธเธญเธกเน€เธกเธเธ•เน")
    parser.add_argument("--name", type=str, default="", help="เธเธทเนเธญเธฅเธนเธเธเนเธฒเธชเธณเธซเธฃเธฑเธเธเธฒเธฃเธ—เธ”เธชเธญเธ (เนเธเนเธฃเนเธงเธกเธเธฑเธ --test-order)")
    parser.add_argument("--comment", type=str, default="", help="เธเนเธญเธเธงเธฒเธกเธเธญเธกเน€เธกเธเธ•เนเธชเธณเธซเธฃเธฑเธเธเธฒเธฃเธ—เธ”เธชเธญเธ (เนเธเนเธฃเนเธงเธกเธเธฑเธ --test-order)")
    parser.add_argument("--post", "--create-post", dest="create_post", action="store_true", help="เธชเธฃเนเธฒเธเนเธฅเธฐเน€เธเธขเนเธเธฃเนเนเธเธชเธ•เนเน€เธเธดเธ”เธฃเนเธฒเธเธฅเธเธเธฅเธธเนเธก Facebook เธญเธฑเธ•เนเธเธกเธฑเธ•เธด")
    parser.add_argument("--post-date", type=str, default="", help="เธฃเธฐเธเธธเธงเธฑเธเธ—เธตเนเธชเธณเธซเธฃเธฑเธเนเธเธชเธ•เน (เน€เธเนเธ 'เธญเธฒเธ—เธดเธ•เธขเน 1/11/69') เธซเธฒเธเนเธกเนเธฃเธฐเธเธธเธเธฐเนเธเนเธงเธฑเธเธเธตเน")
    parser.add_argument("--post-preview", action="store_true", help="เธชเธฃเนเธฒเธเธ เธฒเธเธ•เธฑเธงเธญเธขเนเธฒเธเนเธเธชเธ•เนเธฅเธเนเธเธฅเน preview_post.png เนเธ”เธขเธขเธฑเธเนเธกเนเธเธ”เน€เธเธขเนเธเธฃเน")
    parser.add_argument("--post-group", type=str, default="", help="เธฃเธฐเธเธธ Group ID เธซเธฃเธทเธญ URL เธเธฅเธธเนเธก Facebook เธชเธณเธซเธฃเธฑเธเนเธเธชเธ•เน")
    parser.add_argument("--auto-watch", action="store_true", help="เน€เธฃเธดเนเธกเน€เธเนเธฒเธ”เธนเธเธญเธกเน€เธกเธเธ•เนเธ—เธฑเธเธ—เธตเธซเธฅเธฑเธเธเธฒเธเนเธเธชเธ•เนเน€เธชเธฃเนเธเธชเธดเนเธ")

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
    elif args.create_post or args.post_preview:
        from fb_poster import (
            get_default_template, format_post_text, get_default_post_images,
            publish_facebook_group_post, update_env_post_url
        )
        from config import GROUP_ID
        group_target = args.post_group.strip() or GROUP_ID or "1111870942162462"
        tmpl = get_default_template()
        content_txt = format_post_text(tmpl, custom_date_str=args.post_date)
        images = get_default_post_images()

        print("\n" + "=" * 60)
        if args.post_preview:
            print("๐‘ เธชเธฃเนเธฒเธเธ เธฒเธเธ•เธฑเธงเธญเธขเนเธฒเธเนเธเธชเธ•เน Facebook...")
        else:
            print("๐“ข เธเธณเธฅเธฑเธเธชเธฃเนเธฒเธเนเธฅเธฐเน€เธเธขเนเธเธฃเนเนเธเธชเธ•เนเธฅเธเธเธฅเธธเนเธก Facebook...")
        print(f"๐“ เธเธฅเธธเนเธกเน€เธเนเธฒเธซเธกเธฒเธข: {group_target}")
        print(f"๐–ผ เธเธณเธเธงเธเธฃเธนเธเธ เธฒเธเนเธเธ: {len(images)} เธฃเธนเธ")
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
                print(f"\n[โ“] เธชเธฃเนเธฒเธเธ เธฒเธเธ•เธฑเธงเธญเธขเนเธฒเธเธชเธณเน€เธฃเนเธ: {res.get('preview_image')}")
            else:
                post_url = res.get("post_url")
                print(f"\n[โ“] เน€เธเธขเนเธเธฃเนเนเธเธชเธ•เนเธชเธณเน€เธฃเนเธ! เธฅเธดเธเธเนเนเธเธชเธ•เน: {post_url}")
                if post_url and "posts" in post_url:
                    update_env_post_url(post_url)
                    print("๐‘ เธญเธฑเธเน€เธ”เธ• POST_URL เนเธ .env เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง")
                if args.auto_watch:
                    print("\n๐€ เน€เธฃเธดเนเธกเน€เธเนเธฒเธชเธนเนเนเธซเธกเธ”เน€เธเนเธฒเธ”เธนเธเธญเธกเน€เธกเธเธ•เนเธ—เธฑเธเธ—เธต...")
                    run_monitor(once=False)
        else:
            print(f"\n[!] เธเธฒเธฃเนเธเธชเธ•เนเนเธกเนเธชเธณเน€เธฃเนเธ: {res.get('error')}")
    elif args.check_once:
        run_monitor(once=True)
    elif args.watch:
        run_monitor(once=False)
    else:
        parser.print_help()
        print("\nเธ•เธฑเธงเธญเธขเนเธฒเธเธเธณเธชเธฑเนเธเนเธเนเธเธฒเธ:")
        print("  1. python main.py --login           # เธฅเนเธญเธเธญเธดเธ Facebook เธเธฃเธฑเนเธเนเธฃเธ")
        print("  2. python main.py --telegram-setup  # เน€เธเธทเนเธญเธกเธ•เนเธญ Telegram Chat ID เธญเธฑเธ•เนเธเธกเธฑเธ•เธด")
        print("  3. python main.py --watch           # เน€เธฃเธดเนเธกเน€เธเนเธฒเธ”เธนเนเธเธชเธ•เนเนเธฅเธฐเนเธเนเธเน€เธ•เธทเธญเธ")
        print("  4. python main.py --post            # เธชเธฃเนเธฒเธเนเธฅเธฐเนเธเธชเธ•เนเน€เธเธดเธ”เธฃเนเธฒเธเธฅเธเธเธฅเธธเนเธก Facebook")
        print("  5. python main.py --post-preview    # เธ”เธนเธ เธฒเธเธ•เธฑเธงเธญเธขเนเธฒเธเนเธเธชเธ•เนเธเนเธญเธเธชเนเธเธเธฃเธดเธ")
        print("  6. python main.py --test-order      # เธ—เธ”เธชเธญเธเธชเนเธเธญเธญเน€เธ”เธญเธฃเนเน€เธเนเธฒ Telegram")
        print("  7. python main.py --test-order --name \"เธเธธเธ“เธชเธกเธเธฒเธข\" --comment \"เธ—เธฒเนเธเธฐเธขเธฒเธเธด 1 เธเธฅเนเธญเธ\"")

if __name__ == "__main__":
    main()

