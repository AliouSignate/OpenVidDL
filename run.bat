@echo off
REM Lance OpenVidDL (et met a jour le moteur yt-dlp en silence)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call install.bat
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" -m pip install -q --upgrade "yt-dlp[default]" >nul 2>nul
".venv\Scripts\python.exe" app.py %*
pause
