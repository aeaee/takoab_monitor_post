@echo off
REM Script สำหรับรัน Facebook Group Monitor บน Windows

cd /d "%~dp0"

IF NOT EXIST ".venv" (
    echo [!] ไม่พบ .venv กำลังสร้างสภาพแวดล้อมเสมือน...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
    playwright install chromium
) ELSE (
    call .venv\Scripts\activate
)

python main.py %*
