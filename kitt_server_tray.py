# -*- coding: utf-8 -*-
"""kitt_server_tray.py - KITT-hoofdkwartier als SYSTEEMVAK-app.

Start het servertje op de achtergrond en zet een drakenicoon rechtsonder in het
systeemvak (bij de klok). Rechtsklik voor het menu: het adres tonen/kopieren en
afsluiten. Geen zwart venster.

Bouwen naar EXE: bouw-exe.bat -> dist\\DraveKITT-Server\\DraveKITT-Server.exe
"""
from __future__ import annotations

import os
import sys
import threading
import time

import kitt_server as ks

try:
    import pystray
    from PIL import Image
except Exception:
    pystray = None
    Image = None


STATE = {"addr": "", "status": "Opstarten..."}


def _resource(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, rel), os.path.join(base, "..", rel)):
        if os.path.exists(cand):
            return cand
    return os.path.join(base, rel)


def _icon_image():
    # gebruik het KITT-icoon; lukt dat niet, dan een simpel rood vierkant
    for name in ("icon-192.png", "icon-512.png", "assets/app_icon.png",
                 "assets/logo.png", "assets/logo_t.png", "logo.png"):
        p = _resource(name)
        if os.path.exists(p):
            try:
                return Image.open(p)
            except Exception:
                pass
    img = Image.new("RGBA", (64, 64), (199, 41, 31, 255))
    return img


def _copy(text):
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
    except Exception:
        pass


def _worker(icon):
    # model laden + server starten (op de achtergrond)
    def status(s):
        STATE["status"] = s
        try:
            icon.update_menu()
        except Exception:
            pass
    ks.build(status)

    def ready(ip, port):
        STATE["addr"] = "http://%s:%d" % (ip, port)
        STATE["status"] = "Draait"
        try:
            icon.title = "DraveKITT hoofdkwartier - " + STATE["addr"]
            icon.update_menu()
        except Exception:
            pass
    ks.run_server(ready)


def main():
    try:  # Dravenlock: stille update-check (uit te zetten in de melding)
        import drave_update
        drave_update.start(None, 'KITT-Server', '1.0.4')
    except Exception:
        pass
    if pystray is None or Image is None:
        # geen systeemvak mogelijk -> val terug op de console-versie
        ks.main()
        return

    def _open_browser(i, it):
        import webbrowser
        webbrowser.open("http://localhost:8000")

    def menu():
        return pystray.Menu(
            pystray.MenuItem(lambda i: ("Adres: " + STATE["addr"]) if STATE["addr"]
                             else ("Status: " + STATE["status"]), None, enabled=False),
            pystray.MenuItem("Open KITT (deze pc)", _open_browser,
                             enabled=lambda i: bool(STATE["addr"])),
            pystray.MenuItem("Adres kopieren",
                             lambda i, it: _copy(STATE["addr"]),
                             enabled=lambda i: bool(STATE["addr"])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Afsluiten", lambda i, it: (i.stop(), os._exit(0))))

    icon = pystray.Icon("DraveKITT", _icon_image(),
                        "DraveKITT hoofdkwartier (opstarten...)", menu())
    threading.Thread(target=_worker, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
