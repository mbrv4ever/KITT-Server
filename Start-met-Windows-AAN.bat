@echo off
rem === Start-met-Windows-AAN.bat ===
rem Zet de KITT-server (tray-EXE) in de opstartmap, zodat hij automatisch
rem meestart met Windows. Gewoon DUBBELKLIKKEN (geen administrator nodig).
setlocal
set "EXE=%~dp0dist\DraveKITT-Server\DraveKITT-Server.exe"

if not exist "%EXE%" (
  echo Kon de EXE niet vinden:
  echo   %EXE%
  echo Bouw eerst met bouw-exe.bat.
  pause
  exit /b 1
)

powershell -NoProfile -Command ^
 "$lnk=[IO.Path]::Combine([Environment]::GetFolderPath('Startup'),'DraveKITT-Server.lnk');" ^
 "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
 "$s.TargetPath='%EXE%'; $s.WorkingDirectory=(Split-Path '%EXE%'); $s.Save();" ^
 "Write-Host ('Snelkoppeling gezet: ' + $lnk)"

echo.
echo Klaar! KITT start nu automatisch mee met Windows.
echo (Ongedaan maken? Verwijder DraveKITT-Server.lnk uit de map die je opent
echo  via Start - typ:  shell:startup )
echo.
pause
endlocal
