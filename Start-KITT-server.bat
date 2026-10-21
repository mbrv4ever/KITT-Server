@echo off
rem === Start-KITT-server.bat - jouw persoonlijke KITT-hoofdkwartier ===
rem Staat los van de DraveKITT-app (die je deelt). Gebruikt wel de omgeving
rem (.venv) en het model van de DraveKITT-map ernaast.
setlocal
cd /d "%~dp0"

set "APP=..\DraveKITT"
if not exist "%APP%\.venv\Scripts\python.exe" (
  echo Kan de DraveKITT-omgeving niet vinden op: %APP%
  echo.
  echo Zorg dat de map KITT-Server NAAST de map DraveKITT staat, en dat je
  echo DraveKITT al een keer hebt gestart met Start-DraveKITT.bat
  echo (zodat de .venv en het model bestaan^).
  pause
  exit /b 1
)

echo Het KITT-hoofdkwartier start... laat dit venster open staan.
echo (Het adres dat je op je telefoon invult verschijnt zo hieronder.)
echo.
"%APP%\.venv\Scripts\python.exe" kitt_server.py

pause
endlocal
