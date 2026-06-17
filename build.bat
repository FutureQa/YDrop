@echo off
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run the Developer Setup steps in README.md first to create the 'venv' folder.
    pause
    exit /b 1
)
call venv\Scripts\activate
pip install pyinstaller
pyinstaller --onefile --windowed ^
  --name YDrop ^
  --icon=assets/icon.ico ^
  --collect-all yt_dlp ^
  --collect-all customtkinter ^
  --noconfirm ^
  --clean ^
  main.py
echo Build complete. Find YDrop.exe in dist/
pause
