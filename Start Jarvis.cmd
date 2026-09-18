@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pyw >nul 2>nul
if errorlevel 1 (
    echo Python with Tkinter is required. Install Python 3.12 or later from python.org.
    echo Then run: python app.py
    pause
    exit /b 1
)
py -3 -c "import customtkinter" >nul 2>nul
if errorlevel 1 (
    echo กำลังติดตั้ง customtkinter ครั้งแรก...
    py -3 -m pip install --user customtkinter==5.2.2
    if errorlevel 1 (
        echo ติดตั้ง customtkinter ไม่สำเร็จ ลองรัน: py -m pip install customtkinter==5.2.2
        pause
        exit /b 1
    )
)
start "" pyw -3 "%~dp0app.py"
