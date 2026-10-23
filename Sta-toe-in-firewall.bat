@echo off
rem === Sta-toe-in-firewall.bat ===
rem Laat het KITT-hoofdkwartier door de Windows Firewall, zodat je telefoon
rem op het thuisnetwerk verbinding kan maken.
rem  TCP 8000 = de vraag/antwoord-server,  UDP 8001 = automatisch zoeken.
rem RECHTSKLIK dit bestand -> "Als administrator uitvoeren".

net session >nul 2>&1
if errorlevel 1 (
  echo Dit bestand moet als ADMINISTRATOR draaien.
  echo Rechtsklik erop en kies "Als administrator uitvoeren".
  pause
  exit /b 1
)

echo Firewall-regels toevoegen...
netsh advfirewall firewall delete rule name="DraveKITT server (TCP 8000)" >nul 2>&1
netsh advfirewall firewall delete rule name="DraveKITT zoeken (UDP 8001)" >nul 2>&1
netsh advfirewall firewall add rule name="DraveKITT server (TCP 8000)" dir=in action=allow protocol=TCP localport=8000 profile=any
netsh advfirewall firewall add rule name="DraveKITT zoeken (UDP 8001)" dir=in action=allow protocol=UDP localport=8001 profile=any

echo.
echo Klaar! Start de KITT-server (opnieuw) en probeer op je telefoon
echo "Zoek hoofdkwartier" nog eens.
echo.
pause
