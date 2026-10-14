#!/bin/bash
# Script สำหรับรัน Facebook Group Monitor ได้อย่างสะดวก

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# เปิดใช้งาน Virtual Environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "[!] ไม่พบ .venv กำลังสร้างสภาพแวดล้อม..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
fi

python3 main.py "$@"
