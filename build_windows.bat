@echo off
REM Construit OpenVidDL.exe et l'installateur sur votre propre PC Windows.
REM Prerequis : Python 3.10+  (et Inno Setup 6 pour l'installateur : https://jrsoftware.org/isdl.php)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( py -3 -m venv .venv || python -m venv .venv )
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller -q || ( echo Echec de l'installation & pause & exit /b 1 )
".venv\Scripts\python.exe" build.py || ( echo Echec de la construction & pause & exit /b 1 )
echo.
echo Termine ! Regardez dans le dossier "dist".
explorer dist
pause
