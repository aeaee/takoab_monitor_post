import time
import hashlib
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import CHROME_PATH, USER_DATA_DIR, POST_AUTHOR_NAME, SELLER_NAMES, CONFIRM_KEYWORDS
from analyzer import check_is_seller

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

def expand_comments_and_replies(page: Page, max_scrolls: int = 6):
    """
    กดขยาย 'ความคิดเห็นทั้งหมด' เลื่อนอ่านคอมเมนต์ในคอนเทนเนอร์ที่ถูกต้อง
    และคลิกปุ่ม 'ดูความคิดเห็นเพิ่มเติม' / 'ดูการตอบกลับ ... รายการ' อย่างต่อเนื่อง
    """
    # 1. พยายามเลือกตัวกรอง 'ความคิดเห็นทั้งหมด' หรือ 'ใหม่ล่าสุด'
    try:
        page.evaluate("""() => {
            const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
            let postDialog = dialogs.find(d => {
                const label = d.getAttribute('aria-label') || '';
                if (label.includes('การแจ้งเตือน') || label.includes('Notifications') || label.includes('แชท') || label.includes('Chat')) return false;
                return d.querySelectorAll('div[role="article"]').length > 0 || d.innerText.includes('ความคิดเห็น');
            }) || document.querySelector('div[role="main"]') || document.body;

            const buttons = Array.from(postDialog.querySelectorAll('div[role="button"], span[role="button"]'));
            const filterBtn = buttons.find(b => {
                const txt = (b.innerText || '').trim();
                return txt.includes('เกี่ยวข้องมากที่สุด') || txt.includes('Most relevant');
            });
            if (filterBtn) filterBtn.click();
        }""")
        time.sleep(1.0)
        page.evaluate("""() => {
            const menuItems = Array.from(document.querySelectorAll('div[role="menuitem"], div[role="button"], span, div'));
            const target = menuItems.find(m => {
                const txt = (m.innerText || '').trim();
                return txt === 'ความคิดเห็นทั้งหมด' || txt === 'All comments' || txt === 'ใหม่ล่าสุด' || txt === 'Newest';
            });
            if (target) target.click();
        }""")
        time.sleep(1.2)
    except Exception:
        pass

    # 2. เลื่อนอ่านคอมเมนต์และคลิกขยายการตอบกลับเพิ่มเติม
    for _ in range(max_scrolls):
        try:
            page.evaluate("""() => {
                const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                let postDialog = dialogs.find(d => {
                    const label = d.getAttribute('aria-label') || '';
                    if (label.includes('การแจ้งเตือน') || label.includes('Notifications') || label.includes('แชท') || label.includes('Chat')) return false;
                    return d.querySelectorAll('div[role="article"]').length > 0 || d.innerText.includes('ความคิดเห็น');
                }) || document.querySelector('div[role="main"]') || document.body;

                // 2.1 ค้นหาคอนเทนเนอร์ที่มี scrollbar ด้านใน
                const elements = [postDialog, ...Array.from(postDialog.querySelectorAll('*'))];
                let scroller = null;
                let maxDiff = 0;
                for (const el of elements) {
                    const style = window.getComputedStyle(el);
                    if (['auto', 'scroll'].includes(style.overflowY) && el.scrollHeight > el.clientHeight + 50) {
                        const diff = el.scrollHeight - el.clientHeight;
                        if (diff > maxDiff) {
                            maxDiff = diff;
                            scroller = el;
                        }
                    }
                }

                // 2.2 คลิกปุ่มขยายความคิดเห็นและการตอบกลับ
                const buttons = Array.from(postDialog.querySelectorAll('div[role="button"], span[role="button"]'));
                for (const btn of buttons) {
                    const txt = (btn.innerText || '').trim();
                    if (
                        txt.includes('ดูความคิดเห็นเพิ่มเติม') || 
                        txt.includes('ดูความคิดเห็นก่อนหน้า') || 
                        txt.includes('ดูความคิดเห็นอีก') || 
                        txt.includes('ดูความเห็นเพิ่มเติม') || 
                        txt.includes('ดูการตอบกลับ') || 
                        txt.includes('การตอบกลับอีก') || 
                        txt.includes('รายการตอบกลับ') || 
                        txt.includes('ดูเพิ่มเติม') ||
                        txt.includes('View more comments') || 
                        txt.includes('View previous') || 
                        txt.includes('View more replies') || 
                        txt.includes('more replies') ||
                        txt.includes('See more')
                    ) {
                        if (txt !== 'ตอบกลับ' && txt !== 'Reply' && txt !== 'ถูกใจ' && txt !== 'Like' && txt !== 'แชร์' && txt !== 'Share') {
                            btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                            btn.click();
                        }
                    }
                }

                // 2.3 เลื่อนหน้าจอลงเพื่อโหลดคอมเมนต์ใหม่
                if (scroller) {
                    scroller.scrollTop += 850;
                } else {
                    window.scrollBy(0, 850);
                }
            }""")
        except Exception:
            pass

        time.sleep(1.2)

def extract_comments_from_page(page: Page, post_url: str = "") -> tuple[str, list]:
    """
    ดึงคอมเมนต์เฉพาะของโพสต์เป้าหมาย และจัดกลุ่มคำตอบกลับ (Replies) อย่างแม่นยำ
    """
    time.sleep(1.5)
    print("   📜 กำลังเลื่อนอ่านและขยายความคิดเห็นทั้งหมดในโพสต์...")
    expand_comments_and_replies(page, max_scrolls=6)

    post_author = POST_AUTHOR_NAME

    raw_extracted = page.evaluate("""() => {
        const results = [];
        
        const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        let postRoot = dialogs.find(d => {
            const label = d.getAttribute('aria-label') || '';
            if (label.includes('การแจ้งเตือน') || label.includes('Notifications') || label.includes('แชท') || label.includes('Chat')) return false;
            return d.querySelectorAll('div[role="article"]').length > 0 || d.innerText.includes('ความคิดเห็น');
        });
        
        if (!postRoot) {
            postRoot = document.querySelector('div[role="main"]') || document.body;
        }

        const allArticles = Array.from(postRoot.querySelectorAll('div[role="article"]'));
        
        const commentArticles = allArticles.filter((art, idx) => {
            const label = (art.getAttribute('aria-label') || '').toLowerCase();
            if (
                label.includes('ความคิดเห็น') || 
                label.includes('ตอบกลับ') || 
                label.includes('comment') || 
                label.includes('reply')
            ) {
                return true;
            }
            // สำรอง: กรณีไม่มี aria-label ให้ดูว่ามีปุ่ม 'ถูกใจ' / 'ตอบกลับ' และไม่ใช่ตัวเนื้อหาโพสต์หลัก
            const txt = art.innerText || '';
            return idx > 0 && txt.includes('ถูกใจ') && (txt.includes('ตอบกลับ') || txt.includes('แชร์'));
        });

        commentArticles.forEach((art) => {
            const label = art.getAttribute('aria-label') || '';
            const fullText = art.innerText || '';

            // 1. ดึงชื่อผู้คอมเมนต์ และผู้ที่ถูกตอบกลับ (ถ้ามี)
            let author = '';
            let replyTarget = '';

            if (label.includes('ความคิดเห็นจาก ')) {
                author = label.split('ความคิดเห็นจาก ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('ความคิดเห็นโดย ')) {
                author = label.split('ความคิดเห็นโดย ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('ข้อความตอบกลับจาก ')) {
                author = label.split('ข้อความตอบกลับจาก ')[1].split(' ต่อความคิดเห็นของ')[0].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('การตอบกลับโดย ')) {
                author = label.split('การตอบกลับโดย ')[1].split(' ต่อความคิดเห็นของ')[0].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('ตอบกลับโดย ')) {
                author = label.split('ตอบกลับโดย ')[1].split(' ต่อความคิดเห็นของ')[0].split(' เมื่อ')[0].split(' at ')[0].trim();
            } else if (label.includes('Comment by ')) {
                author = label.split('Comment by ')[1].split(' at ')[0].split(' on ')[0].trim();
            } else if (label.includes('Reply by ')) {
                author = label.split('Reply by ')[1].split(' to ')[0].split(' at ')[0].split(' on ')[0].trim();
            }

            if (label.includes('ต่อความคิดเห็นของ ')) {
                replyTarget = label.split('ต่อความคิดเห็นของ ')[1].split(' เมื่อ')[0].split(' at ')[0].trim();
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

            // ตรวจสอบว่ามีการแนบรูปภาพหรือส่งสติกเกอร์ในคอมเมนต์หรือไม่
            let hasAttachedPhoto = false;
            let isSticker = false;
            const commentImages = Array.from(art.querySelectorAll('img'));
            for (const img of commentImages) {
                const w = img.naturalWidth || img.width || 0;
                const h = img.naturalHeight || img.height || 0;
                const alt = (img.getAttribute('alt') || '').toLowerCase();
                const src = (img.getAttribute('src') || '').toLowerCase();

                if (alt.includes('สติกเกอร์') || alt.includes('sticker') || src.includes('/stickers/') || src.includes('sticker')) {
                    isSticker = true;
                    continue;
                }
                if ((w > 50 && h > 50) || alt.includes('รูปภาพ') || alt.includes('อาจเป็น') || src.includes('photo')) {
                    hasAttachedPhoto = true;
                    break;
                }
            }

            if (isSticker && !hasAttachedPhoto) {
                text = (text ? text + ' ' : '') + '[สติกเกอร์]';
            } else if (hasAttachedPhoto) {
                text = (text ? text + ' ' : '') + '[📷 มีแนบรูปภาพ]';
            }

            // 3. ตรวจสอบว่าเป็นคำตอบกลับหรือไม่
            const isReply = label.includes('ตอบกลับ') || label.includes('Reply') || !!replyTarget;
            const hasAuthorBadge = fullText.includes('ผู้เขียน') || fullText.includes('Author');

            if (author || text) {
                results.push({
                    author: author,
                    reply_target: replyTarget,
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
        reply_target = item.get("reply_target", "").strip()
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
        is_seller = check_is_seller(author, has_author_badge, post_author)
        has_confirm_kw = any(kw in text.lower() for kw in CONFIRM_KEYWORDS)

        # กรณีระบุเป้าหมายที่ตอบกลับชัดเจนจาก aria-label (เช่น "ต่อความคิดเห็นของ Niparat Thummakhan")
        if reply_target:
            target_lower = reply_target.lower()
            for parent in reversed(comments):
                p_author = parent.get("author", "").lower()
                if p_author and (p_author in target_lower or target_lower in p_author or p_author.split()[0] in target_lower):
                    parent["replies"].append({
                        "author": author,
                        "text": text,
                        "has_author_badge": has_author_badge
                    })
                    parent["full_thread_text"] += " " + text
                    linked_to_customer = True
                    break

        # หรือกรณีคนขายพิมพ์ชื่อลูกค้าในข้อความตอบรับ
        if not linked_to_customer and has_confirm_kw and (is_seller or "รับออเดอร์" in text):
            for parent in reversed(comments):
                p_author = parent.get("author", "")
                if p_author and (p_author.lower() in text.lower() or p_author.split()[0].lower() in text.lower()):
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
            post_hash = hashlib.md5(post_url.encode("utf-8")).hexdigest()[:6] if post_url else ""
            unique_str = f"{post_hash}_{author}_{text[:50]}"
            c_id = hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:12]

            parent_item = {
                "id": c_id,
                "author": author,
                "text": text,
                "has_author_badge": has_author_badge,
                "replies": [],
                "full_thread_text": full_text,
                "post_url": post_url
            }
            comments.append(parent_item)

    return post_author, comments
