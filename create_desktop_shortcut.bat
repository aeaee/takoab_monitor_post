@echo off
chcp 65001 >nul
REM Script สำหรับสร้าง Shortcut ของ Takoab Post Monitor ไว้ที่ Desktop
cd /d "%~dp0"

echo [*] กำลังสร้าง Desktop Shortcut...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$repo = (Get-Item .).FullName; " ^
    "$pyw = Join-Path $repo '.venv\Scripts\pythonw.exe'; " ^
    "$py = Join-Path $repo '.venv\Scripts\python.exe'; " ^
    "$s = $ws.CreateShortcut((Join-Path $desktop 'Takoab Post Monitor.lnk')); " ^
    "$s.TargetPath = $pyw; " ^
    "$s.Arguments = 'gui.py'; " ^
    "$s.WorkingDirectory = $repo; " ^
    "$s.Description = 'Takoab Facebook Post Monitor'; " ^
    "$s.IconLocation = "$py,0"; " ^
    "$s.Save()"

if %ERRORLEVEL% EQU 0 (
    echo [✓] สร้าง Shortcut ไว้บน Desktop เรียบร้อยแล้ว! (ชื่อ: Takoab Post Monitor)
) else (
    echo [!] เกิดข้อผิดพลาดในการสร้าง Shortcut
)

pause
