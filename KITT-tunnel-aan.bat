@echo off
rem === KITT-tunnel-aan.bat ===
rem Zet de KITT-server (poort 8000) als BEVEILIGD https-adres op je eigen
rem Tailscale-netwerk. Pas gebruiken NADAT Tailscale op pc + telefoon staat
rem en je in de Tailscale-beheerpagina "HTTPS" hebt aangezet (stap 2).
rem RECHTSKLIK dit bestand -> "Als administrator uitvoeren".

net session >nul 2>&1
if errorlevel 1 (
  echo Er verschijnt zo een Ja/Nee-venster - klik op JA.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "TS=tailscale"
where tailscale >nul 2>&1 || set "TS=%ProgramFiles%\Tailscale\tailscale.exe"

echo KITT als beveiligd https-adres aanzetten...
"%TS%" serve --bg 8000
echo.
echo === Je beveiligde KITT-adres ===
"%TS%" serve status
echo.
echo Open het https-adres hierboven op je TELEFOON (met Tailscale aan)
echo en kies in het browsermenu "App installeren" / "Toevoegen aan startscherm".
echo.
pause
