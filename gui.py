import sys
import os
import re
import queue
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

# Enable High-DPI awareness on Windows so text renders razor-sharp
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

class TakoabMonitorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Takoab Post Monitor - ระบบเฝ้าดูคอมเมนต์ออเดอร์")
        self.root.geometry("1180x940")
        self.root.minsize(980, 750)
        self.root.configure(bg="#0f172a")

        # Select the best native Thai font for Windows
        self._setup_thai_fonts()

        # Process management
        self.process = None
        self.group_id = "1111870942162462"
        self.log_queue = queue.Queue()
        self.is_running = False
        self.tg_poll_active = True
        self.tg_poller_thread = threading.Thread(target=self._telegram_poller_loop, daemon=True)
        self.tg_poller_thread.start()

        # Apply dark theme styling
        self._setup_styles()

        # Build UI layout
        self._create_widgets()

        # Load values from .env
        self.load_env_settings()

        # Start periodic log queue consumer
        self.root.after(100, self._process_log_queue)

        # Handle window close cleanly
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_thai_fonts(self):
        """กำหนดฟอนต์ภาษาไทยที่คมชัดและแสดงสระ-วรรณยุกต์ได้ถูกต้อง 100% บน Windows"""
        import tkinter.font as tkfont
        available = set(tkfont.families())

        # ลำดับฟอนต์ภาษาไทยที่สวยและคมชัดที่สุดบน Windows
        if "Leelawadee UI" in available:
            self.font_family = "Leelawadee UI"
        elif "Tahoma" in available:
            self.font_family = "Tahoma"
        elif "Segoe UI" in available:
            self.font_family = "Segoe UI"
        else:
            self.font_family = "TkDefaultFont"

        self.font_title = (self.font_family, 15, "bold")
        self.font_subtitle = (self.font_family, 10)
        self.font_badge = (self.font_family, 10, "bold")
        self.font_card_title = (self.font_family, 11, "bold")
        self.font_btn_main = (self.font_family, 11, "bold")
        self.font_btn_sub = (self.font_family, 10)
        self.font_label = (self.font_family, 10)
        self.font_label_bold = (self.font_family, 10, "bold")
        self.font_input = (self.font_family, 10)
        self.font_log = (self.font_family, 10)

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Color scheme (Modern dark slate)
        self.c_bg = "#0f172a"
        self.c_card = "#1e293b"
        self.c_card_border = "#334155"
        self.c_text = "#f8fafc"
        self.c_muted = "#94a3b8"
        self.c_input_bg = "#090d16"
        self.c_input_border = "#334155"
        self.c_start = "#10b981"
        self.c_start_hover = "#059669"
        self.c_stop = "#ef4444"
        self.c_stop_hover = "#dc2626"
        self.c_btn = "#334155"
        self.c_btn_hover = "#475569"
        self.c_accent = "#2563eb"
        self.c_accent_hover = "#1d4ed8"

    def _create_widgets(self):
        # Main container with 2 columns: Left = Settings & Controls, Right = Live Logs
        main_frame = tk.Frame(self.root, bg=self.c_bg)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Header bar
        header_frame = tk.Frame(main_frame, bg=self.c_bg)
        header_frame.pack(fill=tk.X, pady=(0, 12))

        title_label = tk.Label(
            header_frame,
            text="🐙 Takoab Post Order Monitor",
            font=self.font_title,
            fg=self.c_text,
            bg=self.c_bg
        )
        title_label.pack(side=tk.LEFT)

        subtitle_label = tk.Label(
            header_frame,
            text="ระบบเฝ้าดูคอมเมนต์ Facebook & แจ้งเตือนออเดอร์",
            font=self.font_subtitle,
            fg=self.c_muted,
            bg=self.c_bg
        )
        subtitle_label.pack(side=tk.LEFT, padx=(12, 0), pady=(3, 0))

        # Status badge in header
        self.status_badge = tk.Label(
            header_frame,
            text="⚪ สถานะ: ยังไม่ได้เริ่มทำงาน",
            font=self.font_badge,
            fg="#94a3b8",
            bg="#1e293b",
            padx=14,
            pady=6,
            relief=tk.FLAT
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Split content: Left (Settings & Control), Right (Console Log)
        content_pane = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, bg=self.c_bg, bd=0, sashwidth=6)
        content_pane.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(content_pane, bg=self.c_bg, width=470)
        right_panel = tk.Frame(content_pane, bg=self.c_bg)

        content_pane.add(left_panel, minsize=430)
        content_pane.add(right_panel, minsize=480)

        # -------------------------------------------------------------
        # LEFT PANEL: Service Control & Settings
        # -------------------------------------------------------------
        
        # 1. Quick Control Card
        control_card = tk.LabelFrame(
            left_panel,
            text=" สั่งเปิด / ปิด เซอร์วิส ",
            font=self.font_card_title,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=8
        )
        control_card.pack(fill=tk.X, pady=(0, 8))

        btn_row = tk.Frame(control_card, bg=self.c_card)
        btn_row.pack(fill=tk.X, pady=(2, 8))

        self.btn_start = tk.Button(
            btn_row,
            text="▶ เริ่มทำงาน (Start)",
            font=self.font_btn_main,
            fg="white",
            bg=self.c_start,
            activebackground=self.c_start_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self.start_service
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.btn_stop = tk.Button(
            btn_row,
            text="⏹ หยุดทำงาน (Stop)",
            font=self.font_btn_main,
            fg="white",
            bg=self.c_stop,
            activebackground=self.c_stop_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=8,
            state=tk.DISABLED,
            command=self.stop_service
        )
        self.btn_stop.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        # Auxiliary buttons (Login / Test notify / Clear cache)
        aux_row = tk.Frame(control_card, bg=self.c_card)
        aux_row.pack(fill=tk.X, pady=(4, 0))

        self.btn_login = tk.Button(
            aux_row,
            text="🔑 ล็อกอิน Facebook",
            font=self.font_btn_sub,
            fg=self.c_text,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=5,
            command=self.open_facebook_login
        )
        self.btn_login.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_test = tk.Button(
            aux_row,
            text="🔔 ทดสอบแจ้งเตือน",
            font=self.font_btn_sub,
            fg=self.c_text,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=5,
            command=self.test_notification
        )
        self.btn_test.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.btn_clear_cache = tk.Button(
            aux_row,
            text="🗑 ล้างประวัติแจ้งเตือน",
            font=self.font_btn_sub,
            fg=self.c_text,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=5,
            command=self.clear_cache
        )
        self.btn_clear_cache.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Create Facebook Post Action
        post_btn_row = tk.Frame(control_card, bg=self.c_card)
        post_btn_row.pack(fill=tk.X, pady=(6, 2))

        self.btn_create_post = tk.Button(
            post_btn_row,
            text="📢 สร้างโพสต์เปิดร้านใหม่ลงกลุ่ม Facebook (Auto Post)",
            font=self.font_btn_main,
            fg="white",
            bg="#0d9488",
            activebackground="#0f766e",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=7,
            command=self.open_create_post_dialog
        )
        self.btn_create_post.pack(fill=tk.X, expand=True)

        # 2. Test Order into Telegram Card
        test_order_card = tk.LabelFrame(
            left_panel,
            text=" 🧪 ทดสอบส่งออเดอร์เข้า Telegram ",
            font=self.font_card_title,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=8
        )
        test_order_card.pack(fill=tk.X, pady=(0, 8))

        # Customer Name Input Row
        row_test_name = tk.Frame(test_order_card, bg=self.c_card)
        row_test_name.pack(fill=tk.X, pady=(0, 6))

        lbl_test_name = tk.Label(
            row_test_name,
            text="ชื่อลูกค้า:",
            font=self.font_label_bold,
            fg=self.c_text,
            bg=self.c_card,
            width=9,
            anchor="w"
        )
        lbl_test_name.pack(side=tk.LEFT)

        self.ent_test_name = tk.Entry(
            row_test_name,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1
        )
        self.ent_test_name.insert(0, "คุณอุ้มฤทัย (ทดสอบ)")
        self.ent_test_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._enable_context_menu_and_shortcuts(self.ent_test_name)

        # Comment Text Input Row
        row_test_comment = tk.Frame(test_order_card, bg=self.c_card)
        row_test_comment.pack(fill=tk.X, pady=(0, 6))

        lbl_test_comment = tk.Label(
            row_test_comment,
            text="คอมเมนต์:",
            font=self.font_label_bold,
            fg=self.c_text,
            bg=self.c_card,
            width=9,
            anchor="nw"
        )
        lbl_test_comment.pack(side=tk.LEFT, anchor="nw", pady=(3, 0))

        self.txt_test_comment = tk.Text(
            row_test_comment,
            height=2,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            wrap=tk.WORD
        )
        self.txt_test_comment.insert("1.0", "มาม่าไก่กรอบคลุกซอส ไม่เผ็ด (แยกสาหร่าย) 2 ไก่กรอบคลุกซอสเกาหลี 1 194/119 ซ.6/2 ใช้ไทยพลัสค่ะ")
        self.txt_test_comment.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._enable_context_menu_and_shortcuts(self.txt_test_comment)

        # Quick Presets Row
        preset_row = tk.Frame(test_order_card, bg=self.c_card)
        preset_row.pack(fill=tk.X, pady=(0, 6))

        lbl_preset = tk.Label(
            preset_row,
            text="ตัวอย่างเร็ว:",
            font=self.font_btn_sub,
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w"
        )
        lbl_preset.pack(side=tk.LEFT, padx=(0, 4))

        btn_p1 = tk.Button(
            preset_row,
            text="🍜 มาม่าไก่กรอบ",
            font=self.font_btn_sub,
            fg=self.c_text,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=6,
            pady=1,
            command=lambda: self._set_test_preset("มาม่าไก่กรอบคลุกซอส ไม่เผ็ด (แยกสาหร่าย) 2 ไก่กรอบคลุกซอสเกาหลี 1 194/119 ซ.6/2 ใช้ไทยพลัสค่ะ", "คุณอุ้มฤทัย (ทดสอบ)")
        )
        btn_p1.pack(side=tk.LEFT, padx=2)

        btn_p2 = tk.Button(
            preset_row,
            text="🐙 ทาโกะยากิ",
            font=self.font_btn_sub,
            fg=self.c_text,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=6,
            pady=1,
            command=lambda: self._set_test_preset("ทาโกะยากิปลาหมึก ปูอัด ไส้กรอก S 1 สปาเก็ตตี้เบคอนพริกแห้ง 1 ข้าวไก่กรอบซอสเทอริยากิ 1 199/125 ซ.9 สแกน หน้าบ้าน", "คุณสมชาย (ทดสอบ)")
        )
        btn_p2.pack(side=tk.LEFT, padx=2)

        btn_clear_test = tk.Button(
            preset_row,
            text="🧹 ล้าง",
            font=self.font_btn_sub,
            fg=self.c_muted,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=6,
            pady=1,
            command=self._clear_test_order_inputs
        )
        btn_clear_test.pack(side=tk.LEFT, padx=2)

        # Test Order Action Row
        test_action_row = tk.Frame(test_order_card, bg=self.c_card)
        test_action_row.pack(fill=tk.X, pady=(2, 0))

        self.btn_send_test_order = tk.Button(
            test_action_row,
            text="🚀 ส่งทดสอบเข้า Telegram",
            font=self.font_btn_main,
            fg="white",
            bg="#0284c7",
            activebackground="#0369a1",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=5,
            command=self.send_test_order_action
        )
        self.btn_send_test_order.pack(side=tk.LEFT)

        self.lbl_test_order_status = tk.Label(
            test_action_row,
            text="",
            font=self.font_btn_sub,
            fg="#10b981",
            bg=self.c_card
        )
        self.lbl_test_order_status.pack(side=tk.LEFT, padx=(10, 0))

        # 3. Configuration Settings Card
        settings_card = tk.LabelFrame(
            left_panel,
            text=" ตั้งค่าระบบ (.env) ",
            font=self.font_card_title,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=10
        )
        settings_card.pack(fill=tk.X, pady=(0, 6))

        # Post URLs Header & Action Buttons
        url_header = tk.Frame(settings_card, bg=self.c_card)
        url_header.pack(fill=tk.X, pady=(0, 4))

        lbl_urls = tk.Label(
            url_header,
            text="📌 ลิงก์โพสต์ Facebook (1 บรรทัดต่อ 1 โพสต์):",
            font=self.font_label_bold,
            fg=self.c_text,
            bg=self.c_card,
            anchor="w"
        )
        lbl_urls.pack(side=tk.LEFT)

        btn_clear_urls = tk.Button(
            url_header,
            text="🧹 ล้าง",
            font=self.font_btn_sub,
            fg=self.c_muted,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            activeforeground=self.c_text,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.clear_urls
        )
        btn_clear_urls.pack(side=tk.RIGHT)

        btn_paste_url = tk.Button(
            url_header,
            text="📋 วางลิงก์ (Paste)",
            font=self.font_btn_sub,
            fg="white",
            bg=self.c_accent,
            activebackground=self.c_accent_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self.paste_to_urls
        )
        btn_paste_url.pack(side=tk.RIGHT, padx=(0, 6))

        self.btn_quick_apply = tk.Button(
            url_header,
            text="⚡ อัปเดตลิงก์ทันที",
            font=self.font_btn_sub,
            fg="white",
            bg="#059669",
            activebackground="#047857",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self.quick_update_urls
        )
        self.btn_quick_apply.pack(side=tk.RIGHT, padx=(0, 6))

        btn_post_quick = tk.Button(
            url_header,
            text="📢 สร้างโพสต์",
            font=self.font_btn_sub,
            fg="white",
            bg="#0d9488",
            activebackground="#0f766e",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.open_create_post_dialog
        )
        btn_post_quick.pack(side=tk.RIGHT, padx=(0, 6))

        self.txt_urls = scrolledtext.ScrolledText(
            settings_card,
            height=4,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            spacing1=3,
            spacing2=3,
            spacing3=3,
            undo=True
        )
        self.txt_urls.pack(fill=tk.X, expand=False, pady=(0, 6))

        # Check Interval
        row_interval = tk.Frame(settings_card, bg=self.c_card)
        row_interval.pack(fill=tk.X, pady=4)

        lbl_interval = tk.Label(
            row_interval,
            text="⏱ รอบเวลาตรวจ (วินาที):",
            font=self.font_label,
            fg=self.c_text,
            bg=self.c_card,
            width=23,
            anchor="w"
        )
        lbl_interval.pack(side=tk.LEFT)

        self.ent_interval = tk.Entry(
            row_interval,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT
        )
        self.ent_interval.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # Operating hours
        row_hours = tk.Frame(settings_card, bg=self.c_card)
        row_hours.pack(fill=tk.X, pady=4)

        lbl_hours = tk.Label(
            row_hours,
            text="⏰ เวลาเปิดร้าน (เช่น 10:00-20:00):",
            font=self.font_label,
            fg=self.c_text,
            bg=self.c_card,
            width=23,
            anchor="w"
        )
        lbl_hours.pack(side=tk.LEFT)

        self.ent_hours = tk.Entry(
            row_hours,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT
        )
        self.ent_hours.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # Author/Seller names
        row_author = tk.Frame(settings_card, bg=self.c_card)
        row_author.pack(fill=tk.X, pady=4)

        lbl_author = tk.Label(
            row_author,
            text="👤 ชื่อเฟสคนขาย / ตอบรับออเดอร์:",
            font=self.font_label,
            fg=self.c_text,
            bg=self.c_card,
            width=23,
            anchor="w"
        )
        lbl_author.pack(side=tk.LEFT)

        self.ent_author = tk.Entry(
            row_author,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT
        )
        self.ent_author.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        # Telegram Status Checkbox
        self.var_telegram_idle = tk.BooleanVar(value=False)
        self.chk_telegram_idle = tk.Checkbutton(
            settings_card,
            text="📱 ส่งข้อความสถานะปกติทุกรอบเข้า Telegram (แบบไร้เสียง)",
            variable=self.var_telegram_idle,
            font=self.font_label,
            fg=self.c_text,
            bg=self.c_card,
            selectcolor=self.c_input_bg,
            activebackground=self.c_card,
            activeforeground=self.c_text
        )
        self.chk_telegram_idle.pack(fill=tk.X, pady=(6, 4))

        # Auto-reply on Facebook Section
        auto_reply_frame = tk.Frame(settings_card, bg=self.c_card)
        auto_reply_frame.pack(fill=tk.X, pady=(4, 6))

        self.var_auto_reply = tk.BooleanVar(value=False)

        chk_header = tk.Frame(auto_reply_frame, bg=self.c_card)
        chk_header.pack(fill=tk.X)

        self.chk_auto_reply = tk.Checkbutton(
            chk_header,
            text="💬 ตอบกลับคอมเมนต์ลูกค้าบน Facebook อัตโนมัติ (Auto-Reply)",
            variable=self.var_auto_reply,
            font=self.font_label_bold,
            fg="#38bdf8",
            bg=self.c_card,
            selectcolor=self.c_input_bg,
            activebackground=self.c_card,
            activeforeground="#38bdf8",
            command=self._update_auto_reply_badge
        )
        self.chk_auto_reply.pack(side=tk.LEFT)

        self.lbl_auto_reply_badge = tk.Label(
            chk_header,
            text="[ ปิดใช้งาน ]",
            font=self.font_btn_sub,
            fg="#94a3b8",
            bg=self.c_card
        )
        self.lbl_auto_reply_badge.pack(side=tk.LEFT, padx=(8, 0))

        row_reply_msg = tk.Frame(auto_reply_frame, bg=self.c_card)
        row_reply_msg.pack(fill=tk.X, pady=(4, 2))

        lbl_reply_msg = tk.Label(
            row_reply_msg,
            text="   ข้อความตอบรับ:",
            font=self.font_label,
            fg=self.c_text,
            bg=self.c_card,
            width=23,
            anchor="w"
        )
        lbl_reply_msg.pack(side=tk.LEFT)

        self.ent_auto_reply_msg = tk.Entry(
            row_reply_msg,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT
        )
        self.ent_auto_reply_msg.insert(0, "รับออเดอร์เรียบร้อยแล้วค่ะ ขอบคุณมากนะคะ 🙏")
        self.ent_auto_reply_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self._enable_context_menu_and_shortcuts(self.ent_auto_reply_msg)

        lbl_reply_hint = tk.Label(
            auto_reply_frame,
            text="   💡 ใส่ {name} ในข้อความเพื่อแทนชื่อลูกค้าอัตโนมัติ (เช่น 'รับออเดอร์คุณ {name} แล้วค่ะ')",
            font=self.font_btn_sub,
            fg=self.c_muted,
            bg=self.c_card,
            anchor="w"
        )
        lbl_reply_hint.pack(anchor="w", pady=(0, 2))

        # Save Settings Button & Feedback label
        save_row = tk.Frame(settings_card, bg=self.c_card)
        save_row.pack(fill=tk.X, pady=(4, 0))

        self.btn_save = tk.Button(
            save_row,
            text="💾 บันทึกการตั้งค่าลง .env",
            font=self.font_btn_main,
            fg="white",
            bg=self.c_accent,
            activebackground=self.c_accent_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=7,
            command=self.save_env_settings
        )
        self.btn_save.pack(side=tk.LEFT)

        self.btn_save_and_check = tk.Button(
            save_row,
            text="⚡ อัปเดตลิงก์ & เริ่มตรวจทันที",
            font=self.font_btn_main,
            fg="white",
            bg="#059669",
            activebackground="#047857",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=7,
            command=self.quick_update_urls
        )
        self.btn_save_and_check.pack(side=tk.LEFT, padx=(8, 0))

        self.lbl_save_status = tk.Label(
            save_row,
            text="",
            font=self.font_label,
            fg="#10b981",
            bg=self.c_card
        )
        self.lbl_save_status.pack(side=tk.LEFT, padx=(10, 0))

        # -------------------------------------------------------------
        # RIGHT PANEL: Live Monitor Logs
        # -------------------------------------------------------------
        log_card = tk.LabelFrame(
            right_panel,
            text=" 📋 บันทึกการทำงานสด (Live Logs) ",
            font=self.font_card_title,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=12
        )
        log_card.pack(fill=tk.BOTH, expand=True)

        # Log toolbar
        log_toolbar = tk.Frame(log_card, bg=self.c_card)
        log_toolbar.pack(fill=tk.X, pady=(0, 6))

        lbl_log_hint = tk.Label(
            log_toolbar,
            text="ข้อความรายงานสถานะจากบอทแบบเรียลไทม์:",
            font=self.font_subtitle,
            fg=self.c_muted,
            bg=self.c_card
        )
        lbl_log_hint.pack(side=tk.LEFT)

        btn_clear_log = tk.Button(
            log_toolbar,
            text="ล้างหน้าจอ Log",
            font=self.font_btn_sub,
            fg=self.c_muted,
            bg=self.c_btn,
            activebackground=self.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self.clear_logs
        )
        btn_clear_log.pack(side=tk.RIGHT)

        # Log Text Box with proper Thai line spacing
        self.txt_log = scrolledtext.ScrolledText(
            log_card,
            wrap=tk.WORD,
            font=self.font_log,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            spacing1=3,
            spacing2=3,
            spacing3=3
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Enable Right-Click context menus & Thai keyboard shortcut support (Ctrl+V, Ctrl+C, Ctrl+A)
        self._enable_context_menu_and_shortcuts(self.txt_urls)
        self._enable_context_menu_and_shortcuts(self.ent_interval)
        self._enable_context_menu_and_shortcuts(self.ent_hours)
        self._enable_context_menu_and_shortcuts(self.ent_author)
        self._enable_context_menu_and_shortcuts(self.txt_log, readonly=True)

        self.log_message("[*] Takoab Monitor พร้อมทำงาน กรุณาตรวจสอบลิงก์แล้วกด [เริ่มทำงาน]\n")

    def clear_urls(self):
        """ล้างข้อความในช่องลิงก์โพสต์"""
        self.txt_urls.delete("1.0", tk.END)
        self.txt_urls.focus_set()

    def paste_to_urls(self):
        """วางลิงก์จากคลิปบอร์ดลงในช่องลิงก์โพสต์โดยตรง"""
        try:
            text = self.root.clipboard_get().strip()
        except Exception:
            messagebox.showinfo(
                "คลิปบอร์ดว่าง", 
                "ไม่พบข้อความในคลิปบอร์ด\nกรุณากดคัดลอก (Copy) ลิงก์โพสต์ Facebook ก่อนกดปุ่มนี้ครับ"
            )
            return

        if not text:
            return

        cleaned_lines = []
        for line in text.splitlines():
            s = line.strip().strip('"').strip("'")
            if s:
                cleaned_lines.append(s)
        pasted_text = "\n".join(cleaned_lines) if cleaned_lines else text

        try:
            # หากมีการไฮไลต์เลือกข้อความไว้ ให้แทนที่ตำแหน่งที่เลือก
            self.txt_urls.delete("sel.first", "sel.last")
            self.txt_urls.insert(tk.INSERT, pasted_text)
        except tk.TclError:
            current = self.txt_urls.get("1.0", tk.END).strip()
            if not current:
                self.txt_urls.insert("1.0", pasted_text)
            else:
                # ถ้ามีลิงก์เดิมอยู่แล้วและเคอร์เซอร์อยู่ท้ายสุด ให้ขึ้นบรรทัดใหม่
                insert_idx = self.txt_urls.index(tk.INSERT)
                end_idx = self.txt_urls.index("end-1c")
                if insert_idx == end_idx:
                    separator = "\n" if not current.endswith("\n") else ""
                    self.txt_urls.insert(tk.END, separator + pasted_text)
                else:
                    self.txt_urls.insert(tk.INSERT, pasted_text)

        self.txt_urls.focus_set()
        self.txt_urls.see(tk.INSERT)
        self.log_message("[*] นำเข้าลิงก์จากคลิปบอร์ดเรียบร้อยแล้ว (อย่าลืมกด [💾 บันทึกการตั้งค่า])\n")

    def _enable_context_menu_and_shortcuts(self, widget, readonly=False):
        """
        1. เพิ่มเมนูคลิกขวา (ตัด, คัดลอก, วาง, เลือกทั้งหมด) สำหรับทั้ง Text และ Entry
        2. แก้ไขปัญหาคีย์ลัด Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A, Ctrl+Z ไม่ทำงานบน Windows
           เมื่อผู้ใช้เปิดสลับแป้นพิมพ์เป็นภาษาไทย (TH)
        """
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=self.c_card,
            fg=self.c_text,
            activebackground=self.c_accent,
            activeforeground="white",
            font=self.font_input,
            bd=1,
            relief=tk.SOLID
        )

        def do_cut():
            do_copy()
            if not readonly:
                try:
                    if isinstance(widget, tk.Text):
                        widget.delete("sel.first", "sel.last")
                    elif isinstance(widget, tk.Entry):
                        widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass

        def do_copy():
            try:
                if isinstance(widget, tk.Text):
                    text = widget.get("sel.first", "sel.last")
                elif isinstance(widget, tk.Entry):
                    text = widget.selection_get()
                else:
                    return
                if text:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(text)
            except (tk.TclError, Exception):
                pass

        def do_paste():
            if readonly:
                return
            try:
                text = self.root.clipboard_get()
            except Exception:
                return
            if not text:
                return
            try:
                if isinstance(widget, tk.Text):
                    try:
                        widget.delete("sel.first", "sel.last")
                    except tk.TclError:
                        pass
                    widget.insert(tk.INSERT, text)
                    widget.see(tk.INSERT)
                elif isinstance(widget, tk.Entry):
                    try:
                        widget.delete("sel.first", "sel.last")
                    except tk.TclError:
                        pass
                    widget.insert(tk.INSERT, text)
            except Exception:
                pass

        def do_select_all():
            try:
                if isinstance(widget, tk.Text):
                    widget.tag_add("sel", "1.0", "end-1c")
                    widget.mark_set(tk.INSERT, "1.0")
                elif isinstance(widget, tk.Entry):
                    widget.selection_range(0, tk.END)
                    widget.icursor(tk.END)
            except Exception:
                pass

        if not readonly:
            menu.add_command(label="✂ ตัด (Cut)", command=do_cut, accelerator="Ctrl+X")
        menu.add_command(label="📄 คัดลอก (Copy)", command=do_copy, accelerator="Ctrl+C")
        if not readonly:
            menu.add_command(label="📋 วาง (Paste)", command=do_paste, accelerator="Ctrl+V")
        menu.add_separator()
        menu.add_command(label="🔘 เลือกทั้งหมด (Select All)", command=do_select_all, accelerator="Ctrl+A")

        def show_popup(event):
            widget.focus_set()
            if isinstance(widget, tk.Entry):
                try:
                    if not widget.selection_present():
                        widget.icursor(widget.index(f"@{event.x}"))
                except Exception:
                    pass
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # คลิกขวา (Windows / Linux: Button-3, macOS: Button-2 หรือ Button-3)
        widget.bind("<Button-3>", show_popup)
        if sys.platform == "darwin":
            widget.bind("<Button-2>", show_popup)

        # จัดการปุ่มลัดเมื่อคีย์บอร์ดถูกสลับเป็นภาษาไทย (Windows Keycode: 86=V, 67=C, 88=X, 65=A, 90=Z)
        def on_key_press(event):
            is_mod = bool((event.state & 4) or (sys.platform == "darwin" and (event.state & 8)))
            if not is_mod:
                return None
            code = event.keycode
            sym = (event.keysym or "").lower()
            if code == 86 or sym == "v":
                if not readonly:
                    do_paste()
                    return "break"
            elif code == 67 or sym == "c":
                do_copy()
                return "break"
            elif code == 88 or sym == "x":
                if not readonly:
                    do_cut()
                    return "break"
            elif code == 65 or sym == "a":
                do_select_all()
                return "break"
            elif code == 90 or sym == "z":
                if not readonly and isinstance(widget, tk.Text):
                    try:
                        widget.edit_undo()
                    except tk.TclError:
                        pass
                    return "break"
            return None

        widget.bind("<KeyPress>", on_key_press)

    # -----------------------------------------------------------------
    # Configuration Load / Save (.env)
    # -----------------------------------------------------------------
    def _update_auto_reply_badge(self):
        """อัปเดตป้ายสถานะเปิด/ปิดการตอบกลับอัตโนมัติ"""
        if self.var_auto_reply.get():
            self.lbl_auto_reply_badge.config(text="[ เปิดใช้งาน ]", fg="#10b981")
        else:
            self.lbl_auto_reply_badge.config(text="[ ปิดใช้งาน ]", fg="#94a3b8")

    def load_env_settings(self):
        """อ่านค่าจาก .env มาแสดงใน UI"""
        if not ENV_PATH.exists():
            return

        env_dict = {}
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
        except Exception as e:
            self.log_message(f"[!] เกิดข้อผิดพลาดในการอ่าน .env: {e}\n")
            return

        self.group_id = env_dict.get("GROUP_ID", "1111870942162462")
        # URLs
        raw_urls = env_dict.get("POST_URLS", "") or env_dict.get("POST_URL", "")
        clean_urls = [u.strip().strip('"').strip("'") for u in raw_urls.replace("\n", ",").split(",") if u.strip()]
        self.txt_urls.delete("1.0", tk.END)
        if clean_urls:
            self.txt_urls.insert(tk.END, "\n".join(clean_urls))

        # Interval
        self.ent_interval.delete(0, tk.END)
        self.ent_interval.insert(0, env_dict.get("CHECK_INTERVAL", "180"))

        # Hours
        self.ent_hours.delete(0, tk.END)
        self.ent_hours.insert(0, env_dict.get("OPERATING_HOURS", "10:00-20:00"))

        # Author
        self.ent_author.delete(0, tk.END)
        self.ent_author.insert(0, env_dict.get("POST_AUTHOR_NAME", ""))

        # Telegram idle
        idle_val = env_dict.get("SEND_IDLE_STATUS", "false").lower() == "true"
        self.var_telegram_idle.set(idle_val)

        # Auto reply on Facebook
        auto_reply_val = env_dict.get("ENABLE_AUTO_REPLY", "false").lower() == "true"
        self.var_auto_reply.set(auto_reply_val)
        reply_msg_val = env_dict.get("AUTO_REPLY_MESSAGE", "รับออเดอร์เรียบร้อยแล้วค่ะ ขอบคุณมากนะคะ 🙏")
        self.ent_auto_reply_msg.delete(0, tk.END)
        self.ent_auto_reply_msg.insert(0, reply_msg_val)
        self._update_auto_reply_badge()

    def save_env_settings(self, trigger_reload: bool = True):
        """บันทึกค่ากลับลงไฟล์ .env โดยรักษาคอมเมนต์และโครงสร้างเดิม และส่งสัญญาณให้อัปเดตทันทีหากบอทกำลังรัน"""
        urls_input = self.txt_urls.get("1.0", tk.END).strip()
        url_list = [u.strip().strip('"').strip("'") for u in urls_input.replace("\n", ",").split(",") if u.strip()]
        formatted_urls = ", ".join(url_list)

        interval = self.ent_interval.get().strip() or "180"
        hours = self.ent_hours.get().strip()
        author = self.ent_author.get().strip()
        telegram_idle = "true" if self.var_telegram_idle.get() else "false"

        auto_reply_enabled = "true" if self.var_auto_reply.get() else "false"
        auto_reply_message = self.ent_auto_reply_msg.get().strip() or "รับออเดอร์เรียบร้อยแล้วค่ะ ขอบคุณมากนะคะ 🙏"

        updates = {
            "POST_URL": formatted_urls,
            "CHECK_INTERVAL": interval,
            "OPERATING_HOURS": hours,
            "POST_AUTHOR_NAME": author,
            "SEND_IDLE_STATUS": telegram_idle,
            "ENABLE_AUTO_REPLY": auto_reply_enabled,
            "AUTO_REPLY_MESSAGE": auto_reply_message
        }

        try:
            lines = []
            if ENV_PATH.exists():
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            updated_keys = set()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                matched = False
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _ = stripped.split("=", 1)
                    k = k.strip()
                    if k in updates:
                        new_lines.append(f"{k}={updates[k]}\n")
                        updated_keys.add(k)
                        matched = True
                    elif k == "POST_URLS":
                        new_lines.append(f"POST_URLS={formatted_urls}\n")
                        updated_keys.add("POST_URLS")
                        matched = True

                if not matched:
                    new_lines.append(line)

            for k, v in updates.items():
                if k not in updated_keys and not (k == "POST_URL" and "POST_URLS" in updated_keys):
                    new_lines.append(f"{k}={v}\n")

            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            # หากบอทกำลังทำงานอยู่ และ trigger_reload เป็น True ให้ส่งสัญญาณ IPC ให้บอทสลับไปตรวจโพสต์ใหม่ทันที
            if self.is_running and trigger_reload:
                try:
                    trigger_file = BASE_DIR / "trigger_check.flag"
                    trigger_file.write_text("reload", encoding="utf-8")
                except Exception:
                    pass
                self.lbl_save_status.config(text="⚡ อัปเดตลิงก์แล้ว! บอทกำลังตรวจโพสต์ใหม่", fg="#10b981")
                self.log_message(f"[*] บันทึกการตั้งค่าแล้ว และส่งสัญญาณให้บอทเริ่มตรวจลิงก์ใหม่ทันที (ไม่ต้องเริ่มโปรแกรมใหม่)\n")
            else:
                self.lbl_save_status.config(text="✓ บันทึกสำเร็จ!", fg="#10b981")
                self.log_message(f"[*] บันทึกการตั้งค่าลง .env เรียบร้อยแล้ว (จำนวนโพสต์: {len(url_list)})\n")

            self.root.after(4000, lambda: self.lbl_save_status.config(text=""))

        except Exception as e:
            messagebox.showerror("บันทึกไม่สำเร็จ", f"เกิดข้อผิดพลาด: {e}")
            self.log_message(f"[!] บันทึก .env ล้มเหลว: {e}\n")

    def quick_update_urls(self):
        """บันทึกการตั้งค่าและสั่งให้บอทสลับลิงก์เริ่มตรวจโพสต์ใหม่ทันทีแบบ Realtime โดยไม่ต้องรีสตาร์ท"""
        urls_input = self.txt_urls.get("1.0", tk.END).strip()
        if not urls_input:
            messagebox.showwarning("ยังไม่ได้ระบุลิงก์", "กรุณาระบุลิงก์โพสต์ Facebook ก่อนกดอัปเดตครับ")
            return

        self.save_env_settings(trigger_reload=True)
        if self.is_running:
            self.log_message("\n⚡ [คำสั่งด่วน] ส่งสัญญาณสลับลิงก์โพสต์สำเร็จ! ระบบจะเริ่มตรวจโพสต์ใหม่นี้ทันทีโดยไม่ต้องเริ่มโปรแกรมใหม่\n")
        else:
            self.lbl_save_status.config(text="✓ บันทึกลิงก์แล้ว (พร้อมเริ่มทำงาน)", fg="#10b981")

    # -----------------------------------------------------------------
    # Service Lifecycle Management
    # -----------------------------------------------------------------
    def _get_subprocess_env(self):
        """สร้าง Environment variables ที่บังคับให้ใช้ UTF-8 ป้องกันฟอนต์ไทยเพี้ยน"""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return env

    def start_service(self):
        """เริ่มรันบอทเฝ้าดูคอมเมนต์ (main.py --watch)"""
        if self.is_running:
            return

        # Auto-save current settings first
        self.save_env_settings()

        urls_input = self.txt_urls.get("1.0", tk.END).strip()
        if not urls_input:
            messagebox.showwarning("ยังไม่ได้ระบุลิงก์", "กรุณาระบุลิงก์โพสต์ Facebook ก่อนเริ่มทำงานครับ")
            return

        self.log_message("\n" + "="*55 + "\n")
        self.log_message("🚀 กำลังสั่งเริ่มระบบเฝ้าดูโพสต์ Facebook...\n")

        cmd = [str(VENV_PYTHON), "-u", "main.py", "--watch"]

        try:
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                env=self._get_subprocess_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags
            )

            self.is_running = True
            self._update_ui_state(running=True)

            reader_thread = threading.Thread(target=self._read_process_output, daemon=True)
            reader_thread.start()

        except Exception as e:
            self.log_message(f"[!] ไม่สามารถเริ่มเซอร์วิสได้: {e}\n")
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถเริ่มเซอร์วิสได้: {e}")
            self._update_ui_state(running=False)

    def stop_service(self):
        """หยุดการทำงานของบอทและปิดโพรเซสที่เกี่ยวข้องอย่างปลอดภัย"""
        if not self.is_running and not self.process:
            return

        self.log_message("\n[*] กำลังหยุดการทำงานของระบบ...\n")
        self.status_badge.config(text="🟡 สถานะ: กำลังหยุดทำงาน...", fg="#f59e0b", bg="#334155")
        self.root.update_idletasks()

        if self.process and self.process.poll() is None:
            pid = self.process.pid
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                else:
                    self.process.terminate()
                    self.process.wait(timeout=3)
            except Exception as e:
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.process = None
        self.is_running = False
        self._update_ui_state(running=False)
        self.log_message("[✓] ปิดเซอร์วิสและเบราว์เซอร์เรียบร้อยแล้ว\n")

    def _update_ui_state(self, running: bool):
        self.is_running = running
        if running:
            self.status_badge.config(text="🟢 สถานะ: กำลังทำงาน (Running)", fg="#10b981", bg="#064e3b")
            self.btn_start.config(state=tk.DISABLED, bg="#334155", cursor="arrow")
            self.btn_stop.config(state=tk.NORMAL, bg=self.c_stop, cursor="hand2")
        else:
            self.status_badge.config(text="🔴 สถานะ: หยุดทำงาน (Stopped)", fg="#ef4444", bg="#450a0a")
            self.btn_start.config(state=tk.NORMAL, bg=self.c_start, cursor="hand2")
            self.btn_stop.config(state=tk.DISABLED, bg="#334155", cursor="arrow")

    def _read_process_output(self):
        """อ่าน stdout จาก Subprocess ส่งเข้า Queue"""
        if not self.process:
            return

        try:
            for line in iter(self.process.stdout.readline, ""):
                if line:
                    self.log_queue.put(line)
        except Exception:
            pass
        finally:
            if self.process:
                self.process.stdout.close()
            self.log_queue.put("__PROCESS_EXIT__")

    def _process_log_queue(self):
        """นำข้อความจาก Queue มาแสดงใน Text Box บน UI Thread"""
        while not self.log_queue.empty():
            try:
                item = self.log_queue.get_nowait()
                if item == "__PROCESS_EXIT__":
                    if self.is_running:
                        self.log_message("\n[i] โพรเซสเบื้องหลังสิ้นสุดการทำงานแล้ว\n")
                        self.stop_service()
                else:
                    self.log_message(item)
            except queue.Empty:
                break

        self.root.after(100, self._process_log_queue)

    def log_message(self, text: str):
        """เพิ่มข้อความในช่อง Log และเลื่อนลงล่างสุดอัตโนมัติ"""
        self.txt_log.insert(tk.END, text)
        self.txt_log.see(tk.END)

    def clear_logs(self):
        self.txt_log.delete("1.0", tk.END)

    # -----------------------------------------------------------------
    # Auxiliary Actions (Login / Test Notify / Clear Cache)
    # -----------------------------------------------------------------
    def _telegram_poller_loop(self):
        """วนตรวจสอบคำสั่งสร้างโพสต์เปิดร้านจาก Telegram เบื้องหลัง"""
        import time
        time.sleep(3)
        while getattr(self, "tg_poll_active", True):
            try:
                from telegram_bridge import check_pending_post_command, execute_telegram_post_task
                task = check_pending_post_command()
                if task:
                    close_t = task.get("close_time", "20.00")
                    cmd_type = task.get("command", "publish")
                    self.log_queue.put(f"\n[Telegram Command] 🤖 ได้รับคำสั่งสั่งสร้างโพสต์จาก Telegram ({cmd_type.upper()} ปิด {close_t} น.)...\n")

                    was_running = self.is_running
                    if was_running:
                        self.log_queue.put("[*] กำลังหยุดเซอร์วิสหลักชั่วคราวเพื่อเปิดเบราว์เซอร์สำหรับโพสต์...\n")
                        self.root.after(0, self.stop_service)
                        time.sleep(4)

                    def _progress_cb(msg):
                        self.log_queue.put(f"[*] {msg}\n")

                    res = execute_telegram_post_task(task, progress_cb=_progress_cb)

                    if res.get("success"):
                        new_url = res.get("post_url")
                        if new_url and "posts" in new_url:
                            def _update_ui(p_url=new_url):
                                self.txt_urls.delete("1.0", tk.END)
                                self.txt_urls.insert("1.0", p_url)
                                self.quick_update_urls()
                                self.log_message(f"\n[✓] 📢 โพสต์ใหม่ถูกตั้งเป็นโพสต์เฝ้าดูแล้ว: {p_url}\n")
                                self.root.after(1000, self.start_service)
                            self.root.after(0, _update_ui)
                    else:
                        if was_running:
                            self.root.after(1000, self.start_service)
            except Exception:
                pass
            time.sleep(5)

    def open_facebook_login(self):
        """เปิดหน้าต่างล็อกอิน Facebook ในโหมดโต้ตอบ"""
        if self.is_running:
            messagebox.showinfo("แจ้งเตือน", "กรุณากด [หยุดทำงาน (Stop)] เซอร์วิสก่อนเปิดหน้าต่างล็อกอินครับ")
            return

        self.log_message("\n[*] กำลังเปิดหน้าต่างเบราว์เซอร์เพื่อเข้าสู่ระบบ Facebook...\n")
        cmd_str = f'"{VENV_PYTHON}" main.py --login'
        if sys.platform == "win32":
            subprocess.Popen(f'start "Facebook Login" cmd.exe /c "{cmd_str}"', cwd=str(BASE_DIR), shell=True)
        else:
            subprocess.Popen([str(VENV_PYTHON), "main.py", "--login"], cwd=str(BASE_DIR))

    def _set_test_preset(self, comment: str, name: str = ""):
        """เลือกข้อความตัวอย่างสำหรับทดสอบ"""
        if name:
            self.ent_test_name.delete(0, tk.END)
            self.ent_test_name.insert(0, name)
        self.txt_test_comment.delete("1.0", tk.END)
        self.txt_test_comment.insert("1.0", comment)

    def _clear_test_order_inputs(self):
        """ล้างช่องป้อนข้อความทดสอบ"""
        self.ent_test_name.delete(0, tk.END)
        self.ent_test_name.insert(0, "ทดสอบ ลูกค้า Facebook")
        self.txt_test_comment.delete("1.0", tk.END)

    def send_test_order_action(self):
        """ส่งข้อความออเดอร์ทดสอบไปยัง Telegram ผ่าน Takoab POS API"""
        name = self.ent_test_name.get().strip() or "ทดสอบ ลูกค้า Facebook"
        comment = self.txt_test_comment.get("1.0", tk.END).strip()
        if not comment:
            messagebox.showwarning("คำเตือน", "กรุณาระบุข้อความคอมเมนต์สำหรับทดสอบออเดอร์")
            return

        self.btn_send_test_order.configure(state=tk.DISABLED, text="⏳ กำลังส่ง...")
        self.lbl_test_order_status.configure(text="กำลังส่งเข้า Telegram...", fg="#38bdf8")
        self.log_message(f"\n[*] 🧪 เริ่มส่งออเดอร์ทดสอบเข้า Telegram (ลูกค้า: {name})...\n")

        def _worker():
            try:
                from notifier import send_pos_draft_order
                res = send_pos_draft_order(customer_name=name, comment_text=comment, reason="ทดสอบระบบ Telegram Draft", sync=True)
                if res and res.get("success"):
                    draft_id = res.get("draft_id", "-")
                    msg = f"✓ ส่งสำเร็จ! (Draft ID: {draft_id})"
                    self.log_queue.put(f"[✓] สร้างร่างออเดอร์ใน Telegram สำเร็จ! (Draft ID: {draft_id})\n👉 ตรวจสอบคำถามและการตอบกลับใน Telegram ของร้านได้ทันที\n")
                    self.root.after(0, lambda: self._on_test_order_done(True, msg))
                else:
                    err = res.get("error", "ไม่สามารถส่งไปยัง POS Draft API ได้") if res else "เกิดข้อผิดพลาด"
                    self.log_queue.put(f"[!] ส่งออเดอร์ทดสอบไม่สำเร็จ: {err}\n")
                    self.root.after(0, lambda: self._on_test_order_done(False, f"✕ ล้มเหลว: {err[:25]}"))
            except Exception as e:
                self.log_queue.put(f"[!] เกิดข้อผิดพลาดในการส่ง: {e}\n")
                self.root.after(0, lambda: self._on_test_order_done(False, f"✕ ข้อผิดพลาด: {str(e)[:25]}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_test_order_done(self, success: bool, msg: str):
        self.btn_send_test_order.configure(state=tk.NORMAL, text="🚀 ส่งทดสอบเข้า Telegram")
        self.lbl_test_order_status.configure(
            text=msg,
            fg="#10b981" if success else "#ef4444"
        )
        self.root.after(8000, lambda: self.lbl_test_order_status.configure(text=""))

    def test_notification(self):
        """รันคำสั่งทดสอบระบบแจ้งเตือนและเสียง"""
        self.log_message("\n[*] กำลังรันการทดสอบระบบแจ้งเตือน...\n")
        threading.Thread(target=self._run_quick_cmd, args=(["--test-notify"],), daemon=True).start()

    def clear_cache(self):
        """ล้างประวัติการแจ้งเตือน"""
        if messagebox.askyesno("ยืนยัน", "ต้องการล้างประวัติที่เคยแจ้งเตือนแล้วเพื่อเริ่มตรวจนับใหม่ทั้งหมดหรือไม่?"):
            threading.Thread(target=self._run_quick_cmd, args=(["--clear-cache"],), daemon=True).start()

    def _run_quick_cmd(self, extra_args):
        try:
            cmd = [str(VENV_PYTHON), "-u", "main.py"] + extra_args
            p = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                env=self._get_subprocess_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            out, _ = p.communicate()
            if out:
                self.log_queue.put(out + "\n")
        except Exception as e:
            self.log_queue.put(f"[!] เกิดข้อผิดพลาด: {e}\n")

    def on_close(self):
        """จัดการเมื่อผู้ใช้กดปิดหน้าต่างโปรแกรม"""
        if self.is_running:
            if messagebox.askokcancel("ปิดโปรแกรม", "ระบบกำลังทำงานอยู่ ต้องการหยุดเซอร์วิสและปิดโปรแกรมหรือไม่?"):
                self.stop_service()
                self.root.destroy()
        else:
            self.root.destroy()

# -----------------------------------------------------------------
    # Create Facebook Group Post Dialog
    # -----------------------------------------------------------------
    def open_create_post_dialog(self):
        """เปิดหน้าต่างสร้างและเผยแพร่โพสต์เปิดร้านลงกลุ่ม Facebook"""
        if self.is_running:
            if not messagebox.askyesno(
                "ระบบกำลังทำงานอยู่",
                "ระบบเฝ้าดูคอมเมนต์กำลังทำงานอยู่ (ซึ่งกำลังใช้เบราว์เซอร์ Facebook)\n\n"
                "จำเป็นต้องหยุดเซอร์วิสชั่วคราวเพื่อเปิดหน้าต่างสร้างโพสต์\n"
                "ต้องการหยุดเซอร์วิสชั่วคราวและดำเนินการต่อหรือไม่?"
            ):
                return
            self.stop_service()

        CreatePostDialog(self)


class PostPreviewWindow:
    """หน้าต่างแสดงภาพตัวอย่างโพสต์ Facebook ก่อนส่งจริง"""
    def __init__(self, parent_window, image_path: str):
        self.win = tk.Toplevel(parent_window)
        self.win.title("👁 ภาพตัวอย่างโพสต์ Facebook")
        self.win.geometry("780x620")
        self.win.minsize(680, 500)
        self.win.configure(bg="#0f172a")

        header = tk.Frame(self.win, bg="#0f172a")
        header.pack(fill=tk.X, padx=16, pady=(12, 8))

        lbl = tk.Label(
            header,
            text="👁 ภาพตัวอย่างหน้าต่างโพสต์ Facebook (จำลองการกรอกข้อมูลจริง)",
            font=("Leelawadee UI", 12, "bold"),
            fg="#f8fafc",
            bg="#0f172a"
        )
        lbl.pack(side=tk.LEFT)

        # Scrollable canvas for the image
        container = tk.Frame(self.win, bg="#090d16")
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        try:
            self.raw_photo = tk.PhotoImage(file=image_path)
            # Scale down 2x for comfortable display
            if self.raw_photo.width() > 750:
                self.disp_photo = self.raw_photo.subsample(2, 2)
            else:
                self.disp_photo = self.raw_photo

            img_label = tk.Label(container, image=self.disp_photo, bg="#090d16")
            img_label.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            lbl_err = tk.Label(
                container,
                text=f"ไม่สามารถโหลดภาพตัวอย่างได้: {e}\n(ไฟล์ถูกบันทึกไว้ที่: {image_path})",
                font=("Leelawadee UI", 10),
                fg="#ef4444",
                bg="#090d16",
                pady=40
            )
            lbl_err.pack()

        btn_row = tk.Frame(self.win, bg="#0f172a")
        btn_row.pack(fill=tk.X, padx=16, pady=12)

        btn_close = tk.Button(
            btn_row,
            text="ปิดหน้าต่างตัวอย่าง",
            font=("Leelawadee UI", 10, "bold"),
            fg="white",
            bg="#334155",
            activebackground="#475569",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=6,
            command=self.win.destroy
        )
        btn_close.pack(side=tk.RIGHT)


class CreatePostDialog:
    """หน้าต่างสร้างและเผยแพร่โพสต์เปิดร้านลงกลุ่ม Facebook พร้อมใส่อีโมจิและแนบรูปภาพ"""
    def __init__(self, parent: TakoabMonitorGUI):
        self.parent = parent
        self.root = parent.root

        from fb_poster import (
            get_thai_date_string, get_default_template, save_template,
            format_post_text, get_default_post_images, publish_facebook_group_post,
            update_env_post_url
        )
        from datetime import datetime, timedelta

        self.get_thai_date_string = get_thai_date_string
        self.get_default_template = get_default_template
        self.save_template = save_template
        self.format_post_text = format_post_text
        self.get_default_post_images = get_default_post_images
        self.publish_facebook_group_post = publish_facebook_group_post
        self.update_env_post_url = update_env_post_url
        self.datetime = datetime
        self.timedelta = timedelta

        self.attached_images = self.get_default_post_images()
        self.is_processing = False

        self.win = tk.Toplevel(self.root)
        self.win.title("📢 สร้างและเผยแพร่โพสต์เปิดร้านลงกลุ่ม Facebook")
        self.win.geometry("920x840")
        self.win.minsize(820, 700)
        self.win.configure(bg=self.parent.c_bg)
        self.win.transient(self.root)
        self.win.grab_set()

        # Center on parent window
        try:
            x = self.root.winfo_x() + max(0, (self.root.winfo_width() - 920) // 2)
            y = self.root.winfo_y() + max(0, (self.root.winfo_height() - 840) // 2)
            self.win.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        c_bg = self.parent.c_bg
        c_card = self.parent.c_card
        c_text = self.parent.c_text
        c_muted = self.parent.c_muted
        c_input_bg = self.parent.c_input_bg
        font_main = self.parent.font_family

        main_box = tk.Frame(self.win, bg=c_bg)
        main_box.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Header
        hdr = tk.Frame(main_box, bg=c_bg)
        hdr.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            hdr,
            text="📢 สร้างโพสต์เปิดร้านลงกลุ่ม Facebook",
            font=(font_main, 14, "bold"),
            fg=c_text,
            bg=c_bg
        ).pack(side=tk.LEFT)

        tk.Label(
            hdr,
            text="พิมพ์ข้อความพร้อมอีโมจิครบถ้วน แนบรูปภาพ และอัปเดตลิงก์เฝ้าดูอัตโนมัติ",
            font=(font_main, 10),
            fg=c_muted,
            bg=c_bg
        ).pack(side=tk.LEFT, padx=(12, 0), pady=(3, 0))

        # Top Control Card (Group + Date)
        top_card = tk.LabelFrame(
            main_box,
            text=" ⚙️ ข้อมูลกลุ่มและวันที่ ",
            font=self.parent.font_card_title,
            fg=c_text,
            bg=c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=8
        )
        top_card.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Target Group
        row_grp = tk.Frame(top_card, bg=c_card)
        row_grp.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            row_grp,
            text="👥 กลุ่มเป้าหมาย (ID หรือ URL):",
            font=self.parent.font_label_bold,
            fg=c_text,
            bg=c_card,
            width=24,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.ent_group = tk.Entry(
            row_grp,
            font=self.parent.font_input,
            bg=c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1
        )
        default_grp = self.parent.group_id or "1111870942162462"
        self.ent_group.insert(0, default_grp)
        self.ent_group.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.parent._enable_context_menu_and_shortcuts(self.ent_group)

        # Row 2: Post Date
        row_dt = tk.Frame(top_card, bg=c_card)
        row_dt.pack(fill=tk.X, pady=(2, 0))

        tk.Label(
            row_dt,
            text="📅 วันที่เปิดรับออเดอร์:",
            font=self.parent.font_label_bold,
            fg=c_text,
            bg=c_card,
            width=24,
            anchor="w"
        ).pack(side=tk.LEFT)

        today_thai = self.get_thai_date_string()
        self.ent_date = tk.Entry(
            row_dt,
            font=self.parent.font_input,
            bg=c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            width=18
        )
        self.ent_date.insert(0, today_thai)
        self.ent_date.pack(side=tk.LEFT)
        self.parent._enable_context_menu_and_shortcuts(self.ent_date)

        # Date helper buttons
        btn_today = tk.Button(
            row_dt,
            text="📅 วันนี้",
            font=self.parent.font_btn_sub,
            fg=c_text,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._set_date_today
        )
        btn_today.pack(side=tk.LEFT, padx=(8, 4))

        btn_tmrw = tk.Button(
            row_dt,
            text="📅 พรุ่งนี้",
            font=self.parent.font_btn_sub,
            fg=c_text,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._set_date_tomorrow
        )
        btn_tmrw.pack(side=tk.LEFT, padx=4)

        btn_apply_date = tk.Button(
            row_dt,
            text="↻ อัปเดตในข้อความ",
            font=self.parent.font_btn_sub,
            fg="white",
            bg="#0284c7",
            activebackground="#0369a1",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._apply_datetime_to_text
        )
        btn_apply_date.pack(side=tk.LEFT, padx=4)

        # Row 3: Close Time
        row_time = tk.Frame(top_card, bg=c_card)
        row_time.pack(fill=tk.X, pady=(4, 0))

        tk.Label(
            row_time,
            text="⏰ รับออเดอร์ถึง (เวลา):",
            font=self.parent.font_label_bold,
            fg=c_text,
            bg=c_card,
            width=24,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.ent_close_time = tk.Entry(
            row_time,
            font=self.parent.font_input,
            bg=c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            width=18
        )
        self.ent_close_time.insert(0, "20.00")
        self.ent_close_time.pack(side=tk.LEFT)
        self.parent._enable_context_menu_and_shortcuts(self.ent_close_time)

        for t_val in ["20.00", "20.30", "21.00", "21.30", "19.30"]:
            btn_t = tk.Button(
                row_time,
                text=t_val,
                font=self.parent.font_btn_sub,
                fg=c_text,
                bg=self.parent.c_btn,
                activebackground=self.parent.c_btn_hover,
                relief=tk.FLAT,
                cursor="hand2",
                padx=6,
                pady=1,
                command=lambda val=t_val: self._set_close_time(val)
            )
            btn_t.pack(side=tk.LEFT, padx=3)

        # Emoji Toolbar Card
        emoji_bar = tk.Frame(main_box, bg=c_card, bd=1, relief=tk.SOLID, padx=8, pady=4)
        emoji_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            emoji_bar,
            text="🎨 แทรกอีโมจิ:",
            font=self.parent.font_label_bold,
            fg="#38bdf8",
            bg=c_card
        ).pack(side=tk.LEFT, padx=(0, 6))

        emojis = [
            "🐙", "💸", "👉", "💥", "📌", "🍛", "🍳", "🍗",
            "🍿", "🍟", "🥤", "❌", "🌶", "🧀", "🧅", "🍢",
            "🍯", "🧄", "🏚️", "🛵", "✨"
        ]
        for em in emojis:
            b = tk.Button(
                emoji_bar,
                text=em,
                font=(font_main, 11),
                fg="white",
                bg=c_input_bg,
                activebackground=self.parent.c_btn_hover,
                relief=tk.FLAT,
                cursor="hand2",
                padx=5,
                pady=1,
                command=lambda c=em: self._insert_emoji(c)
            )
            b.pack(side=tk.LEFT, padx=1)

        # Post Content Text Card
        text_card = tk.LabelFrame(
            main_box,
            text=" 📝 ข้อความโพสต์ (แก้ไขรายละเอียด ราคา หรือเมนูได้อิสระ) ",
            font=self.parent.font_card_title,
            fg=c_text,
            bg=c_card,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=8
        )
        text_card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        txt_hdr = tk.Frame(text_card, bg=c_card)
        txt_hdr.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            txt_hdr,
            text="💡 ระบบจะพิมพ์ข้อความพร้อมอีโมจิลงกล่องโพสต์ของ Facebook 100%",
            font=self.parent.font_btn_sub,
            fg=c_muted,
            bg=c_card
        ).pack(side=tk.LEFT)

        btn_save_tmpl = tk.Button(
            txt_hdr,
            text="💾 บันทึกเป็นเทมเพลตต้นแบบ",
            font=self.parent.font_btn_sub,
            fg="white",
            bg=self.parent.c_accent,
            activebackground=self.parent.c_accent_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._save_as_template
        )
        btn_save_tmpl.pack(side=tk.RIGHT)

        btn_reset_tmpl = tk.Button(
            txt_hdr,
            text="↻ โหลดเทมเพลตต้นแบบ",
            font=self.parent.font_btn_sub,
            fg=c_muted,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self._reload_template
        )
        btn_reset_tmpl.pack(side=tk.RIGHT, padx=(0, 6))

        self.txt_content = scrolledtext.ScrolledText(
            text_card,
            wrap=tk.WORD,
            font=self.parent.font_input,
            bg=c_input_bg,
            fg="#f8fafc",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            spacing1=3,
            spacing2=3,
            spacing3=3,
            undo=True
        )
        self.txt_content.pack(fill=tk.BOTH, expand=True)
        self.parent._enable_context_menu_and_shortcuts(self.txt_content)

        # Load initial content
        initial_text = self.format_post_text(self.get_default_template(), custom_date_str=today_thai, close_time="20.00")
        self.txt_content.insert("1.0", initial_text)

        # Image Attachments Card
        img_card = tk.Frame(main_box, bg=c_card, bd=1, relief=tk.SOLID, padx=10, pady=6)
        img_card.pack(fill=tk.X, pady=(0, 6))

        self.lbl_img_info = tk.Label(
            img_card,
            text="",
            font=self.parent.font_label_bold,
            fg=c_text,
            bg=c_card,
            anchor="w"
        )
        self.lbl_img_info.pack(side=tk.LEFT)
        self._update_images_label()

        btn_clear_imgs = tk.Button(
            img_card,
            text="🗑 ล้างรูป",
            font=self.parent.font_btn_sub,
            fg=c_muted,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._clear_images
        )
        btn_clear_imgs.pack(side=tk.RIGHT)

        btn_open_folder = tk.Button(
            img_card,
            text="📂 โฟลเดอร์รูป",
            font=self.parent.font_btn_sub,
            fg=c_text,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._open_assets_folder
        )
        btn_open_folder.pack(side=tk.RIGHT, padx=(0, 6))

        btn_add_img = tk.Button(
            img_card,
            text="➕ เพิ่มรูป...",
            font=self.parent.font_btn_sub,
            fg="white",
            bg="#0284c7",
            activebackground="#0369a1",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._pick_more_images
        )
        btn_add_img.pack(side=tk.RIGHT, padx=(0, 6))

        # Checkboxes row
        opts_row = tk.Frame(main_box, bg=c_bg)
        opts_row.pack(fill=tk.X, pady=(2, 6))

        self.var_update_urls = tk.BooleanVar(value=True)
        chk_url = tk.Checkbutton(
            opts_row,
            text="☑ อัปเดตลิงก์ในโปรแกรมและ .env ทันทีหลังโพสต์เสร็จ",
            variable=self.var_update_urls,
            font=self.parent.font_label,
            fg=c_text,
            bg=c_bg,
            selectcolor=c_input_bg,
            activebackground=c_bg,
            activeforeground=c_text
        )
        chk_url.pack(side=tk.LEFT)

        self.var_auto_watch = tk.BooleanVar(value=True)
        chk_watch = tk.Checkbutton(
            opts_row,
            text="☑ เริ่มเฝ้าดูคอมเมนต์ทันทีหลังโพสต์เสร็จ (Auto Watch)",
            variable=self.var_auto_watch,
            font=self.parent.font_label,
            fg="#38bdf8",
            bg=c_bg,
            selectcolor=c_input_bg,
            activebackground=c_bg,
            activeforeground="#38bdf8"
        )
        chk_watch.pack(side=tk.LEFT, padx=(16, 0))

        # Status row
        self.lbl_status = tk.Label(
            main_box,
            text="⚪ สถานะ: พร้อมทำงาน (กดปุ่มด้านล่างเพื่อเริ่ม)",
            font=self.parent.font_label,
            fg="#94a3b8",
            bg=c_bg,
            anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, pady=(0, 6))

        # Bottom Buttons Row
        action_row = tk.Frame(main_box, bg=c_bg)
        action_row.pack(fill=tk.X)

        self.btn_publish = tk.Button(
            action_row,
            text="🚀 เผยแพร่โพสต์ลง Facebook ทันที",
            font=self.parent.font_btn_main,
            fg="white",
            bg=self.parent.c_start,
            activebackground=self.parent.c_start_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=18,
            pady=8,
            command=self.start_publish
        )
        self.btn_publish.pack(side=tk.LEFT)

        self.btn_preview = tk.Button(
            action_row,
            text="👁 ดูภาพตัวอย่างก่อนโพสต์ (Preview)",
            font=self.parent.font_btn_main,
            fg="white",
            bg=self.parent.c_accent,
            activebackground=self.parent.c_accent_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self.start_preview
        )
        self.btn_preview.pack(side=tk.LEFT, padx=(10, 0))

        btn_close = tk.Button(
            action_row,
            text="✕ ปิดหน้าต่าง",
            font=self.parent.font_btn_sub,
            fg=c_muted,
            bg=self.parent.c_btn,
            activebackground=self.parent.c_btn_hover,
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self.win.destroy
        )
        btn_close.pack(side=tk.RIGHT)

    def _insert_emoji(self, char: str):
        try:
            self.txt_content.insert(tk.INSERT, char)
            self.txt_content.focus_set()
        except Exception:
            pass

    def _set_date_today(self):
        dt_str = self.get_thai_date_string(self.datetime.now())
        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, dt_str)
        self._apply_datetime_to_text()

    def _set_date_tomorrow(self):
        tmrw = self.datetime.now() + self.timedelta(days=1)
        dt_str = self.get_thai_date_string(tmrw)
        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, dt_str)
        self._apply_datetime_to_text()

    def _set_close_time(self, val: str):
        self.ent_close_time.delete(0, tk.END)
        self.ent_close_time.insert(0, val)
        self._apply_datetime_to_text()

    def _apply_datetime_to_text(self):
        dt_str = self.ent_date.get().strip() or self.get_thai_date_string()
        close_t = self.ent_close_time.get().strip() or "20.00"
        current = self.txt_content.get("1.0", tk.END).strip()
        updated = self.format_post_text(current, custom_date_str=dt_str, close_time=close_t)
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", updated)
        self.lbl_status.config(text=f"✓ อัปเดตวันที่ '{dt_str}' และเวลาปิดรับออเดอร์ถึง '{close_t}' เรียบร้อย", fg="#10b981")

    def _save_as_template(self):
        content = self.txt_content.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("คำเตือน", "ไม่มีข้อความสำหรับบันทึก")
            return
        dt_str = self.ent_date.get().strip()
        close_t = self.ent_close_time.get().strip() or "20.00"
        tmpl_content = content
        if dt_str and dt_str in tmpl_content:
            tmpl_content = tmpl_content.replace(dt_str, "{date}")
        if close_t and f"รับออเดอร์ถึง {close_t}" in tmpl_content:
            tmpl_content = tmpl_content.replace(f"รับออเดอร์ถึง {close_t}", "รับออเดอร์ถึง {close_time}")
        self.save_template(tmpl_content)
        messagebox.showinfo("บันทึกสำเร็จ", "บันทึกข้อความปัจจุบันเป็นเทมเพลตต้นแบบเรียบร้อยแล้ว!")

    def _reload_template(self):
        dt_str = self.ent_date.get().strip() or self.get_thai_date_string()
        close_t = self.ent_close_time.get().strip() or "20.00"
        tmpl = self.get_default_template()
        text = self.format_post_text(tmpl, custom_date_str=dt_str, close_time=close_t)
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", text)
        self.lbl_status.config(text="✓ รีเซ็ตข้อความจากเทมเพลตต้นแบบเรียบร้อย", fg="#10b981")

    def _update_images_label(self):
        count = len(self.attached_images)
        if count == 0:
            self.lbl_img_info.config(text="🖼️ รูปภาพแนบ: ยังไม่มีการแนบรูปภาพ", fg="#ef4444")
        else:
            names = [os.path.basename(p) for p in self.attached_images[:3]]
            more = f" และอีก {count - 3} รูป" if count > 3 else ""
            self.lbl_img_info.config(text=f"🖼️ แนบรูปภาพ {count} รูป ({', '.join(names)}{more})", fg="#10b981")

    def _pick_more_images(self):
        files = filedialog.askopenfilenames(
            title="เลือกรูปภาพสำหรับแนบโพสต์ Facebook",
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png;*.webp;*.bmp")]
        )
        if files:
            for f in files:
                if f not in self.attached_images:
                    self.attached_images.append(f)
            self._update_images_label()

    def _open_assets_folder(self):
        from fb_poster import ASSETS_DIR
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(ASSETS_DIR))
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(ASSETS_DIR)])

    def _clear_images(self):
        self.attached_images = []
        self._update_images_label()

    def _set_ui_busy(self, busy: bool):
        self.is_processing = busy
        if busy:
            self.btn_publish.config(state=tk.DISABLED, bg="#334155", cursor="arrow")
            self.btn_preview.config(state=tk.DISABLED, bg="#334155", cursor="arrow")
        else:
            self.btn_publish.config(state=tk.NORMAL, bg=self.parent.c_start, cursor="hand2")
            self.btn_preview.config(state=tk.NORMAL, bg=self.parent.c_accent, cursor="hand2")

    def _update_progress(self, msg: str):
        self.root.after(0, lambda: self.lbl_status.config(text=f"⏳ {msg}", fg="#38bdf8"))

    def start_preview(self):
        """ดูตัวอย่างโพสต์ Facebook"""
        if self.is_processing:
            return

        grp = self.ent_group.get().strip() or "1111870942162462"
        content = self.txt_content.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("คำเตือน", "กรุณาระบุข้อความสำหรับโพสต์")
            return

        self._set_ui_busy(True)
        self.lbl_status.config(text="⏳ กำลังเปิดเบราว์เซอร์เพื่อสร้างภาพตัวอย่าง...", fg="#38bdf8")

        def _worker():
            try:
                res = self.publish_facebook_group_post(
                    group_id_or_url=grp,
                    content=content,
                    image_paths=self.attached_images,
                    headless=True,
                    preview_only=True,
                    progress_cb=self._update_progress
                )
                self.root.after(0, lambda: self._on_preview_done(res))
            except Exception as e:
                self.root.after(0, lambda: self._on_preview_done({"success": False, "error": str(e)}))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_preview_done(self, res: dict):
        self._set_ui_busy(False)
        if res.get("success"):
            img_path = res.get("preview_image")
            self.lbl_status.config(text="✓ สร้างภาพตัวอย่างสำเร็จเรียบร้อย!", fg="#10b981")
            PostPreviewWindow(self.win, img_path)
        else:
            err = res.get("error", "เกิดข้อผิดพลาด")
            self.lbl_status.config(text=f"✕ เกิดข้อผิดพลาด: {err}", fg="#ef4444")
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถสร้างภาพตัวอย่างได้: {err}")

    def start_publish(self):
        """เผยแพร่โพสต์ลงในกลุ่ม Facebook ทันที"""
        if self.is_processing:
            return

        grp = self.ent_group.get().strip() or "1111870942162462"
        content = self.txt_content.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("คำเตือน", "กรุณาระบุข้อความสำหรับโพสต์")
            return

        if not messagebox.askyesno(
            "ยืนยันการโพสต์",
            f"ระบบจะเปิด Facebook และเผยแพร่โพสต์เปิดร้านนี้ลงในกลุ่ม {grp} โดยอัตโนมัติ\n\n"
            f"จำนวนรูปภาพที่จะแนบ: {len(self.attached_images)} รูป\n\n"
            "ต้องการยืนยันการเผยแพร่โพสต์ทันทีหรือไม่?"
        ):
            return

        self._set_ui_busy(True)
        self.lbl_status.config(text="⏳ กำลังเชื่อมต่อ Facebook เพื่อโพสต์...", fg="#38bdf8")

        def _worker():
            try:
                res = self.publish_facebook_group_post(
                    group_id_or_url=grp,
                    content=content,
                    image_paths=self.attached_images,
                    headless=True,
                    preview_only=False,
                    progress_cb=self._update_progress
                )
                self.root.after(0, lambda: self._on_publish_done(res))
            except Exception as e:
                self.root.after(0, lambda: self._on_publish_done({"success": False, "error": str(e)}))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_publish_done(self, res: dict):
        self._set_ui_busy(False)
        if res.get("success"):
            new_url = res.get("post_url")
            self.lbl_status.config(text=f"✓ เผยแพร่โพสต์สำเร็จ! ({new_url})", fg="#10b981")

            # 1. Update URLs in main GUI and .env
            if self.var_update_urls.get() and new_url and "posts" in new_url:
                self.parent.txt_urls.delete("1.0", tk.END)
                self.parent.txt_urls.insert("1.0", new_url)
                self.parent.quick_update_urls()
                self.parent.log_message(f"\n[✓] 📢 โพสต์ใหม่ถูกตั้งเป็นโพสต์เฝ้าดูแล้ว: {new_url}\n")

            # 2. Auto-start watch
            if self.var_auto_watch.get():
                self.parent.root.after(500, self.parent.start_service)

            messagebox.showinfo(
                "เผยแพร่โพสต์สำเร็จ!",
                f"🎉 โพสต์เปิดร้านลงกลุ่ม Facebook สำเร็จเรียบร้อย!\n\n"
                f"ลิงก์โพสต์:\n{new_url}\n\n"
                + ("ระบบกำลังเริ่มเฝ้าดูคอมเมนต์ออเดอร์ทันที" if self.var_auto_watch.get() else "")
            )
            self.win.destroy()
        else:
            err = res.get("error", "เกิดข้อผิดพลาดในการโพสต์")
            self.lbl_status.config(text=f"✕ เกิดข้อผิดพลาด: {err}", fg="#ef4444")
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถโพสต์ลงกลุ่ม Facebook ได้:\n{err}")

def main():
    root = tk.Tk()
    app = TakoabMonitorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
