KITT-Server - jouw persoonlijke "hoofdkwartier" voor DraveKITT Mobile
====================================================================

Wat is dit?
-----------
Een klein servertje dat op JOUW pc draait en het zware werk doet voor de mobiele
DraveKITT-app: het grote taalmodel, online zoeken en het weer. Je telefoon stuurt
een vraag, de pc rekent, en stuurt het antwoord terug.

Deze map staat BEWUST los van de DraveKITT-app, want de app deel je met anderen en
de server is alleen voor jou. De server gebruikt wel de code, de omgeving (.venv)
en het model van je bestaande DraveKITT-installatie ernaast.

Belangrijk: zet deze map (KITT-Server) NAAST de map DraveKITT:
   ...\Claude_projects\DraveKITT\
   ...\Claude_projects\KITT-Server\

Twee manieren om te draaien
---------------------------
A) Systeemvak-EXE (aanbevolen, geen venster):
   - Eenmalig bouwen: dubbelklik 'bouw-exe.bat' -> dist\DraveKITT-Server\DraveKITT-Server.exe
   - Start die EXE: er verschijnt een drakenicoon RECHTSONDER in het systeemvak
     (bij de klok). Rechtsklik -> 'Adres kopieren' of 'Afsluiten'.
   - Het model wordt NIET in de EXE meegebakken; hij gebruikt dat uit ..\DraveKITT.
B) Console (snel testen): dubbelklik 'Start-KITT-server.bat'.

Gebruik
-------
1. Start je DraveKITT-app minstens 1 keer (Start-DraveKITT.bat) zodat de omgeving
   (.venv) en een taalmodel bestaan.
2. Dubbelklik hier op 'Start-KITT-server.bat'. Laat dat venster open staan.
3. Het venster toont een adres, bv. http://192.168.1.50:8000.
4. Open DraveKITT op je telefoon -> 'Instellen' -> vul dat adres in -> Opslaan.
   (Telefoon en pc op hetzelfde wifi.)

Staat DraveKITT ergens anders? Stel dan de omgevingsvariabele DRAVEKITT_DIR in op
het pad van die map.

Later kunnen we 'van buitenshuis bereikbaar' toevoegen (veilig via Tailscale).
