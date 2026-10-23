# -*- coding: utf-8 -*-
"""kitt_server.py - het "hoofdkwartier" voor DraveKITT Mobile (persoonlijk).

Hergebruikt de code, omgeving en het model van je DraveKITT-installatie ernaast
(../DraveKITT). Het zware werk (model + zoeken + weer) gebeurt hier; je telefoon
stuurt alleen de vraag.

Endpoints:
  GET  /ping   -> {"ok": true, "name": "KITT"}
  POST /vraag  -> body {"text": "..."} -> {"reply": "..."}

Draaien kan op twee manieren:
  - als systeemvak-app (aanbevolen): kitt_server_tray.py / de EXE
  - als console:                     dit bestand direct (python kitt_server.py)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- de DraveKITT-app vinden (werkt ook na verplaatsen naar een andere schijf,
#     zolang DraveKITT bij KITT-Server in de buurt staat) ---
try:
    from uitspraak import uitspraak as _uitspraak
except Exception:
    try:
        from .uitspraak import uitspraak as _uitspraak
    except Exception:  # zonder uitspraak.py gewoon de tekst zelf
        def _uitspraak(t, taal="nl"):
            return t


def _here():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _find_app_dir():
    # 1) handmatig opgegeven pad heeft voorrang
    env = os.environ.get("DRAVEKITT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    here = _here()
    # 2) een tekstbestand 'dravekitt_path.txt' naast de exe/het script
    try:
        pf = os.path.join(here, "dravekitt_path.txt")
        if os.path.isfile(pf):
            p = open(pf, encoding="utf-8").read().strip()
            if p and os.path.isdir(p):
                return os.path.abspath(p)
    except Exception:
        pass
    # 3) zoek een map 'DraveKITT' een paar niveaus omhoog (vangt ook de dist-map)
    d = here
    for _ in range(6):
        cand = os.path.join(d, "DraveKITT")
        if os.path.isfile(os.path.join(cand, "brain.py")) or \
           os.path.isdir(os.path.join(cand, "DraveKITT-data")):
            return os.path.abspath(cand)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    # 4) terugval
    return os.path.abspath(os.path.join(here, "..", "DraveKITT"))


APP_DIR = _find_app_dir()
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

PORT = 8000

# globale toestand (gevuld door build())
BRAIN = None
TOKEN = ""
_LOCK = threading.Lock()


def data_dir():
    d = os.path.join(APP_DIR, "DraveKITT-data")
    os.makedirs(d, exist_ok=True)
    return d


def load_config():
    cfg = {
        "backend": "local",
        "local_repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "local_file": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "model": "llama3.2",
        "ollama_host": "http://localhost:11434",
        "online_search": True,
        "search_engine": "startpage",
        "user_name": "",
        "instructions": "",
        "server_token": "",
    }
    try:
        with open(os.path.join(data_dir(), "config.json"), "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def build(on_status=None):
    """Zet het KITT-brein klaar (laadt het model). Geeft (ok, melding) terug."""
    global BRAIN, TOKEN
    try:
        from brain import Brain
        from localbrain import LocalBackend
        from search import Search
        from memory import Memory
    except ImportError:
        msg = ("KITT-Server heeft de map DraveKITT nodig (met brain.py erin).\n\n"
               "Zo los je het op:\n"
               "1. Download DraveKITT als broncode: github.com/mbrv4ever/DraveKITT \u2192 Code \u2192 Download ZIP.\n"
               "2. Pak hem uit en zet de map 'DraveKITT' naast de map van KITT-Server.\n"
               "   (Of zet het pad naar die map in het bestand dravekitt_path.txt naast KITT-Server.exe.)\n\n"
               "Gezocht in: %s" % APP_DIR)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "KITT-Server", 0x30)
        except Exception:
            pass
        raise SystemExit(msg)

    cfg = load_config()
    TOKEN = (cfg.get("server_token") or "").strip()
    brain = Brain(host=cfg.get("ollama_host"), model=cfg.get("model"))
    if cfg.get("backend", "local") == "local":
        brain.local = LocalBackend(cfg.get("local_repo"), cfg.get("local_file"),
                                   data_dir())
    try:
        brain.memory = Memory(os.path.join(data_dir(), "kitt-geheugen.db"))
    except Exception:
        brain.memory = None
    if cfg.get("online_search", True):
        try:
            brain.search = Search(engine=cfg.get("search_engine", "startpage"))
        except Exception:
            brain.search = None
    brain.user_name = cfg.get("user_name", "")
    brain.instructions = cfg.get("instructions", "")
    if on_status:
        on_status("Model laden...")
    ok = False
    try:
        if brain.local is not None:
            ok = bool(brain.local.ensure())     # lokaal model (zoals KITT zelf)
        else:
            ok = bool(brain.ensure_running())   # Ollama-backend
    except Exception as e:
        if on_status:
            on_status("Model laden mislukt: %s" % e)
    BRAIN = brain
    # de stem (neuvoice) vast op de achtergrond klaarzetten
    threading.Thread(target=_ensure_synth, daemon=True).start()
    return ok, ("Model geladen." if ok else
                "Model nog niet beschikbaar - download het eerst in DraveKITT.")


_WMO = {0: "helder", 1: "overwegend helder", 2: "half bewolkt", 3: "bewolkt",
        45: "mistig", 48: "mist met rijp", 51: "lichte motregen", 53: "motregen",
        55: "dichte motregen", 56: "ijzel", 57: "ijzel", 61: "lichte regen",
        63: "regen", 65: "zware regen", 66: "ijzel", 67: "ijzel",
        71: "lichte sneeuw", 73: "sneeuw", 75: "zware sneeuw", 77: "sneeuwkorrels",
        80: "lichte buien", 81: "buien", 82: "zware buien", 85: "sneeuwbuien",
        86: "zware sneeuwbuien", 95: "onweer", 96: "onweer met hagel",
        99: "zwaar onweer met hagel"}


def _extract_stad(text):
    import re
    m = re.search(r'\bin\s+(.+)$', text, re.I) or re.search(
        r'\bweer(?:\s+(?:van|voor))?\s+(.+)$', text, re.I)
    return (m.group(1).strip(" ?.!,") if m else "")


def weerbericht(stad):
    """Echt actueel weer via Open-Meteo (gratis, geen sleutel). None bij mislukken."""
    import urllib.request
    import urllib.parse
    try:
        g = ("https://geocoding-api.open-meteo.com/v1/search?"
             + urllib.parse.urlencode({"name": stad, "count": 1, "language": "nl"}))
        with urllib.request.urlopen(g, timeout=8) as r:
            res = (json.loads(r.read().decode("utf-8")).get("results") or [])
        if not res:
            return None
        loc = res[0]
        naam = loc.get("name", stad)
        w = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto"}))
        with urllib.request.urlopen(w, timeout=8) as r:
            cur = (json.loads(r.read().decode("utf-8")).get("current") or {})
        t = cur.get("temperature_2m")
        if t is None:
            return None
        oms = _WMO.get(int(cur.get("weather_code", -1)), "wisselend weer")
        zin = "In %s is het nu %d graden, %s" % (naam, round(t), oms)
        gevoel = cur.get("apparent_temperature")
        if gevoel is not None and abs(gevoel - t) >= 2:
            zin += " (gevoelstemperatuur %d)" % round(gevoel)
        wind = cur.get("wind_speed_10m")
        if wind is not None:
            zin += ", wind %d kilometer per uur" % round(wind)
        return zin + "."
    except Exception:
        return None


def antwoord(text):
    text = (text or "").strip()
    if not text:
        return "Ik luister."
    # echt weerbericht onderscheppen (anders verzint het model iets)
    low = text.lower()
    if (low.startswith("wat is het weer") or low.startswith("weer in")
            or "het weer in" in low or "weerbericht" in low):
        stad = _extract_stad(text)
        if stad:
            w = weerbericht(stad)
            if w:
                return w
    if BRAIN is None:
        return "Mijn systemen starten nog op. Een ogenblik."
    with _LOCK:
        try:
            return BRAIN.ask(text)
        except Exception as e:
            return "Er ging iets mis in mijn systemen: %s" % e


# --- neuvoice-stem (zelfde als de desktop-KITT) -> WAV voor de telefoon ---
_SYNTH = {"tts": None, "sr": 24000, "failed": False,
          "names": [], "default": "", "styles": {}}
_SYNTH_LOCK = threading.Lock()


def _ensure_synth():
    if _SYNTH["tts"] is not None or _SYNTH["failed"]:
        return _SYNTH["tts"] is not None
    with _SYNTH_LOCK:
        if _SYNTH["tts"] is not None or _SYNTH["failed"]:
            return _SYNTH["tts"] is not None
        try:
            print("[stem] neuvoice laden...")
            from neuvoice import TTS
            cfg = load_config()
            want = (cfg.get("voice_name") or "").strip().lower()
            tts = TTS(auto_download=True)
            names = list(getattr(tts, "voice_style_names", []) or [])
            pick = None
            for n in names:
                if n.strip().lower() == want:
                    pick = n
                    break
            if pick is None and "Leon" in names:
                pick = "Leon"
            if pick is None:
                for n in names:                       # anders een mannenstem
                    if n.upper().startswith("M") or "MALE" in n.upper():
                        pick = n
                        break
            if pick is None and names:
                pick = names[0]
            _SYNTH["tts"] = tts
            _SYNTH["names"] = names
            _SYNTH["default"] = pick or ""
            _SYNTH["sr"] = int(getattr(tts, "sample_rate", 24000) or 24000)
            print("[stem] klaar. Stemmen: %d, standaard: %s" % (len(names), pick))
        except Exception as e:
            _SYNTH["failed"] = True
            print("[stem] neuvoice mislukt:", e)
    return _SYNTH["tts"] is not None


def _style_for(name):
    """Geef (en cache) de neuvoice-stijl voor een stemnaam (of de standaard)."""
    name = name or _SYNTH["default"]
    if not name:
        return None
    if name not in _SYNTH["styles"]:
        try:
            _SYNTH["styles"][name] = _SYNTH["tts"].get_voice_style(name)
        except Exception:
            _SYNTH["styles"][name] = None
    return _SYNTH["styles"][name]


def voices_list():
    _ensure_synth()
    return list(_SYNTH.get("names", []))


def synth_wav(text, voice=None, speed=None):
    """Spreek tekst in met neuvoice en geef WAV-bytes terug (of None).
    voice/speed overschrijven de standaard (zodat de telefoon de stem kan kiezen)."""
    text = (text or "").strip()
    if not text or not _ensure_synth():
        return None
    try:
        import io
        import wave
        import numpy as np
        cfg = load_config()
        try:
            spd = float(speed) if speed else float(cfg.get("voice_speed", 1.0) or 1.0)
        except Exception:
            spd = 1.0
        if not (0.5 <= spd <= 2.0):
            spd = 1.0
        style = _style_for((voice or "").strip())
        with _SYNTH_LOCK:
            wav, _dur = _SYNTH["tts"].synthesize(
                _uitspraak(text, cfg.get("lang", "nl")), voice_style=style, total_steps=10, speed=spd,
                lang=cfg.get("lang", "nl"))
        data = np.asarray(wav, dtype=np.float32).flatten()
        i16 = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_SYNTH["sr"])
            w.writeframes(i16.tobytes())
        out = buf.getvalue()
        print("[spreek] %d bytes audio gemaakt (stem: %s)" % (len(out), voice or _SYNTH["default"]))
        return out
    except Exception as e:
        print("[spreek] synth-fout:", e)
        return None


KITT_HTML = '''<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#0b0b0e">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>DraveKITT</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-192.png">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html,body { margin:0; height:100%; background:#0b0b0e; color:#e8e9ef;
    font-family:Segoe UI,Roboto,Arial,sans-serif; overflow:hidden; }
  #app { display:flex; flex-direction:column; height:100%; padding:8px; gap:6px; }
  #top { display:flex; align-items:center; gap:8px; height:8%; }
  #title { font-size:26px; font-weight:bold; color:#ececf2; flex:1; }
  #gear { background:#33333c; color:#e8e9ef; border:0; border-radius:8px;
    font-size:15px; padding:8px 12px; }
  #dash { display:flex; gap:6px; height:42%; }
  .col { display:flex; flex-direction:column; gap:6px; width:28%; }
  .kbtn { flex:1; border:0; border-radius:14px; font-weight:bold; font-size:15px;
    color:#16120a; }
  .amber { background:#e6b81f; } .red { background:#c7281e; color:#fff0f0; }
  #vbox { width:44%; height:100%; background:#000; border-radius:10px; }
  #answer { flex:1; display:flex; align-items:center; justify-content:center;
    text-align:center; font-size:19px; color:#cdd6ea; padding:0 8px; }
  #q { width:100%; font-size:19px; padding:12px; border-radius:8px; border:0;
    background:#16161b; color:#eceef2; }
  #btns { display:flex; gap:10px; height:11%; }
  #btns button { flex:1; border:0; border-radius:10px; font-size:19px; font-weight:bold; }
  #ask { background:#6fa3d6; color:#10141a; } #speak { background:#b32d28; color:#fff5f5; }
  .hidden { display:none !important; }
  #settings { position:fixed; inset:0; background:rgba(0,0,0,.55);
    display:flex; align-items:center; justify-content:center; padding:14px; }
  #scard { background:#1b1b22; border-radius:12px; padding:16px; width:100%;
    max-width:440px; display:flex; flex-direction:column; gap:12px; }
  #scard h2 { margin:0; font-size:20px; }
  #scard label { font-size:15px; color:#b9c2d6; }
  #scard select, #scard input { font-size:18px; padding:10px; border-radius:8px;
    border:0; background:#101015; color:#eceef2; width:100%; }
  #scard .row { display:flex; gap:10px; }
  #scard .row button { flex:1; border:0; border-radius:8px; font-size:17px; padding:12px; }
  #save { background:#6fa3d6; color:#10141a; } #close { background:#3a3a44; color:#e8e9ef; }
  #test { background:#33333c; color:#e8e9ef; border:0; border-radius:8px; font-size:16px; padding:11px; }
</style>
</head>
<body>
<div id="app">
  <div id="top"><div id="title">DraveKITT</div><button id="gear">Instellen</button></div>
  <div id="dash">
    <div class="col" id="left"></div>
    <canvas id="vbox"></canvas>
    <div class="col" id="right"></div>
  </div>
  <div id="answer">Alle systemen online. Waarmee kan ik van dienst zijn?</div>
  <input id="q" placeholder="Typ je vraag...">
  <div id="btns"><button id="ask">Vraag</button><button id="speak">Spreek</button></div>
</div>

<div id="settings" class="hidden"><div id="scard">
  <h2>Instellingen</h2>
  <label>KITT-stem (van de pc)</label>
  <select id="voice"><option value="">standaard</option></select>
  <label>Spreeksnelheid: <span id="spdval">1.0</span></label>
  <input id="speed" type="range" min="0.6" max="1.6" step="0.05" value="1.0">
  <label>Wachtwoord (alleen nodig als je dat op de server hebt gezet)</label>
  <input id="token" type="password" placeholder="laat leeg als geen wachtwoord">
  <button id="test">Test stem</button>
  <div class="row"><button id="close">Sluiten</button><button id="save">Opslaan</button></div>
</div></div>

<script>
const LEFT=[["TIJD","amber"],["ACCU","amber"],["SYSTEEM","red"],["GRAP","red"],["WEER","red"]];
const RIGHT=[["HERHAAL","amber"],["NIEUWS","amber"],["NIEUW","red"],["SCAN","red"],["HULP","red"]];
const $=s=>document.querySelector(s);
let cfg={voice:"",speed:1.0,token:""};
try{cfg=Object.assign(cfg,JSON.parse(localStorage.getItem("kitt")||"{}"));}catch(e){}
let lastReply="", pending=null;
if("serviceWorker" in navigator){navigator.serviceWorker.register("/sw.js").catch(()=>{});}

function mkcol(el,arr){arr.forEach(([t,c])=>{const b=document.createElement("button");
  b.className="kbtn "+c;b.textContent=t;b.onclick=()=>side(t);el.appendChild(b);});}
mkcol($("#left"),LEFT); mkcol($("#right"),RIGHT);

// ---- voicebox ----
const cv=$("#vbox"); const ctx=cv.getContext("2d");
let phase=0, level=0, active=false, dpr=Math.max(1,window.devicePixelRatio||1);
function resize(){cv.width=cv.clientWidth*dpr; cv.height=cv.clientHeight*dpr;}
window.addEventListener("resize",resize);
function rr(x,y,w,h,r){if(ctx.roundRect){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fill();}
  else ctx.fillRect(x,y,w,h);}
function draw(){const W=cv.width,H=cv.height; ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#000"; ctx.fillRect(0,0,W,H);
  if(level<0.05) return;
  const cx=W/2, cy=H/2, maxhalf=H/2-4*dpr;
  const colw=Math.max(10*dpr,W*0.16), spacing=W*0.30;
  const centers=[cx-spacing,cx,cx+spacing];
  const pitch=Math.max(8*dpr,H/16), segh=pitch*0.6;
  const amp=level*Math.max(0.18,Math.min(1,0.45+0.55*Math.abs(0.7*Math.sin(phase*2)+0.3*Math.sin(phase*3.3))));
  const sidej=0.80+0.18*Math.abs(Math.sin(phase*2.4));
  const hs=[0.55*amp*sidej,1.0*amp,0.55*amp*sidej];
  for(let ci=0;ci<3;ci++){const colh=Math.max(0.06,Math.min(1,hs[ci]));
    const nseg=Math.max(1,Math.floor((colh*maxhalf)/pitch));
    for(let k=0;k<=nseg;k++){const inten=Math.max(0.45,1-(k/(nseg+0.001))*0.5);
      ctx.fillStyle="rgb("+Math.round(255*(0.32+0.68*inten))+","+Math.round(255*0.05*inten)+","+Math.round(255*0.03)+")";
      rr(centers[ci]-colw/2, cy-(k*pitch)-segh, colw, segh, 3*dpr);
      if(k>0) rr(centers[ci]-colw/2, cy+k*pitch, colw, segh, 3*dpr);}}}
function loop(){const t=active?1:0; level+=(t-level)*0.12; phase+=0.10; draw(); requestAnimationFrame(loop);}
resize(); loop();

// ---- netwerk ----
function hdr(){const h={"Content-Type":"application/json"}; if(cfg.token) h["X-Token"]=cfg.token; return h;}
function setAnswer(t){$("#answer").textContent=t;}
function speak(text){
  fetch("/spreek",{method:"POST",headers:hdr(),body:JSON.stringify({text:text,voice:cfg.voice,speed:cfg.speed})})
   .then(r=>{ if(r.status===204||!r.ok){browserSpeak(text);return null;} return r.blob(); })
   .then(b=>{ if(!b)return; const u=URL.createObjectURL(b); const a=new Audio(u);
     a.onplay=()=>{active=true;};                       // beweeg ALLEEN tijdens de stem
     a.onended=()=>{active=false; URL.revokeObjectURL(u);};
     a.onpause=()=>{active=false;}; a.onerror=()=>{active=false;};
     a.play().catch(()=>{active=false;}); })
   .catch(()=>browserSpeak(text));
}
function browserSpeak(text){ try{const u=new SpeechSynthesisUtterance(text); u.lang="nl-NL"; u.rate=cfg.speed||1;
  u.onstart=()=>active=true; u.onend=()=>active=false; u.onerror=()=>active=false; speechSynthesis.speak(u);}catch(e){} }

function say(text){ lastReply=text; setAnswer(text); speak(text); }

function ask(text){ text=(text||"").trim(); if(!text)return;
  $("#q").value="";
  if(pending==="weer"){pending=null; text="wat is het weer in "+text;}
  else if(pending==="nieuws"){pending=null; text="geef kort het nieuws over "+text;}
  setAnswer("Moment, ik zoek het even voor je op...");
  fetch("/vraag",{method:"POST",headers:hdr(),body:JSON.stringify({text:text})})
   .then(r=>r.ok?r.json():Promise.reject(r.status))
   .then(d=>say(d.reply||"Begrepen."))
   .catch(()=>{active=false; setAnswer("Ik kan het hoofdkwartier nu niet bereiken.");});
}

function side(t){
  if(t==="TIJD"){const n=new Date(); say("Het is "+("0"+n.getHours()).slice(-2)+":"+("0"+n.getMinutes()).slice(-2)+" uur.");}
  else if(t==="ACCU"){ if(navigator.getBattery){navigator.getBattery().then(b=>say("Energiestatus: "+Math.round(b.level*100)+" procent."));} else say("Energiestatus: alle systemen optimaal.");}
  else if(t==="SYSTEEM"){say("Diagnose voltooid. Alle systemen functioneren naar behoren.");}
  else if(t==="GRAP"){ask("vertel een korte grap");}
  else if(t==="SCAN"){say("Scan voltooid. Geen bedreigingen gedetecteerd.");}
  else if(t==="HULP"){say("Vraag me naar de tijd, het weer of nieuws, of praat gewoon. WEER en NIEUWS vragen eerst om een plaats of onderwerp.");}
  else if(t==="NIEUW"){$("#q").value=""; say("Nieuw gesprek. Ik luister.");}
  else if(t==="HERHAAL"){say(lastReply||"Ik heb nog niets gezegd om te herhalen.");}
  else if(t==="WEER"){pending="weer"; setAnswer("Voor welke plaats wil je het weer? Typ het in.");}
  else if(t==="NIEUWS"){pending="nieuws"; setAnswer("Welk onderwerp of welke bron? Typ het in.");}
}

$("#ask").onclick=()=>ask($("#q").value);
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")ask($("#q").value);});

// ---- spreken (microfoon) ----
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
$("#speak").onclick=async ()=>{
  if(!window.isSecureContext){ setAnswer("Spreken werkt alleen via een beveiligde (https) verbinding."); return; }
  if(!SR){ setAnswer("Deze browser ondersteunt spraakherkenning niet. Probeer Chrome."); return; }
  // eerst microfoon-toestemming forceren (anders blijft het stil)
  try{ const s=await navigator.mediaDevices.getUserMedia({audio:true}); s.getTracks().forEach(t=>t.stop()); }
  catch(e){ setAnswer("Geen toegang tot de microfoon. Sta die toe voor deze app (slotje/instellingen)."); return; }
  const r=new SR(); r.lang="nl-NL"; r.interimResults=false; r.maxAlternatives=1;
  let got=false;
  setAnswer("Luisteren... spreek nu.");
  r.onresult=e=>{got=true; active=false; const txt=e.results[0][0].transcript; $("#q").value=txt; ask(txt);};
  r.onerror=ev=>{active=false; setAnswer("Spraak lukt niet ("+(ev.error||"?")+") - typ je vraag.");};
  r.onend=()=>{active=false; if(!got) setAnswer("Ik hoorde niets. Tik nog eens op Spreek en praat duidelijk.");};
  try{ r.start(); }catch(e){ setAnswer("Kon niet starten met luisteren - typ je vraag."); }
};

// ---- instellingen ----
function openSettings(){ $("#speed").value=cfg.speed; $("#spdval").textContent=cfg.speed;
  $("#token").value=cfg.token||""; $("#voice").value=cfg.voice||"";
  fetch("/stemmen").then(r=>r.json()).then(d=>{ const sel=$("#voice");
    sel.innerHTML='<option value="">standaard</option>';
    (d.voices||[]).forEach(v=>{const o=document.createElement("option");o.value=v;o.textContent=v;sel.appendChild(o);});
    sel.value=cfg.voice||""; }).catch(()=>{});
  $("#settings").classList.remove("hidden"); }
$("#gear").onclick=openSettings;
$("#close").onclick=()=>$("#settings").classList.add("hidden");
$("#speed").oninput=()=>$("#spdval").textContent=(+$("#speed").value).toFixed(2);
$("#test").onclick=()=>{ cfg.voice=$("#voice").value; cfg.speed=+$("#speed").value; cfg.token=$("#token").value.trim(); speak("Hallo, dit is de gekozen KITT-stem."); };
$("#save").onclick=()=>{ cfg.voice=$("#voice").value; cfg.speed=+$("#speed").value; cfg.token=$("#token").value.trim();
  localStorage.setItem("kitt",JSON.stringify(cfg)); $("#settings").classList.add("hidden"); setAnswer("Instellingen opgeslagen."); };
</script>
</body>
</html>'''


_HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

MANIFEST_JSON = '''{
  "name": "DraveKITT",
  "short_name": "KITT",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#0b0b0e",
  "theme_color": "#0b0b0e",
  "icons": [
    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
  ]
}'''

SW_JS = '''self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => self.clients.claim());
self.addEventListener("fetch", e => {});
'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _token_ok(self):
        return (not TOKEN) or self.headers.get("X-Token", "") == TOKEN

    def _send_raw(self, ctype, data):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html):
        self._send_raw("text/html; charset=utf-8", html.encode("utf-8"))

    def _send_file(self, name, ctype):
        try:
            with open(os.path.join(_HERE, name), "rb") as f:
                self._send_raw(ctype, f.read())
        except Exception:
            self._send(404, {"error": "bestand niet gevonden"})

    def do_GET(self):
        path = self.path.rstrip("/")
        if path in ("", "/app"):
            self._send_html(KITT_HTML)          # het KITT-dashboard (webpagina)
        elif path == "/ping":
            self._send(200, {"ok": True, "name": "KITT"})
        elif path == "/stemmen":
            self._send(200, {"voices": voices_list()})
        elif path == "/manifest.webmanifest":
            self._send_raw("application/manifest+json; charset=utf-8",
                           MANIFEST_JSON.encode("utf-8"))
        elif path == "/sw.js":
            self._send_raw("application/javascript; charset=utf-8",
                           SW_JS.encode("utf-8"))
        elif path == "/icon-192.png":
            self._send_file("icon-192.png", "image/png")
        elif path == "/icon-512.png":
            self._send_file("icon-512.png", "image/png")
        else:
            self._send(404, {"error": "onbekend"})

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in ("/vraag", "/spreek"):
            self._send(404, {"error": "onbekend"})
            return
        if not self._token_ok():
            self._send(403, {"error": "sleutel onjuist"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            self._send(400, {"error": "ongeldige vraag"})
            return
        if path == "/vraag":
            vraag = data.get("text", "")
            print("[vraag]", vraag[:80])
            rep = antwoord(vraag)
            print("[antwoord]", rep[:80])
            self._send(200, {"reply": rep})
            return
        # /spreek -> neuvoice-audio (WAV) terug, of 204 als er geen stem is
        wav = synth_wav(data.get("text", ""), data.get("voice"), data.get("speed"))
        if not wav:
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav)))
        self.end_headers()
        self.wfile.write(wav)

    def log_message(self, *a):
        pass


DISCOVERY_PORT = 8001


def _udp_responder(http_port):
    """Antwoordt op 'zoek'-pakketjes van de telefoon met ons adres (LAN-ontdekking)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass
    try:
        s.bind(("", DISCOVERY_PORT))
    except Exception:
        return
    while True:
        try:
            data, addr = s.recvfrom(1024)
            if b"DRAVEKITT" in data:
                msg = "DRAVEKITT|http://%s:%d" % (lan_ip(), http_port)
                s.sendto(msg.encode("utf-8"), addr)
        except Exception:
            break


def run_server(on_ready=None):
    """Start de webserver (blokkeert). on_ready(ip, port) wordt aangeroepen."""
    ip = lan_ip()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    threading.Thread(target=_udp_responder, args=(PORT,), daemon=True).start()
    if on_ready:
        on_ready(ip, PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def main():
    try:  # Dravenlock: stille update-check (uit te zetten in de melding)
        import drave_update
        drave_update.start(None, 'KITT-Server', '1.0.4')
    except Exception:
        pass
    print("KITT-hoofdkwartier: brein klaarzetten... (code uit %s)" % APP_DIR)
    ok, msg = build(lambda s: print(s))
    print(msg)

    def ready(ip, port):
        print("\n========= KITT-hoofdkwartier draait =========")
        print(" Vul op je telefoon dit adres in: http://%s:%d" % (ip, port))
        print(" (Telefoon en pc op hetzelfde wifi.) Stoppen: Ctrl+C.")
        print("=============================================\n")

    run_server(ready)


if __name__ == "__main__":
    main()
