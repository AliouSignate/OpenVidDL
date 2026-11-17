@echo off
REM Installation d'OpenVidDL pour Windows
setlocal
cd /d "%~dp0"
echo === Installation d'OpenVidDL ===

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto :nopython

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto :oldpython

if not exist ".venv\Scripts\python.exe" (
  echo - Creation de l'environnement isole...
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

echo - Installation des dependances...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 goto :fail

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo - Telechargement de FFmpeg ^(une seule fois^)...
  ".venv\Scripts\python.exe" -c "import static_ffmpeg; static_ffmpeg.add_paths()"
)

echo.
echo Installation terminee. Double-cliquez sur run.bat pour lancer OpenVidDL.
pause
exit /b 0

:nopython
echo [ERREUR] Python 3.10+ est requis.
echo Installez-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH"
echo ou tapez dans un terminal :  winget install Python.Python.3.12
pause
exit /b 1

:oldpython
echo [ERREUR] Python 3.10 minimum est requis. Installez une version plus recente.
pause
exit /b 1

:fail
echo [ERREUR] L'installation a echoue. Verifiez votre connexion internet puis relancez.
pause
exit /b 1
