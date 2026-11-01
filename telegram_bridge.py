import os
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POS_API_BASE = os.getenv("POS_API_BASE", "https://takoab-api.aeaee.one").rstrip("/")

def check_pending_post_command() -> dict | None:
    """ตรวจสอบคำสั่งโพสต์ Facebook ที่รอคิวจาก Telegram"""
    url = f"{POS_API_BASE}/api/monitor/pending-post"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("has_task"):
                return data
    except Exception:
        pass
    return None

def report_post_result(task_id: str, status: str, post_url: str = None, close_time: str = "20.00", error: str = None) -> bool:
    """ส่งผลการโพสต์กลับไปยัง POS เพื่อแจ้งเตือนกลับใน Telegram"""
    url = f"{POS_API_BASE}/api/monitor/post-result"
    payload = {
        "task_id": task_id,
        "status": status,
        "post_url": post_url,
        "close_time": close_time or "20.00",
        "error": error
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        print(f"[!] ไม่สามารถส่งผลลัพธ์โพสต์กลับไปยัง POS ได้: {e}")
        return False

def execute_telegram_post_task(task: dict, progress_cb=None) -> dict:
    """รันคำสั่งโพสต์ที่ได้รับจาก Telegram"""
    from fb_poster import (
        get_default_template, format_post_text, get_default_post_images,
        publish_facebook_group_post, update_env_post_url
    )
    from config import GROUP_ID

    task_id = task.get("task_id")
    command = task.get("command", "publish")
    close_time = task.get("close_time", "20.00")
    date_str = task.get("date_str")
    is_preview = (command == "preview")
    group_target = GROUP_ID or "1111870942162462"

    print(f"\n[*] 🤖 ได้รับคำสั่งจาก Telegram: {command.upper()} (ปิดรับออเดอร์: {close_time} น.)")
    if progress_cb:
        try:
            progress_cb(f"ได้รับคำสั่งจาก Telegram ({command.upper()} ปิด {close_time} น.)")
        except Exception:
            pass

    tmpl = get_default_template()
    content = format_post_text(tmpl, custom_date_str=date_str, close_time=close_time)
    images = get_default_post_images()

    res = publish_facebook_group_post(
        group_id_or_url=group_target,
        content=content,
        image_paths=images,
        headless=True,
        preview_only=is_preview,
        progress_cb=progress_cb
    )

    if res.get("success"):
        post_url = res.get("post_url")
        if not is_preview and post_url and "posts" in post_url:
            update_env_post_url(post_url)
        report_post_result(
            task_id=task_id,
            status="completed",
            post_url=post_url,
            close_time=close_time,
            error=None
        )
        print(f"[✓] 🤖 ดำเนินการคำสั่ง Telegram สำเร็จ! (Post: {post_url or 'Preview'})")
    else:
        err = res.get("error", "เกิดข้อผิดพลาดในการโพสต์")
        report_post_result(
            task_id=task_id,
            status="failed",
            post_url=None,
            close_time=close_time,
            error=err
        )
        print(f"[!] 🤖 ดำเนินการคำสั่ง Telegram ไม่สำเร็จ: {err}")

    return res
