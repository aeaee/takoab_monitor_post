import json
import re
import requests
from config import (
    GEMINI_API_KEY, GEMINI_MODEL, CONFIRM_KEYWORDS, ORDER_KEYWORDS, 
    ANNOUNCEMENT_KEYWORDS, USE_AI, SELLER_NAMES,
    SELLER_GREETINGS_OR_INVITATIONS, FOOD_ITEMS, UNIT_KEYWORDS, ORDER_VERBS
)

def normalize_text(text: str) -> str:
    """ลบเครื่องหมายคำพูด วงเล็บ และตัดช่องว่างส่วนเกิน"""
    if not text:
        return ""
    cleaned = re.sub(r"[\'\"`()\[\]]+", " ", text)
    return " ".join(cleaned.lower().split())

def get_name_variants(name: str) -> set[str]:
    """สร้างรูปแบบชื่อที่เป็นไปได้ทั้งหมด เช่น มี/ไม่มีชื่อเล่นในเครื่องหมายคำพูด หรือชื่อคู่ 'กับ'"""
    variants = set()
    raw_lower = name.strip().lower()
    if not raw_lower:
        return variants

    variants.add(raw_lower)
    norm = normalize_text(name)
    if norm:
        variants.add(norm)

    # 1. กรณีชื่อมีเครื่องหมายคำพูดหรือวงเล็บ เช่น Peerawat 'A' Sukkawat -> Peerawat Sukkawat
    no_nick = re.sub(r"[\'\"`][^\'\"`]+[\'\"`]", "", name)
    no_nick = re.sub(r"\([^\)]+\)|\[[^\]]+\]", "", no_nick)
    no_nick_norm = normalize_text(no_nick)
    if no_nick_norm and len(no_nick_norm) >= 3:
        variants.add(no_nick_norm)

    # 2. กรณีชื่อเชื่อมด้วย 'กับ', 'และ', 'and', '&', '/', ',' เช่น 'แม่บี กับ น้องบราวนี่'
    sub_parts = re.split(r"\s+(?:กับ|และ|and|&)\s+|\s*[/,]\s*", name, flags=re.IGNORECASE)
    for part in sub_parts:
        p_clean = normalize_text(part)
        if p_clean and len(p_clean) >= 2:
            variants.add(p_clean)

    return variants

def check_is_seller(author: str, has_author_badge: bool = False, post_author: str = "") -> bool:
    """ตรวจสอบว่าผู้เขียนคอมเมนต์เป็นคนขาย/เจ้าของร้านตามรายชื่อ POST_AUTHOR_NAME หรือไม่"""
    if has_author_badge:
        return True
    if not author:
        return False

    author_norm = normalize_text(author)
    if not author_norm:
        return False

    # ตรวจสอบกับ post_author ที่ส่งเข้ามา
    if post_author:
        for p_name in post_author.split(","):
            for v in get_name_variants(p_name):
                if v in author_norm or author_norm in v:
                    return True

    # ตรวจสอบกับ SELLER_NAMES ทั้งหมดจาก POST_AUTHOR_NAME ใน .env
    if SELLER_NAMES:
        for s in SELLER_NAMES:
            for v in get_name_variants(s):
                if v in author_norm or author_norm in v:
                    return True

            s_tokens = [t for t in normalize_text(s).split() if len(t) > 1]
            a_tokens = [t for t in author_norm.split() if len(t) > 1]
            if s_tokens and a_tokens:
                if all(t in s_tokens for t in a_tokens) and len(a_tokens) >= 2:
                    return True
                main_s_tokens = [t for t in s_tokens if len(t) >= 4]
                if main_s_tokens and all(t in a_tokens for t in main_s_tokens):
                    return True

    return False

def check_is_post_author(author: str, has_author_badge: bool = False, post_author: str = "") -> bool:
    """ตรวจสอบว่าผู้เขียนคอมเมนต์เป็นเจ้าของโพสต์หรือทีมงานคนขายหรือไม่"""
    return check_is_seller(author, has_author_badge, post_author)

def is_seller_ordering_for_customer(text: str) -> bool:
    """
    ตรวจสอบว่าข้อความของคนขาย/ทีมงานตาม POST_AUTHOR_NAME เป็นการสั่งอาหารแทนลูกค้าท่านอื่นจริงหรือไม่
    - หากเป็นสติกเกอร์, ข้อความรับออเดอร์, แจ้งข้อมูลร้าน, คำขอบคุณ, ทักทาย หรือชวนสั่ง จะคืนค่า False
    - จะคืนค่า True เฉพาะเมื่อมีรายการอาหารหรือคำสั่งซื้อชัดเจนเท่านั้น
    """
    if not text:
        return False

    # ตัดสัญลักษณ์สติกเกอร์และรูปภาพออก
    text_clean = text.replace("[📷 มีแนบรูปภาพ]", "").replace("[สติกเกอร์]", "").strip().lower()

    # ถ้าตัดสติกเกอร์ออกแล้วไม่มีข้อความ หรือข้อความสั้นมาก (เช่น ส่งสติกเกอร์อย่างเดียว) -> ไม่ใช่การสั่งอาหาร
    if not text_clean or len(text_clean) < 2:
        return False

    # 1. ถ้ามีคำยืนยันรับออเดอร์ (เช่น รับออเดอร์ครับ/ค่ะ, รับยอด, จดแล้ว) -> เป็นการตอบรับลูกค้า ไม่ใช่การสั่งของ
    if any(kw in text_clean for kw in CONFIRM_KEYWORDS):
        return False

    # 2. ถ้าเป็นข้อความประกาศร้าน (เช่น เปิดร้าน, ปิดรอบ, โอนเงิน) -> ไม่ใช่การสั่งของ
    if any(kw in text_clean for kw in ANNOUNCEMENT_KEYWORDS):
        return False

    # 3. ถ้าเป็นคำทักทาย ขอบคุณ หรือคำเชิญชวนสั่งอาหารของคนขาย -> ไม่ใช่การสั่งของ
    if any(kw in text_clean for kw in SELLER_GREETINGS_OR_INVITATIONS):
        return False

    # 4. ตรวจสอบว่ามีชื่ออาหาร หรือคำกริยาสั่งซื้อพร้อมจำนวน
    has_food = any(food in text_clean for food in FOOD_ITEMS)
    has_unit = any(u in text_clean for u in UNIT_KEYWORDS)
    has_verb = any(v in text_clean for v in ORDER_VERBS)
    has_number = bool(re.search(r"\d+|[๑-๙]", text_clean))

    if has_food:
        if has_unit or has_number or has_verb:
            return True
        return True

    if has_verb and (has_unit or has_number):
        return True

    return False

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
        is_seller = check_is_seller(author, has_badge, post_author)
        text_lower = text.lower()
        has_confirm_kw = any(kw in text_lower for kw in CONFIRM_KEYWORDS)

        # 1. ถ้าเป็นคนขาย (ตามรายชื่อ POST_AUTHOR_NAME หรือมี Author Badge)
        if is_seller:
            # เก็บข้อความยืนยันรับออเดอร์ของคนขายไว้ให้ AI ใช้ตรวจสอบการตอบรับ
            if has_confirm_kw:
                seller_comments.append(f"{author}: {text}")

            # เช็คว่าเป็นการสั่งอาหารแทนลูกค้าท่านอื่นจริงหรือไม่
            # ถ้าเป็นสติกเกอร์ ข้อความรับออเดอร์ ประกาศร้าน หรือขอบคุณ ให้ข้ามทันที ไม่ต้องนำมาตรวจออเดอร์
            if not is_seller_ordering_for_customer(text):
                continue

            # ถ้าเป็นการสั่งอาหารแทนลูกค้าท่านอื่นจริง ให้ส่งให้ AI ตรวจสอบว่ามีคนตอบรับแล้วหรือยัง
            simplified_comments.append({
                "id": c.get("id"),
                "customer_name": f"{author} (สั่งให้ลูกค้า)",
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
            continue

        # 2. ถ้าเป็นข้อความประกาศร้าน ให้ข้าม
        if any(kw in text_lower for kw in ANNOUNCEMENT_KEYWORDS):
            continue

        # 3. ถ้าเป็นลูกค้าทั่วไป
        simplified_comments.append({
            "id": c.get("id"),
            "customer_name": author,
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
4. กรณีทีมงานคนขายมาสั่งของ: หากผู้คอมเมนต์เป็นคนขาย ({sellers_label}) ที่พิมพ์สั่งอาหารแทนลูกค้าอย่างชัดเจน และยังไม่มีใครตอบรับออเดอร์ ให้ถือว่าเป็นออเดอร์ที่ต้องแจ้งเตือน แต่ถ้าเป็นสติกเกอร์ ข้อความตอบรับ ข้อความขอบคุณ หรือข้อความอื่นๆ ห้ามแจ้งเตือนเด็ดขาด

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
            c_id = item.get("id")
            orig = next((c for c in comments if c.get("id") == c_id), {})
            unreplied.append({
                "id": c_id,
                "customer_name": item.get("customer_name"),
                "text": item.get("text"),
                "reason": item.get("reason", "ยังไม่มีการตอบรับออเดอร์"),
                "post_url": orig.get("post_url", "")
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

        is_seller = check_is_seller(author, has_badge, post_author)

        # 1. หากผู้คอมเมนต์เป็นคนขาย (ตามรายชื่อ POST_AUTHOR_NAME หรือ Author badge)
        if is_seller:
            # เช็คว่าเป็นการสั่งอาหารแทนลูกค้าท่านอื่นจริงหรือไม่
            # ถ้าเป็นสติกเกอร์ ข้อความรับออเดอร์ ประกาศร้าน หรือข้อความอื่นๆ ที่ไม่ใช่การสั่งอาหาร -> ข้ามทันที ไม่ต้องแจ้งเตือน!
            if not is_seller_ordering_for_customer(text):
                continue
        else:
            # 2. ถ้าเป็นลูกค้าทั่วไป แล้วเป็นข้อความประกาศร้าน ให้ข้าม
            if any(kw in text_lower for kw in ANNOUNCEMENT_KEYWORDS):
                continue

        # 3. ตรวจสอบว่าใน replies หรือใน thread มีคำยืนยันรับออเดอร์แล้วหรือไม่
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

        # ตรวจสอบข้ามคอมเมนต์: คนขายพิมพ์ตอบรับโดยแท็กชื่อลูกค้าในคอมเมนต์แยกต่างหากหรือไม่
        if not has_confirmation and author:
            author_first_name = author.split()[0].lower()
            author_full_name = author.lower()
            for msg in seller_messages:
                # ถ้าข้อความรับออเดอร์ของคนขายมีชื่อของคนสั่ง
                if author_first_name in msg or author_full_name in msg:
                    has_confirmation = True
                    break

        # 4. ถ้ายังไม่มีการยืนยัน ให้ตรวจว่าเป็นออเดอร์หรือไม่
        if not has_confirmation:
            if is_seller:
                # กรณีคนขายสั่งแทนลูกค้า (และผ่านการเช็ค is_seller_ordering_for_customer แล้ว)
                unreplied.append({
                    "id": c_id,
                    "customer_name": f"{author} (สั่งให้ลูกค้า)",
                    "text": text,
                    "reason": "พบคนขายสั่งอาหารแทนลูกค้า แต่ยังไม่พบข้อความ 'รับออเดอร์' ในคำตอบกลับ",
                    "post_url": c.get("post_url", "")
                })
            else:
                is_order = any(k in text_lower for k in ORDER_KEYWORDS) or ("[📷 มีแนบรูปภาพ]" in text and "[สติกเกอร์]" not in text)
                if is_order:
                    unreplied.append({
                        "id": c_id,
                        "customer_name": author or "ลูกค้า",
                        "text": text,
                        "reason": "พบคำสั่งซื้อ แต่ยังไม่พบข้อความ 'รับออเดอร์' ในคำตอบกลับ",
                        "post_url": c.get("post_url", "")
                    })

    return unreplied
