import sys
import os
import re
import queue
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

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
        self.root.geometry("1140x740")
        self.root.minsize(980, 640)
        self.root.configure(bg="#0f172a")

        # Select the best native Thai font for Windows
        self._setup_thai_fonts()

        # Process management
        self.process = None
        self.log_queue = queue.Queue()
        self.is_running = False

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
            pady=12
        )
        control_card.pack(fill=tk.X, pady=(0, 12))

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

        # 2. Configuration Settings Card
        settings_card = tk.LabelFrame(
            left_panel,
            text=" ตั้งค่าระบบ (.env) ",
            font=self.font_card_title,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=12
        )
        settings_card.pack(fill=tk.BOTH, expand=True)

        # Post URLs
        lbl_urls = tk.Label(
            settings_card,
            text="📌 ลิงก์โพสต์ Facebook ที่ต้องการเฝ้าดู (1 บรรทัดต่อ 1 โพสต์):",
            font=self.font_label_bold,
            fg=self.c_text,
            bg=self.c_card,
            anchor="w"
        )
        lbl_urls.pack(fill=tk.X, pady=(0, 4))

        self.txt_urls = scrolledtext.ScrolledText(
            settings_card,
            height=6,
            font=self.font_input,
            bg=self.c_input_bg,
            fg="#e2e8f0",
            insertbackground="white",
            relief=tk.FLAT,
            bd=1,
            spacing1=3,
            spacing2=3,
            spacing3=3
        )
        self.txt_urls.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

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
        self.chk_telegram_idle.pack(fill=tk.X, pady=(6, 10))

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

        self.log_message("[*] Takoab Monitor พร้อมทำงาน กรุณาตรวจสอบลิงก์แล้วกด [เริ่มทำงาน]\n")

    # -----------------------------------------------------------------
    # Configuration Load / Save (.env)
    # -----------------------------------------------------------------
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

        # URLs
        raw_urls = env_dict.get("POST_URLS", "") or env_dict.get("POST_URL", "")
        clean_urls = [u.strip() for u in raw_urls.replace("\n", ",").split(",") if u.strip()]
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

    def save_env_settings(self):
        """บันทึกค่ากลับลงไฟล์ .env โดยรักษาคอมเมนต์และโครงสร้างเดิม"""
        urls_input = self.txt_urls.get("1.0", tk.END).strip()
        url_list = [u.strip() for u in urls_input.replace("\n", ",").split(",") if u.strip()]
        formatted_urls = ", ".join(url_list)

        interval = self.ent_interval.get().strip() or "180"
        hours = self.ent_hours.get().strip()
        author = self.ent_author.get().strip()
        telegram_idle = "true" if self.var_telegram_idle.get() else "false"

        updates = {
            "POST_URL": formatted_urls,
            "CHECK_INTERVAL": interval,
            "OPERATING_HOURS": hours,
            "POST_AUTHOR_NAME": author,
            "SEND_IDLE_STATUS": telegram_idle
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

            self.lbl_save_status.config(text="✓ บันทึกสำเร็จ!", fg="#10b981")
            self.root.after(3000, lambda: self.lbl_save_status.config(text=""))
            self.log_message(f"[*] บันทึกการตั้งค่าลง .env เรียบร้อยแล้ว (จำนวนโพสต์: {len(url_list)})\n")

        except Exception as e:
            messagebox.showerror("บันทึกไม่สำเร็จ", f"เกิดข้อผิดพลาด: {e}")
            self.log_message(f"[!] บันทึก .env ล้มเหลว: {e}\n")

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

def main():
    root = tk.Tk()
    app = TakoabMonitorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
