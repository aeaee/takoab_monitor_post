import time
import hashlib
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import CHROME_PATH, USER_DATA_DIR, POST_AUTHOR_NAME, SELLER_NAMES, CONFIRM_KEYWORDS

def get_browser_context(p, headless: bool = False) -> BrowserContext:
    """เปิด Persistent Context ของ Chrome เพื่อคงสถานะล็อกอิน (รองรับทั้ง Windows และ Mac)"""
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    launch_kwargs = {
        "user_data_dir": str(USER_DATA_DIR),
        "headless": headless,
        "viewport": {"width": 1280, "height": 900},
        "args": [
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check"
        ]
    }
    
    if CHROME_PATH and str(CHROME_PATH).strip():
        launch_kwargs["executable_path"] = str(CHROME_PATH)
    else:
        launch_kwargs["channel"] = "chrome"

    return p.chromium.launch_persistent_context(**launch_kwargs)

def manual_login():
    """เปิดหน้าต่างเบราว์เซอร์เพื่อให้ผู้ใช้ล็อกอิน Facebook ครั้งแรก"""
    print("\n" + "="*60)
    print("🔑 กำลังเปิดเบราว์เซอร์ Chrome เพื่อให้คุณล็อกอิน Facebook...")
    print("="*60)

    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.new_page()
        page.goto("https://www.facebook.com", wait_until="domcontentloaded")

        print("\n👉 กรุณาล็อกอิน Facebook ในหน้าต่างเบราว์เซอร์ที่เปิดขึ้นมา")
        print("👉 เมื่อล็อกอินสำเร็จและเข้าหน้าฟีดได้แล้ว ให้กลับมากด [Enter] ในหน้าจอนี้...")
        input("\n[กดปุ่ม Enter เมื่อล็อกอินเสร็จสิ้น] > ")

        print("[✓] บันทึก Session เรียบร้อยแล้ว! ปิดเบราว์เซอร์...")
        context.close()

def expand_comments_and_replies(page: Page):
    """
    กดขยาย 'ความคิดเห็นทั้งหมด' และคลิกปุ่ม 'ดูการตอบกลับ' เฉพาะภายในโพสต์เป้าหมาย
    """
    try:
        page.evaluate("""() => {
            const root = document.querySelector('div[role="dialog"]') || document.querySelector('div[role="main"]') || document;
            const btns = Array.from(root.querySelectorAll('div[role="button"], span[role="button"]'));
            for (const b of btns) {
                const txt = (b.innerText || '').trim();
                if (txt.includes('เกี่ยวข้องมากที่สุด') || txt.includes('Most relevant')) {
                    b.click();
                    break;
                }
            }
        }""")
        time.sleep(1)
        page.evaluate("""() => {
            const items = Array.from(document.querySelectorAll('div[role="menuitem"], span, div'));
            for (const item of items) {
                const txt = (item.innerText || '').trim();
                if (txt === 'ความคิดเห็นทั้งหมด' || txt === 'All comments') {
                    item.click();
                    break;
                }
            }
        }""")
        time.sleep(1.5)
    except Exception:
        pass

    for _ in range(3):
        clicked = page.evaluate("""() => {
            const root = document.querySelector('div[role="dialog"]') || document.querySelector('div[role="main"]') || document;
            let count = 0;
            const buttons = Array.from(root.querySelectorAll('div[role="button"], span[role="button"]'));
            for (const btn of buttons) {
                const txt = (btn.innerText || '').trim();
                if (
                    txt.includes('ตอบกลับ') || 
                    txt.includes('ความคิดเห็นก่อนหน้า') || 
                    txt.includes('ดูความคิดเห็นเพิ่มเติม') ||
                    txt.includes('View more replies') ||
                    txt.includes('View previous') ||
                    txt.includes('replies') ||
                    txt.includes('reply')
                ) {
                    btn.click();
                    count++;
                }
            }
            return count;
        }""")
        if clicked > 0:
            time.sleep(1.5)
        else:
            break

def extract_comments_from_page(page: Page) -> tuple[str, list]:
    """
    ดึงคอมเมนต์เฉพาะของโพสต์เป้าหมาย และจัดกลุ่มคำตอบกลับ (Replies) อย่างแม่นยำ
    """
    time.sleep(2)
    expand_comments_and_replies(page)

    post_author = POST_AUTHOR_NAME

    raw_extracted = page.evaluate("""() => {
        const results = [];
        
        let postRoot = document.querySelector('div[role="dialog"]');
        if (!postRoot) {
            postRoot = document.querySelector('div[role="main"]') || document.body;
        }

        const allArticles = Array.from(postRoot.querySelectorAll('div[role="article"]'));
        
        const commentArticles = allArticles.filter(art => {
            const label = (art.getAttribute('aria-label') || '').toLowerCase();
            return label.includes('ความคิดเห็น') || 
                   label.includes('ตอบกลับ') || 
                   label.includes('comment') || 
                   label.includes('reply');
        });

        commentArticles.forEach((art) => {
            const label = art.getAttribute('aria-label') || '';
            const fullText = art.innerText || '';

            // 1. ดึงชื่อผู้คอมเมนต์
            let author = '';
            if (label.includes('ความคิดเห็นโดย ')) {
                author = label.split('ความคิดเห็นโดย ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('การตอบกลับโดย ')) {
                author = label.split('การตอบกลับโดย ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('ตอบกลับโดย ')) {
                author = label.split('ตอบกลับโดย ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('Comment by ')) {
                author = label.split('Comment by ')[1].split(' at ')[0].split(' on ')[0].trim();
            } else if (label.includes('Reply by ')) {
                author = label.split('Reply by ')[1].split(' at ')[0].split(' on ')[0].trim();
            }

            if (!author) {
                const authorLink = art.querySelector('a span, a strong, strong');
                if (authorLink) {
                    author = authorLink.innerText.trim();
                }
            }

            // 2. ดึงข้อความคอมเมนต์
            const textNodes = Array.from(art.querySelectorAll('div[dir="auto"]'));
            const textParts = [];
            textNodes.forEach(tn => {
                const t = tn.innerText.trim();
                if (t && t !== author && !t.startsWith('ถูกใจ') && !t.startsWith('ตอบกลับ') && !t.startsWith('แชร์')) {
                    textParts.push(t);
                }
            });
            let text = textParts.join(' ');

            // ตรวจสอบว่ามีการแนบรูปภาพในคอมเมนต์หรือไม่ (เช่น แคปรูปเมนูมาสั่ง)
            let hasAttachedPhoto = false;
            const commentImages = Array.from(art.querySelectorAll('img'));
            for (const img of commentImages) {
                const w = img.naturalWidth || img.width || 0;
                const h = img.naturalHeight || img.height || 0;
                const alt = img.getAttribute('alt') || '';
                const src = img.getAttribute('src') || '';
                if ((w > 50 && h > 50) || alt.includes('รูปภาพ') || alt.includes('อาจเป็น') || src.includes('photo')) {
                    hasAttachedPhoto = true;
                    break;
                }
            }

            if (hasAttachedPhoto) {
                text = (text ? text + ' ' : '') + '[📷 มีแนบรูปภาพ]';
            }

            // 3. ตรวจสอบว่าเป็นคำตอบกลับหรือไม่
            const isReply = label.includes('ตอบกลับ') || label.includes('Reply');
            const hasAuthorBadge = fullText.includes('ผู้เขียน') || fullText.includes('Author');

            if (author || text) {
                results.push({
                    author: author,
                    text: text,
                    full_text: fullText,
                    has_author_badge: hasAuthorBadge,
                    has_image: hasAttachedPhoto,
                    is_reply: isReply
                });
            }
        });

        return results;
    }""")

    # จัดกลุ่มคอมเมนต์และคำตอบกลับ
    comments = []
    seen_signatures = set()

    for item in raw_extracted:
        author = item.get("author", "").strip()
        text = item.get("text", "").strip()
        is_reply = item.get("is_reply", False)
        has_author_badge = item.get("has_author_badge", False)
        full_text = item.get("full_text", "")

        if not text and not author:
            continue

        sig = f"{author}_{text}"
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        # ตรวจสอบเพิ่มเติม: ถ้าคนเขียนเป็นคนขาย/เจ้าของโพสต์ และข้อความเป็นการยืนยันรับออเดอร์
        # เช่น "Jerakanok Satthaporn รับออเดอร์ค่ะ" ให้ผูกเป็นคำตอบกลับของลูกค้ารายนั้นทันที!
        linked_to_customer = False
        author_lower = author.lower()
        is_seller = any(s.lower() in author_lower for s in SELLER_NAMES) or has_author_badge or (post_author and author_lower in post_author.lower())
        has_confirm_kw = any(kw in text.lower() for kw in CONFIRM_KEYWORDS)

        # เฉพาะกรณีที่มีคำยืนยันรับออเดอร์เท่านั้น ถึงจะนำไปผูกเป็นคำตอบรับของลูกค้าคนอื่น
        if has_confirm_kw and (is_seller or "รับออเดอร์" in text):
            for parent in reversed(comments):
                p_author = parent.get("author", "")
                # ถ้าข้อความของคนขายมีชื่อของลูกค้าคนนี้อยู่
                if p_author and (p_author in text or p_author.split()[0] in text):
                    parent["replies"].append({
                        "author": author,
                        "text": text,
                        "has_author_badge": has_author_badge
                    })
                    parent["full_thread_text"] += " " + text
                    linked_to_customer = True
                    break

        if linked_to_customer:
            continue

        # ถ้าเป็น Reply ทั่วไป ให้ผูกเข้ากับ parent ล่าสุด
        if is_reply and comments:
            comments[-1]["replies"].append({
                "author": author,
                "text": text,
                "has_author_badge": has_author_badge
            })
            comments[-1]["full_thread_text"] += " " + text
        else:
            # เป็นคอมเมนต์ระดับหลัก
            unique_str = f"{author}_{text[:50]}"
            c_id = hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:12]

            parent_item = {
                "id": c_id,
                "author": author,
                "text": text,
                "has_author_badge": has_author_badge,
                "replies": [],
                "full_thread_text": full_text
            }
            comments.append(parent_item)

    return post_author, comments
