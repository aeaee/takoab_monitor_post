import json
import requests
from config import GEMINI_API_KEY, GEMINI_MODEL, CONFIRM_KEYWORDS, ORDER_KEYWORDS, ANNOUNCEMENT_KEYWORDS, USE_AI, SELLER_NAMES

def check_is_post_author(author: str, has_author_badge: bool = False, post_author: str = "") -> bool:
    """
    ตรวจสอบว่าผู้เขียนคอมเมนต์เป็น 'คนโพสต์' (เจ้าของโพสต์ / ผู้เขียน) หรือไม่
    คนโพสต์คือผู้สร้างโพสต์ขายของ จะไม่มีทางคอมเมนต์สั่งอาหารจากโพสต์ตนเองเด็ดขาด
    """
    if has_author_badge:
        return True
    if not author:
        return False
    author_clean = author.lower().strip()

    if post_author:
        main_author = post_author.split(",")[0].strip().lower()
        if main_author and (main_author in author_clean or author_clean in main_author):
            return True

    if SELLER_NAMES:
        first_seller = SELLER_NAMES[0].lower()
        if first_seller in author_clean or author_clean in first_seller:
            return True

    return False

def check_is_seller(author: str, has_author_badge: bool = False, post_author: str = "") -> bool:
    """ตรวจสอบว่าผู้เขียนคอมเมนต์เป็นคนขาย/เจ้าของร้านคนใดคนหนึ่งหรือไม่"""
    if has_author_badge:
        return True
    author_lower = author.lower().strip()
    if post_author and author_lower in post_author.lower():
        return True
    return any(s.lower() in author_lower for s in SELLER_NAMES)

def analyze_comments(comments: list, post_author: str = "") -> list:
    """
    วิเคราะห์คอมเมนต์ทั้งหมด หาคอมเมนต์ที่มีการสั่งซื้อและยังไม่มีการตอบรับออเดอร์
    คืนค่าเป็น list ของคอมเมนต์ที่ต้องแจ้งเตือน
    """
    if not comments:
        return []

    # ถ้าเปิด USE_AI=true และมี API Key ให้ใช้ AI วิเคราะห์
    if USE_AI and GEMINI_API_KEY:
        try:
            return analyze_with_gemini(comments, post_author)
        except Exception as e:
            print(f"[!] Gemini AI วิเคราะห์ขัดข้อง ({e}) สลับไปใช้ระบบตรวจ Keyword ในเครื่อง...")

    # โหมดตรวจคำปกติ (Keyword Matching ในเครื่อง)
    return analyze_with_rules(comments, post_author)

def analyze_with_gemini(comments: list, post_author: str = "") -> list:
    """วิเคราะห์ด้วย Gemini Flash ผ่าน REST API อย่างแม่นยำ"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    simplified_comments = []
    seller_comments = []

    for c in comments:
        author = c.get("author", "")
        text = c.get("text", "")
        has_badge = c.get("has_author_badge", False)
        is_creator = check_is_post_author(author, has_badge, post_author)
        is_seller = check_is_seller(author, has_badge, post_author)
        text_lower = text.lower()
        has_confirm_kw = any(kw in text_lower for kw in CONFIRM_KEYWORDS)

        # 1. ถ้าเป็น "คนโพสต์" (เจ้าของโพสต์ / ผู้เขียน)
        # ให้ข้ามเสมอ ไม่นำมาตรวจเป็นออเดอร์เด็ดขาด (เก็บเฉพาะข้อความยืนยันรับออเดอร์)
        if is_creator:
            if has_confirm_kw:
                seller_comments.append(f"{author}: {text}")
            continue

        # 2. ถ้าเป็นข้อความประกาศร้าน ให้ข้าม
        if any(kw in text_lower for kw in ANNOUNCEMENT_KEYWORDS):
            continue

        # 3. ถ้าเป็นคนขายคนอื่น (เช่น แม่บี) และพิมพ์ยืนยันรับออเดอร์ ให้เก็บไว้เป็นข้อความยืนยัน
        if is_seller and has_confirm_kw:
            seller_comments.append(f"{author}: {text}")
        else:
            # ถ้าเป็นลูกค้าทั่วไป หรือเป็นคนขายที่มาคอมเมนต์สั่งของแทนลูกค้า (ไม่ได้พิมพ์รับออเดอร์)
            simplified_comments.append({
                "id": c.get("id"),
                "customer_name": f"{author} (สั่งให้ลูกค้า)" if is_seller else author,
                "comment_text": text,
                "replies": [
                    {
                        "author": r.get("author"),
                        "text": r.get("text"),
                        "is_author": check_is_seller(r.get("author", ""), r.get("has_author_badge", False), post_author)
                    }
                    for r in c.get("replies", [])
                ],
                "full_thread_text": c.get("full_thread_text", "")[:300]
            })

    if not simplified_comments:
        return []

    sellers_label = ", ".join(SELLER_NAMES) if SELLER_NAMES else (post_author or "ไม่ระบุ")

    prompt = f"""
คุณเป็นระบบคัดกรองออเดอร์ในกลุ่ม Facebook โพสต์นี้เป็นการขายของ/รับออเดอร์
ชื่อคนขาย/ทีมงานรับออเดอร์: "{sellers_label}"

ข้อความทั้งหมดที่คนขายพิมพ์ตอบในโพสต์นี้:
{chr(10).join(seller_comments) if seller_comments else '(ไม่มี)'}

กฎการวิเคราะห์:
1. คนขาย (เช่น {sellers_label}) อาจตอบรับออเดอร์ได้ 2 วิธี:
   - วิธีที่ 1: ตอบกลับใต้คอมเมนต์ของลูกค้าโดยตรง (ใน replies)
   - วิธีที่ 2: พิมพ์คอมเมนต์ใหม่โดยแท็กชื่อลูกค้า แล้วพิมพ์ว่า "รับออเดอร์ครับ" หรือ "รับออเดอร์ค่ะ" (เช่น 'Jerakanok Satthaporn รับออเดอร์ค่ะ')
   **หากพบว่าคนขายคนใดคนหนึ่งได้ตอบรับออเดอร์ลูกค้ารายนั้นแล้วไม่ว่าจะวิธีใด ให้ถือว่าตอบรับแล้ว และห้ามแจ้งเตือนเด็ดขาด!**
2. ตรวจสอบเฉพาะคอมเมนต์ที่มีการ "สั่งซื้อสินค้า" หรือ "สอบถามออเดอร์" (เช่น 'ทาโกะ 1', 'เอา 2 กล่อง', 'cf', 'ราคาเท่าไหร่', หรือมีแนบรูปภาพ)
3. แจ้งเตือนเฉพาะคอมเมนต์ที่ **"ยังไม่ได้รับการตอบรับออเดอร์จากคนขาย"** เท่านั้น!
4. กรณีทีมงานคนขายมาสั่งของ: หากผู้คอมเมนต์เป็นคนขาย (เช่น {sellers_label}) แต่ข้อความเป็น "การสั่งซื้ออาหารให้ลูกค้า" (ไม่ใช่การพิมพ์รับออเดอร์) และยังไม่มีใครตอบรับออเดอร์ ให้ถือว่าเป็นออเดอร์ที่ต้องแจ้งเตือนด้วย

รายการคอมเมนต์ที่จะตรวจ (JSON):
{json.dumps(simplified_comments, ensure_ascii=False, indent=2)}

ตอบกลับเป็น JSON array เท่านั้น:
[
  {{
    "id": "<id>",
    "customer_name": "<ชื่อลูกค้า/ผู้สั่ง>",
    "text": "<ข้อความสั่งซื้อ>",
    "is_unreplied_order": true,
    "reason": "<เหตุผล เช่น ลูกค้าสั่ง 2 กล่อง ยังไม่มีข้อความรับออเดอร์จากคนขาย>"
  }}
]
(หากทุกคอมเมนต์ได้รับการตอบรับแล้ว หรือไม่มีออเดอร์ค้างตอบ ให้ตอบเป็น [])
"""

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }

    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return []

    text_output = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
    results = json.loads(text_output)
    
    unreplied = []
    for item in results:
        if item.get("is_unreplied_order"):
            unreplied.append({
                "id": item.get("id"),
                "customer_name": item.get("customer_name"),
                "text": item.get("text"),
                "reason": item.get("reason", "ยังไม่มีการตอบรับออเดอร์")
            })
    return unreplied

def analyze_with_rules(comments: list, post_author: str = "") -> list:
    """วิเคราะห์ด้วย Local Rules & Keywords ในเครื่อง"""
    unreplied = []

    # รวบรวมข้อความยืนยันรับออเดอร์ทั้งหมดที่คนขายพิมพ์ในโพสต์
    seller_messages = []
    for c in comments:
        author = c.get("author", "").strip()
        text = c.get("text", "").strip()
        has_badge = c.get("has_author_badge", False)
        is_seller = check_is_seller(author, has_badge, post_author)
        # เก็บเฉพาะข้อความที่คนขายพิมพ์ยืนยันรับออเดอร์
        if is_seller and text and any(kw in text.lower() for kw in CONFIRM_KEYWORDS):
            seller_messages.append(text.lower())
        for r in c.get("replies", []):
            r_author = r.get("author", "").strip()
            r_text = r.get("text", "").strip()
            r_badge = r.get("has_author_badge", False)
            if check_is_seller(r_author, r_badge, post_author) and r_text and any(kw in r_text.lower() for kw in CONFIRM_KEYWORDS):
                seller_messages.append(r_text.lower())

    for c in comments:
        c_id = c.get("id")
        author = c.get("author", "").strip()
        text = c.get("text", "").strip()
        replies = c.get("replies", [])
        has_badge = c.get("has_author_badge", False)
        full_thread_text = c.get("full_thread_text", "").lower()
        text_lower = text.lower()

        is_creator = check_is_post_author(author, has_badge, post_author)
        # 1. ถ้าเป็น "คนโพสต์" (เจ้าของโพสต์ / ผู้เขียน) ให้ข้ามเสมอ!
        # เจ้าของโพสต์ไม่มีทางคอมเมนต์สั่งอาหารจากโพสต์ของตัวเองเด็ดขาด (มีแต่แจ้งข้อมูล/ตอบรับ)
        if is_creator:
            continue

        # 2. ถ้าเป็นข้อความประกาศหรือแจ้งรายละเอียดของร้าน (เช่น "พร้อมจัดส่งทุกหมู่บ้าน") ให้ข้าม
        if any(kw in text_lower for kw in ANNOUNCEMENT_KEYWORDS):
            continue

        is_seller = check_is_seller(author, has_badge, post_author)
        has_confirm_in_own = any(kw in text_lower for kw in CONFIRM_KEYWORDS)

        # 3. ถ้าเป็นคนขายคนอื่น (เช่น แม่บี) และข้อความเป็นคำยืนยันรับออเดอร์ ให้ข้าม
        if is_seller and has_confirm_in_own:
            continue

        # 1. ตรวจสอบว่าใน replies หรือใน thread มีคำยืนยันรับออเดอร์แล้วหรือไม่
        has_confirmation = False

        # ตรวจสอบใน replies ว่ามีคนขายคนใดมาตอบรับออเดอร์แล้วหรือไม่
        for reply in replies:
            reply_text = reply.get("text", "").lower()
            for kw in CONFIRM_KEYWORDS:
                if kw in reply_text:
                    has_confirmation = True
                    break
            if has_confirmation:
                break

        # 2. ตรวจสอบข้ามคอมเมนต์: คนขายพิมพ์ตอบรับโดยแท็กชื่อลูกค้าในคอมเมนต์แยกต่างหากหรือไม่
        if not has_confirmation and author:
            author_first_name = author.split()[0].lower()
            author_full_name = author.lower()
            for msg in seller_messages:
                # ถ้าข้อความรับออเดอร์ของคนขายมีชื่อของคนสั่ง
                if author_first_name in msg or author_full_name in msg:
                    has_confirmation = True
                    break

        # 3. ถ้ายังไม่มีการยืนยัน ให้ตรวจว่าเป็นออเดอร์หรือไม่
        if not has_confirmation:
            is_order = any(k in text_lower for k in ORDER_KEYWORDS) or "[📷 มีแนบรูปภาพ]" in text

            if is_order:
                display_author = f"{author} (สั่งให้ลูกค้า)" if is_seller else (author or "ลูกค้า")
                unreplied.append({
                    "id": c_id,
                    "customer_name": display_author,
                    "text": text,
                    "reason": "พบคำสั่งซื้อ แต่ยังไม่พบข้อความ 'รับออเดอร์' ในคำตอบกลับ"
                })

    return unreplied
