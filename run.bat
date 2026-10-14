@echo off
REM Script สำหรับรัน Facebook Group Monitor บน Windows

cd /d "%~dp0"

REM ตรวจหาคำสั่ง python หรือ py บนเครื่อง
set PYTHON_CMD=python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [!] ไม่พบคำสั่ง Python ในระบบ กรุณาติดตั้ง Python จาก python.org และติ๊ก 'Add python.exe to PATH'
        pause
        exit /b 1
    )
)

REM ตรวจสอบว่ามี .venv ที่สมบูรณ์หรือไม่
if not exist ".venv\Scripts\python.exe" (
    echo [!] กำลังสร้างสภาพแวดล้อมเสมือน .venv...
    if exist ".venv" rmdir /s /q ".venv"
    %PYTHON_CMD% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [!] สร้าง .venv ไม่สำเร็จ กำลังติดตั้งลง Python ของเครื่องโดยตรง...
        %PYTHON_CMD% -m pip install -r requirements.txt
        %PYTHON_CMD% -m playwright install chromium
        %PYTHON_CMD% main.py %*
        exit /b 0
    )
    echo [*] กำลังติดตั้งโมดูลที่จำเป็น (playwright, python-dotenv, requests)...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m playwright install chromium
)

.venv\Scripts\python.exe main.py %*
