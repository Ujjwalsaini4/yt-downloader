# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify, send_file, render_template_string, abort
import tempfile, shutil, glob, threading, uuid, re, time
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Write cookies from environment variable -> cookies.txt
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

# ---------- FFmpeg detection ----------
def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg" or "/data/data/com.termux/files/usr/bin/ffmpeg"

HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML UI ----------
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Hyper Downloader</title>

<!-- Favicon: gradient square with HD -->
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' x2='1'%3E%3Cstop offset='0' stop-color='%236d28d9'/%3E%3Cstop offset='1' stop-color='%23111827'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='96' height='96' rx='16' fill='url(%23g)'/%3E%3Ctext x='50%25' y='58%25' text-anchor='middle' font-size='44' fill='%23fff' font-family='Arial,Helvetica,sans-serif' font-weight='700'%3EHD%3C/text%3E%3C/svg%3E">

<style>
  :root{
    --bg:#0b1220; --card:#0f172a; --text:#e6eefc; --muted:#9fb0c8; --border:#263143;
    --primary:#7c3aed; --accent:#22d3ee; --ring:#a78bfa;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#eef2f7; --card:#ffffff; --text:#0f172a; --muted:#475569; --border:#cbd5e1; --primary:#6d28d9; --accent:#06b6d4; --ring:#8b5cf6; }
  }

  /* MOBILE-FIRST BASE */
  *{box-sizing:border-box}
  html,body{height:100%}
  body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Noto Sans",sans-serif; font-size:15px; line-height:1.35}
  .wrap{max-width:980px;margin-inline:auto;padding-inline:12px}
  .box{background:var(--card);border:1px solid var(--border);border-radius:14px;box-shadow:0 6px 20px rgba(0,0,0,.14);padding:14px}
  h1,h2{margin:0;font-weight:800}
  .lead{margin:8px 0 12px;color:var(--muted);font-size:14px}

  /* HEADER */
  .header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 14px}
  .logo{width:40px;height:40px;border-radius:10px;flex:0 0 40px;background:linear-gradient(135deg,#6d28d9,#111827);display:grid;place-items:center;box-shadow:inset 0 0 1px rgba(255,255,255,.06)}
  .logo span{color:#fff;font-weight:800;font-size:16px}
  .brand{display:flex;flex-direction:row;align-items:center;gap:8px;min-width:0}
  .brand h1{font-size:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tag-prem{padding:6px 10px;border-radius:999px;font-size:13px;font-weight:700;border:1.4px solid #a78bfa;color:#c4b5fd;background:transparent}

  .spacer{flex:1 1 auto}

  /* NAV - mobile default: hide desktop links, show menu */
  .nav-links{display:none;align-items:center;gap:12px}
  .menu{display:block}
  .menu summary{list-style:none;cursor:pointer;padding:8px 12px;border-radius:12px;border:1px solid var(--border);color:var(--muted);background:transparent}
  .menu[open] summary{background:color-mix(in oklab,var(--border) 20%,transparent)}
  .menu a{display:block;padding:8px 0;color:var(--muted);text-decoration:none}

  /* FORM - stacked on mobile */
  form{display:block}
  .grid{display:grid;gap:10px;grid-template-columns:1fr}
  label{display:block;margin-bottom:6px;font-size:13px;color:var(--muted)}
  input,select,button{
    width:100%;padding:12px 10px;border-radius:10px;border:1px solid var(--border);
    background:transparent;color:var(--text);font-size:15px
  }
  input::placeholder{color:color-mix(in oklab,var(--muted) 70%,transparent)}
  select{appearance:none;padding-right:30px}
  button{border:none;background:var(--primary);color:#fff;font-weight:700;cursor:pointer;padding:12px 14px;border-radius:10px}

  /* Progress small but clear on phone */
  .progress{position:relative;width:100%;height:12px;background:color-mix(in oklab,var(--border) 65%,transparent);border-radius:999px;overflow:hidden;margin-top:6px}
  .bar{position:absolute;inset:0 100% 0 0;background:linear-gradient(90deg,var(--primary),var(--accent));transition:inset .18s ease}
  .pct{position:absolute;inset:0;display:grid;place-items:center;font-size:12px;color:#fff;font-weight:800}
  .footer{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-top:10px;font-size:13px}

  /* Preview */
  .preview{display:none;margin:10px 0;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--card)}
  .preview-row{display:flex;gap:10px;padding:8px;align-items:center}
  .thumb{width:96px;aspect-ratio:16/9;border-radius:8px;object-fit:cover;background:#ddd}
  .title{font-size:14px;font-weight:800;margin:0 0 4px}
  .sub{font-size:13px;color:var(--muted);margin:0}

  /* Feature/FAQ cards spacing optimized for small screens */
  .box + .box{margin-top:12px}
  .box ul{padding-left:18px;margin:8px 0}

  /* TABLET / SMALL DESKTOP */
  @media (min-width:640px){
    .wrap{padding-inline:18px}
    .box{padding:18px;border-radius:16px}
    .brand h1{font-size:20px}
    .logo{width:44px;height:44px}
    .thumb{width:110px}
    .grid{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end}
    .menu{display:none}
    .nav-links{display:flex}
    .nav-links a{font-size:15px;color:var(--muted);text-decoration:none;padding:6px 4px;border-radius:10px}
    .cta{padding:10px 14px;border-radius:12px;background:linear-gradient(90deg,var(--primary),var(--accent));color:#fff;font-weight:800}
    .progress{height:14px}
    .box + .box{margin-top:14px}
  }

  /* DESKTOP WIDE */
  @media (min-width:1024px){
    .wrap{max-width:1140px;margin-inline:auto}
    .brand h1{font-size:24px}
    .logo{width:48px;height:48px}
    .thumb{width:120px}
    .box{padding:22px}
    .grid{grid-template-columns:2.4fr 1fr 1.2fr auto}
    .lead{font-size:15px}
    .progress{height:16px}
  }

  /* Accessibility / small polish */
  button:focus, input:focus, select:focus, summary:focus{outline:none;box-shadow:0 0 0 4px color-mix(in oklab,var(--ring) 30%,transparent)}
</style>
</head>
<body>
  <main class="wrap">
    <header class="header">
      <div class="logo"><span>HD</span></div>

      <div class="brand">
        <h1>Hyper Downloader</h1>
        <span class="tag-prem">Premium</span>
      </div>

      <div class="spacer"></div>

      <!-- Desktop / tablet landscape -->
      <nav class="nav-links" aria-label="Primary">
        <a href="#features">Features</a>
        <a href="#faq">FAQ</a>
        <a class="cta" href="#">Go Premium</a>
      </nav>

      <!-- Mobile / small tablet -->
      <details class="menu">
        <summary>Menu</summary>
        <a href="#features">Features</a>
        <a href="#faq">FAQ</a>
        <a href="#">Go Premium</a>
      </details>
    </header>

    <section class="box" aria-labelledby="h2">
      <h2 id="h2">Download from YouTube</h2>
      <p class="lead">Paste a link, see preview, pick format, and download. Fast, minimal, mobile-first.</p>

      <div id="preview" class="preview" aria-live="polite">
        <div class="preview-row">
          <img id="thumb" class="thumb" alt="Thumbnail preview">
          <div class="meta">
            <p id="pTitle" class="title"></p>
            <p id="pSub" class="sub"></p>
          </div>
        </div>
      </div>

      <form id="frm">
        <div class="grid">
          <div>
            <label for="url">Video URL</label>
            <input id="url" inputmode="url" placeholder="https://www.youtube.com/watch?v=..." required>
          </div>

          <div>
            <label for="format">Format</label>
            <select id="format">
              <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
              <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
              <option value="mp4_best">4K MP4</option>
              <option value="audio_mp3" data-need-ffmpeg="1">Audio MP3 Only</option>
            </select>
          </div>

          <div>
            <label for="name">Filename (optional)</label>
            <input id="name" placeholder="My video">
          </div>

          <div>
            <label>&nbsp;</label>
            <button id="goBtn" type="submit">Download</button>
          </div>
        </div>

        <div style="margin-top:12px">
          <div class="progress" role="progressbar" aria-label="Download progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div id="bar" class="bar"></div>
            <div class="pct"><span id="pctTxt">0%</span></div>
          </div>
        </div>

        <div class="footer">
          <p id="msg" role="status" aria-live="polite"></p>
          <p class="muted"><span id="speedTxt">0 MB/s</span> • <span id="etaTxt">ETA —</span></p>
        </div>

        <p class="muted">Tip: If high-quality merge fails, install FFmpeg on the server or Termux.</p>
      </form>
    </section>

    <section id="features" class="box" style="margin-top:14px">
      <h2>Premium Features</h2>
      <ul>
        <li>Smart preview (title, channel, duration, thumbnail)</li>
        <li>Auto 4K/1080p selection based on availability</li>
        <li>Live percent, speed, and ETA</li>
        <li>MP3 extraction (requires FFmpeg)</li>
      </ul>
    </section>

    <section id="faq" class="box" style="margin-top:14px">
      <h2>FAQ</h2>
      <p class="muted">Why are some options disabled? Your server may not have FFmpeg installed.</p>
    </section>
  </main>

<script>
let job=null, debounceTimer=null, HAS_FFMPEG=false;
const frm = document.getElementById("frm");
const bar = document.getElementById("bar");
const msg = document.getElementById("msg");
const btn = document.getElementById("goBtn");
const pbar = document.querySelector(".progress");
const urlIn = document.getElementById("url");
const preview = document.getElementById("preview");
const pTitle = document.getElementById("pTitle");
const pSub = document.getElementById("pSub");
const thumb = document.getElementById("thumb");
const formatSel = document.getElementById("format");
const pctTxt = document.getElementById("pctTxt");
const speedTxt = document.getElementById("speedTxt");
const etaTxt = document.getElementById("etaTxt");

fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG = !!j.ffmpeg;
  if(!HAS_FFMPEG){
    [...formatSel.options].forEach(o=>{ if(o.dataset.needFfmpeg==="1"){ o.disabled = true; } });
    setMsg("FFmpeg not found: using single-file MP4.", false);
  }
}).catch(()=>{});

function setMsg(t, isErr=false){ msg.style.color = isErr ? "#fca5a5" : "inherit"; msg.textContent = t || ""; }
function setBusy(b){ btn.disabled = b; pbar.style.opacity = b ? "1" : ".7"; }
function hidePreview(){ preview.style.display="none"; thumb.removeAttribute("src"); pTitle.textContent=""; pSub.textContent=""; }
function showPreview(d){
  if(!d||!d.title){ hidePreview(); return; }
  pTitle.textContent = d.title||"";
  pSub.textContent = [d.channel,d.duration_str].filter(Boolean).join(" • ");
  if(d.thumbnail){ thumb.src=d.thumbnail; thumb.alt=d.title; }
  preview.style.display="block";
}

urlIn.addEventListener("input", ()=>{
  clearTimeout(debounceTimer);
  const url = urlIn.value.trim();
  if(!/^https?:\/\//i.test(url)){ hidePreview(); return; }
  debounceTimer = setTimeout(()=>fetchInfo(url), 500);
});

async function fetchInfo(url){
  try{
    const r = await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j = await r.json();
    if(!r.ok || j.error){ hidePreview(); return; }
    showPreview(j); setMsg("");
  }catch(e){ hidePreview(); }
}

frm.addEventListener("submit", async (e)=>{
  e.preventDefault();
  setMsg(""); setBusy(true); bar.style.inset = "0 100% 0 0"; pctTxt.textContent = "0%"; document.querySelector(".progress").setAttribute("aria-valuenow","0");

  const url = urlIn.value.trim();
  const fmt = formatSel.value;
  const name = document.getElementById("name").value.trim();

  if(!/^https?:\/\//i.test(url)){
    setMsg("Please paste a valid URL.", true); setBusy(false); return;
  }

  try{
    const r = await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url, format_choice:fmt, filename:name})});
    const j = await r.json();
    if(!r.ok){ throw new Error(j.error||"Failed to start"); }
    job = j.job_id; setMsg("Downloading..."); poll();
  }catch(err){
    setMsg(err.message||"Error starting download.", true);
    setBusy(false);
  }
});

function fmtBytes(x){
  if(!x || x<=0) return "0 B";
  const u=["B","KB","MB","GB","TB"]; let i=0; while(x>=1024 && i<u.length-1){ x/=1024; i++; } return (x<10?x.toFixed(1):Math.round(x))+" "+u[i];
}
function fmtETA(s){ if(!s && s!==0) return "ETA —"; const m=Math.floor(s/60), ss=Math.floor(s%60); return "ETA "+m+":"+(ss.toString().padStart(2,"0")); }

async function poll(){
  if(!job) return;
  try{
    const r = await fetch("/progress/"+job);
    if(r.status===404){ setMsg("Job expired.", true); setBusy(false); job=null; return; }
    const p = await r.json();
    const pct = Math.max(0, Math.min(100, p.percent||0));
    bar.style.inset = "0 "+(100-pct)+"% 0 0"; document.querySelector(".progress").setAttribute("aria-valuenow", String(pct));
    pctTxt.textContent = pct+"%";

    if(p.speed_bytes){ speedTxt.textContent = fmtBytes(p.speed_bytes)+"/s"; }
    if(p.eta !== undefined && p.eta !== null){ etaTxt.textContent = fmtETA(p.eta); }

    if(p.status==="finished"){ setMsg("Done. Preparing file...", false); setBusy(false); window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ setMsg(p.error||"Download failed.", true); setBusy(false); job=null; return; }
    setTimeout(poll, 700);
  }catch(e){
    setMsg("Network error.", true); setBusy(false); job=null;
  }
}
</script>
</body>
</html>
"""

# ---------- Jobs ----------
JOBS = {}

class Job:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.tmp = tempfile.mkdtemp(prefix="mvd_")
        self.percent = 0
        self.status = "queued"
        self.file = None
        self.error = None
        # Extra telemetry for UI
        self.speed_bytes = 0.0
        self.eta = None
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.started_at = time.time()
        JOBS[self.id] = self

# ---------- Helpers ----------
YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    if HAS_FFMPEG:
        return {
            "mp4_720"  : "bestvideo[height<=720]+bestaudio/best",
            "mp4_1080" : "bestvideo[height<=1080]+bestaudio/best",
            "mp4_best" : "bestvideo+bestaudio/best",
            "audio_mp3": "bestaudio/best"
        }
    else:
        return {
            "mp4_720"  : "best[ext=mp4][height<=720]/best[ext=mp4]",
            "mp4_1080" : "best[ext=mp4][height<=1080]/best[ext=mp4]",
            "mp4_best" : "best[ext=mp4]/best",
            "audio_mp3": None
        }

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error"; job.error="Invalid URL"; return

        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status = "error"; job.error = "Selected format requires FFmpeg"; return

        def hook(d):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                    downloaded = d.get("downloaded_bytes", 0)
                    job.total_bytes = int(total)
                    job.downloaded_bytes = int(downloaded)
                    job.percent = max(0, min(100, int(downloaded * 100 / total)))
                    spd = d.get("speed")
                    if spd is not None:
                        job.speed_bytes = float(spd)
                    job.eta = d.get("eta")
                elif d.get("status") == "finished":
                    job.percent = 100
            except Exception:
                pass

        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        out = os.path.join(job.tmp, base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": out,
            "merge_output_format": "mp4",
            "cookiefile": "cookies.txt",
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True
        }

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(job.tmp + "/*")
        job.file = max(files, key=os.path.getsize)
        job.status = "finished"

    except Exception as e:
        job.status="error"; job.error=str(e)[:300]

# ---------- Routes ----------
@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(
        target=run_download,
        args=(job, d.get("url",""), d.get("format_choice","mp4_best"), d.get("filename")),
        daemon=True
    ).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url","")
    try:
        with YoutubeDL({"skip_download":True,"quiet":True,"noplaylist":True,"cookiefile":"cookies.txt"}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title","")
        channel = info.get("uploader") or info.get("channel","")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}"})
    except Exception:
        return jsonify({"error":"Preview failed"}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j: abort(404)
    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": j.speed_bytes,
        "eta": j.eta,
        "downloaded": j.downloaded_bytes,
        "total": j.total_bytes
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j: abort(404)
    resp = send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    threading.Thread(target=lambda: (shutil.rmtree(j.tmp, ignore_errors=True), JOBS.pop(id,None)), daemon=True).start()
    return resp

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
