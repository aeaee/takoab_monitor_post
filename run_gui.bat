@echo off
REM Launcher สำหรับเปิด Takoab Monitor Desktop App
cd /d "%~dp0"

set PYTHON_EXE=.venv\Scripts\pythonw.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=.venv\Scripts\python.exe
)
if not exist "%PYTHON_EXE%" (
    where pythonw >nul 2>nul && (set PYTHON_EXE=pythonw) || (set PYTHON_EXE=python)
)

start "" "%PYTHON_EXE%" gui.py %*
