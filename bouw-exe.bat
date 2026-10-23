@echo off
rem === bouw-exe.bat - bouwt het KITT-hoofdkwartier als systeemvak-EXE ===
rem Resultaat: dist\DraveKITT-Server\DraveKITT-Server.exe
rem Het taalmodel wordt NIET meegebakken; dat hergebruikt hij uit ..\DraveKITT.
setlocal
cd /d "%~dp0"

set PY=
for %%V in (3.13 3.12 3.11) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY ( echo Geen Python gevonden. & pause & exit /b 1 )

if not exist ".venv" ( %PY% -m venv .venv )
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
rem llama-cpp als AVX2-wheel (zelfde als DraveKITT), + de rest van de motor
python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
if errorlevel 1 python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/basic llama-cpp-python
python -m pip install huggingface_hub ddgs certifi pystray pillow
rem neuvoice = de KITT-stem die de server inspreekt voor de telefoon
python -m pip install neuvoice onnxruntime numpy
python -m pip install pyinstaller

echo.
echo === Bouwen met PyInstaller... ===
pyinstaller --noconfirm dravekitt_server.spec

echo.
echo Klaar! Start:  dist\DraveKITT-Server\DraveKITT-Server.exe
echo Hij verschijnt rechtsonder in het systeemvak (bij de klok). Rechtsklik voor
echo het adres en Afsluiten. Houd de map DraveKITT ernaast (voor het model).
echo.
pause
endlocal
