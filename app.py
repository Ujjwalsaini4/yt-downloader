# app.py
# -*- coding: utf-8 -*-
# Hyper Downloader - patched version (audio fixes included)
# Replace your current app file with this. Works with yt-dlp + ffmpeg if available.

import os
import time
import tempfile
import shutil
import glob
import threading
import uuid
import re
import mimetypes
from flask import Flask, request, jsonify, render_template_string, abort, send_file
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Save cookies if present (from environment)
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (UI kept as requested) ----------
HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hyper Downloader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#050b16;
  --card:#0a162b;
  --muted:#a3b5d2;
  --grad1:#2563eb;
  --grad2:#06b6d4;
  --accent:linear-gradient(90deg,var(--grad1),var(--grad2));
  --radius:16px;
  --pill-bg: rgba(255,255,255,0.03);
  --pill-border: rgba(255,255,255,0.06);
}
*{box-sizing:border-box;}
body{
  margin:0;
  background:radial-gradient(1200px 800px at 30% 20%,rgba(37,99,235,.08),transparent),
             radial-gradient(1000px 600px at 80% 90%,rgba(6,182,212,.1),transparent),
             var(--bg);
  color:#e8f0ff;
  font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans",sans-serif;
  -webkit-font-smoothing:antialiased;
  padding:clamp(12px,2vw,24px);
}
.wrap{max-width:960px;margin:auto;}
h1,h2{margin:0;font-weight:800;}
h2{font-size:22px;}
.small{font-size:13px;color:var(--muted);}

/* Header */
header{
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(255,255,255,0.02);
  border:1px solid rgba(255,255,255,0.05);
  padding:12px 18px;border-radius:var(--radius);
  box-shadow:0 6px 24px rgba(0,0,0,.3);
  backdrop-filter:blur(8px) saturate(120%);
}
.brand{display:flex;align-items:center;gap:12px;}
.logo{
  width:52px;height:52px;border-radius:14px;
  background:var(--accent);
  display:grid;place-items:center;
  color:#fff;font-weight:800;font-size:18px;
  box-shadow:0 8px 24px rgba(6,182,212,.25);
}
/* gentle background pulse for subtle shine */
@keyframes bgPulse {
  0% { filter: hue-rotate(0deg) saturate(100%); }
  50% { filter: hue-rotate(8deg) saturate(110%); }
  100% { filter: hue-rotate(0deg) saturate(100%); }
}
.logo { animation: bgPulse 8s ease-in-out infinite; }
.brand-title span{
  background:var(--accent);
  -webkit-background-clip:text;
  color:transparent;
}

/* Card */
.card{
  background:rgba(255,255,255,0.02);
  border:1px solid rgba(255,255,255,0.05);
  border-radius:var(--radius);
  box-shadow:0 8px 32px rgba(0,0,0,.4);
  padding:clamp(16px,3vw,28px);
  margin-top:20px;
  transition:transform .2s ease,box-shadow .3s ease;
}
.card:hover{transform:translateY(-4px);box-shadow:0 14px 40px rgba(0,0,0,.6);}

/* Form */
label{display:block;margin-bottom:6px;color:var(--muted);font-size:13px;}
input,select,button{
  width:100%;padding:12px 14px;border-radius:12px;
  border:1px solid rgba(255,255,255,0.07);
  background-color:#0d1c33;color:#e8f0ff;
  font-size:15px;
}
input::placeholder{color:#5a6b8a;}
button{
  background:var(--accent);border:none;font-weight:700;color:#fff;
  box-shadow:0 8px 28px rgba(6,182,212,.25);
  cursor:pointer;transition:transform .08s;
}
button:active{transform:scale(.98);}
button[disabled]{opacity:.6;cursor:not-allowed;}

/* Grid responsive */
.grid{display:grid;gap:12px;}
@media(min-width:700px){.grid{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end;}}
.full{grid-column:1/-1;}

/* Progress bar */
.progress{
  margin-top:14px;height:14px;border-radius:999px;
  background:rgba(255,255,255,0.04);
  overflow:hidden;position:relative;
}
.bar{
  width:0%;height:100%;
  background:var(--accent);
  transition:width .3s ease;
  box-shadow:0 0 20px rgba(6,182,212,.4);
}
.pct{
  position:absolute;left:50%;top:50%;
  transform:translate(-50%,-50%);
  color:#fff;font-weight:700;font-size:13px;
  text-shadow:0 1px 2px rgba(0,0,0,0.5);
}

/* sheen overlay on progress */
.bar::after{
  content:"";
  position:absolute;inset:0;
  background:linear-gradient(90deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02), rgba(255,255,255,0.06));
  transform:translateX(-40%);opacity:0.6;filter:blur(6px);
  animation: sheen 2.4s linear infinite;
}
@keyframes sheen{100%{transform:translateX(120%)}}

/* Status row: message left, ETA pill right */
.status-row{
  display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:12px;
}
.status-left{Color:var(--muted);font-size:13px;display:flex;align-items:center;gap:8px;}
.eta-pill{
  display:inline-flex;align-items:center;gap:10px;padding:8px 12px;border-radius:999px;
  background:var(--pill-bg);border:1px solid var(--pill-border);font-weight:700;font-size:13px;color:#fff;
  min-width:90px;justify-content:center;
  box-shadow:0 6px 18px rgba(6,182,212,0.06);
}
/* make ETA number monospaced-ish */
.eta-pill .label{opacity:0.85;color:var(--muted);font-weight:600;font-size:12px;margin-right:6px}
.eta-pill .value{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Roboto Mono,monospace;font-weight:800}

/* Preview */
.preview{
  display:none;margin-top:10px;padding:10px;
  background:rgba(255,255,255,0.02);
  border-radius:12px;border:1px solid rgba(255,255,255,0.05);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);
}
.preview-row{display:flex;gap:10px;align-items:center;}
.thumb{width:120px;height:68px;border-radius:8px;object-fit:cover;background:#081627;}
.meta .title{font-weight:700;font-size:15px;}
.meta .sub{color:var(--muted);font-size:13px;margin-top:4px;}

footer{margin-top:20px;text-align:center;color:var(--muted);font-size:12px;}
/* responsive tweaks */
@media(max-width:520px){
  .eta-pill{min-width:72px;padding:6px 10px;font-size:12px}
  .brand-title h1{font-size:18px}
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand">
    <div class="logo">HD</div>
    <div class="brand-title"><h1>Hyper <span>Downloader</span></h1></div>
  </div>
</header>

<main class="card">
  <h2>⬇️ Download from YouTube</h2>
  <p class="small">Paste your link, select format, and start. Progress and speed show in real-time.</p>

  <div id="preview" class="preview">
    <div class="preview-row">
      <img id="thumb" class="thumb" alt="">
      <div class="meta">
        <div id="pTitle" class="title"></div>
        <div id="pSub" class="sub"></div>
      </div>
    </div>
  </div>

  <form id="frm">
    <div class="grid">
      <div><label>Video URL</label><input id="url" placeholder="https://youtube.com/watch?v=..." required></div>
      <div><label>Format</label>
        <select id="format">
          <optgroup label="Video (MP4)">
            <option value="mp4_144" data-need-ffmpeg="0">144p MP4</option>
            <option value="mp4_240" data-need-ffmpeg="0">240p MP4</option>
            <option value="mp4_360" data-need-ffmpeg="0">360p MP4</option>
            <option value="mp4_480" data-need-ffmpeg="0">480p MP4</option>
            <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
            <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
          </optgroup>
          <optgroup label="Audio">
            <option value="audio_mp3_128" data-need-ffmpeg="1">MP3 — 128 kbps</option>
            <option value="audio_mp3_192" data-need-ffmpeg="1">MP3 — 192 kbps</option>
            <option value="audio_mp3_320" data-need-ffmpeg="1">MP3 — 320 kbps</option>
            <option value="audio_best" data-need-ffmpeg="0">Best audio (original)</option>
          </optgroup>
        </select>
      </div>
      <div><label>Filename</label><input id="name" placeholder="My video"></div>
      <div class="full"><button id="goBtn" type="submit">⚡ Start Download</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div><div id="pct" class="pct">0%</div></div>

  <!-- status row: left = message, right = ETA pill -->
  <div class="status-row" aria-live="polite">
    <div id="msg" class="status-left">—</div>
    <div id="eta" class="eta-pill"><span class="label">ETA:</span><span class="value">--</span></div>
  </div>
</main>

<footer>© 2025 Hyper Downloader — Auto cleanup & responsive UI</footer>
</div>

<script>
let job=null;
const bar=document.getElementById("bar"),pct=document.getElementById("pct");
const msg=document.getElementById("msg");
const etaEl=document.getElementById("eta");
const etaVal=document.querySelector("#eta .value");
const urlIn=document.getElementById("url"),thumb=document.getElementById("thumb"),preview=document.getElementById("preview"),pTitle=document.getElementById("pTitle"),pSub=document.getElementById("pSub");

document.getElementById("frm").addEventListener("submit",async(e)=>{
  e.preventDefault();
  msg.textContent="⏳ Starting...";
  etaVal.textContent="--";
  const url=urlIn.value.trim(),fmt=document.getElementById("format").value,name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j=await r.json();
    if(!r.ok)throw new Error(j.error||"Failed to start");
    job=j.job_id;poll();
  }catch(err){msg.textContent="❌ "+err.message; etaVal.textContent="--";}
});

urlIn.addEventListener("input",()=>{
  clearTimeout(window._deb);
  const u=urlIn.value.trim();
  if(!/^https?:\/\//i.test(u)){preview.style.display="none";return;}
  window._deb=setTimeout(()=>fetchInfo(u),500);
});
async function fetchInfo(url){
  try{
    const r=await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j=await r.json();
    if(!r.ok||j.error){preview.style.display="none";return;}
    pTitle.textContent=j.title||"";pSub.textContent=[j.channel,j.duration_str].filter(Boolean).join(" • ");
    if(j.thumbnail)thumb.src=j.thumbnail;
    preview.style.display="block";
  }catch(e){preview.style.display="none";}
}

function formatSeconds(s){
  if(s===null || s===undefined || !isFinite(s) || s<0) return "--";
  s=Math.round(s);
  const h=Math.floor(s/3600); const m=Math.floor((s%3600)/60); const sec=s%60;
  if(h>0) return `${h}h ${m}m ${sec}s`;
  if(m>0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function formatMbps(speed_b){
  if(!speed_b || speed_b <= 0) return "0.0 Mbps";
  const mbps = (speed_b * 8) / 1_000_000;
  return mbps.toFixed(1) + " Mbps";
}

async function poll(){
  if(!job)return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){msg.textContent="Job expired.";etaVal.textContent="--";job=null;return;}
    const p=await r.json();
    const pctv=Math.max(0,Math.min(100,p.percent||0));
    bar.style.width=pctv+"%";pct.textContent=pctv+"%";

    if(p.status==="finished"){msg.textContent="✅ Preparing file...";}
    else if(p.status==="error"){msg.textContent="❌ "+(p.error||"Download failed");}
    else msg.textContent = p.status==="downloaded" ? "✅ Download complete (fetching file)..." : "Downloading…";

    // ETA preference: server-provided -> client-calc fallback
    let etaText="--";
    if(typeof p.eta_seconds !== "undefined" && p.eta_seconds !== null){
      etaText = formatSeconds(p.eta_seconds);
    } else {
      try{
        const downloaded = p.downloaded_bytes || 0;
        const total = p.total_bytes || 0;
        const speed = p.speed_bytes || 0;
        if(total>0 && downloaded>0 && speed>0 && downloaded < total){
          const remain = (total - downloaded)/speed;
          etaText = formatSeconds(remain);
        } else {
          etaText="--";
        }
      }catch(e){etaText="--";}
    }
    etaVal.textContent = etaText;
    etaEl.title = "Speed: " + formatMbps(p.speed_bytes || 0);

    if(p.status==="finished"){ window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ job=null; return; }
    setTimeout(poll,800);
  }catch(e){msg.textContent="Network error.";etaVal.textContent="--";job=null;}
}
</script>
</body>
</html>
"""

# ---------- Backend ----------
JOBS = {}

class Job:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.tmp = tempfile.mkdtemp(prefix="mvd_")
        self.percent = 0
        self.status = "queued"
        self.file = None
        self.error = None
        self.speed_bytes = 0.0
        self.created_at = time.time()
        self.downloaded_at = None
        # fields to support ETA calculation
        self.total_bytes = 0
        self.downloaded_bytes = 0
        JOBS[self.id] = self

YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    """
    Return a mapping key -> yt-dlp format selector.
    Audio selectors prefer m4a when ffmpeg is present for stable conversion to mp3.
    """
    if HAS_FFMPEG:
        video_map = {
            "mp4_144":  "bestvideo[height<=144]+bestaudio/best[height<=144]",
            "mp4_240":  "bestvideo[height<=240]+bestaudio/best[height<=240]",
            "mp4_360":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
            "mp4_480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "mp4_720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "mp4_1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        }

        # Prefer m4a (aac) where available; fallback to best audio.
        audio_map = {
            "audio_mp3_128": "bestaudio[ext=m4a]/bestaudio",
            "audio_mp3_192": "bestaudio[ext=m4a]/bestaudio",
            "audio_mp3_320": "bestaudio[ext=m4a]/bestaudio",
            "audio_best": "bestaudio/best"
        }

        video_map.update(audio_map)
        return video_map

    else:
        # If ffmpeg missing, we still try to download best available streams.
        return {
            "mp4_144":  "best[height<=144][ext=mp4]/best[height<=144]",
            "mp4_240":  "best[height<=240][ext=mp4]/best[height<=240]",
            "mp4_360":  "best[height<=360][ext=mp4]/best[height<=360]",
            "mp4_480":  "best[height<=480][ext=mp4]/best[height<=480]",
            "mp4_720":  "best[height<=720][ext=mp4]/best[height<=720]",
            "mp4_1080": "best[height<=1080][ext=mp4]/best[height<=1080]",
            "audio_mp3_128": "bestaudio",
            "audio_mp3_192": "bestaudio",
            "audio_mp3_320": "bestaudio",
            "audio_best": "bestaudio",
        }

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status = "error"
            job.error = "Invalid URL"
            return

        fmt_map = format_map_for_env()
        requested_fmt = fmt_map.get(fmt_key)
        if requested_fmt is None:
            job.status = "error"
            job.error = "Format not supported"
            return

        def hook(d):
            try:
                st = d.get("status")
                if st == "downloading":
                    job.status = "downloading"
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0) or 0
                    job.total_bytes = int(total or 0)
                    job.downloaded_bytes = int(downloaded or 0)
                    job.speed_bytes = d.get("speed") or 0
                    if job.total_bytes:
                        job.percent = int((job.downloaded_bytes * 100) / job.total_bytes)
                elif st == "finished":
                    # note: 'finished' hook appears for each fragment; final output handled after extract_info
                    job.percent = 100
                    job.status = "downloaded"
                elif st == "error":
                    job.status = "error"
                    job.error = d.get("msg") or "Download hook error"
            except Exception:
                pass

        # Prepare base filename and sanitize
        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        safe = re.sub(r'[\\/*?:"<>|]', "_", base).strip()
        if not safe:
            safe = "%(title)s"
        out = os.path.join(job.tmp, safe + ".%(ext)s")

        # Base options for yt-dlp
        base_opts = {
            "format": requested_fmt,
            "outtmpl": out,
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            "cookiefile": "cookies.txt",
            # writeinfojson useful for debugging; disabled in quiet mode but we keep it off by default
        }

        # Helper to run yt-dlp once with given opts, returns (ok, exception)
        def try_run(opts):
            try:
                with YoutubeDL(opts) as y:
                    y.extract_info(url, download=True)
                return True, None
            except Exception as e:
                return False, e

        is_audio_mp3 = fmt_key.startswith("audio_mp3_")
        tried_attempts = []

        # Build candidate selectors
        candidates = []
        candidates.append(requested_fmt)
        candidates.append(requested_fmt + "/best")
        if is_audio_mp3:
            candidates.extend(["bestaudio[ext=m4a]/bestaudio", "bestaudio", "bestaudio/best", "best"])
        else:
            candidates.append("best")

        # Unique preserve order
        seen = set(); filtered = []
        for c in candidates:
            if c and c not in seen:
                filtered.append(c); seen.add(c)
        candidates = filtered

        success = False
        last_exc = None

        for fmt_try in candidates:
            opts = dict(base_opts)
            opts["format"] = fmt_try

            # Setup ffmpeg-based postprocessor only when user asked for mp3 conversion and ffmpeg exists
            if is_audio_mp3 and HAS_FFMPEG:
                kbps = fmt_key.split("_")[-1]  # e.g. '192'
                # Prefer extracting audio to mp3 using ffmpeg
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": kbps
                }]
                opts["ffmpeg_location"] = ffmpeg_path()
            else:
                opts.pop("postprocessors", None)

            # For video merges (video+audio), configure ffmpeg merge if available
            if HAS_FFMPEG and fmt_key.startswith("mp4_"):
                opts["ffmpeg_location"] = ffmpeg_path()
                opts["merge_output_format"] = "mp4"

            tried_attempts.append(fmt_try)
            ok, exc = try_run(opts)
            if ok:
                success = True
                break
            else:
                last_exc = exc

        # Find largest output file in tmp (best guess)
        files = glob.glob(os.path.join(job.tmp, "*"))
        files = [f for f in files if os.path.isfile(f)]
        job.file = None
        if files:
            # Prefer mp3 if conversion was requested and produced one
            if is_audio_mp3:
                mp3s = [f for f in files if f.lower().endswith(".mp3")]
                if mp3s:
                    job.file = max(mp3s, key=os.path.getsize)
                else:
                    # fallback to largest (m4a/webm/whatever)
                    job.file = max(files, key=os.path.getsize)
            else:
                job.file = max(files, key=os.path.getsize)

        if success and job.file:
            job.status = "finished"
            job.downloaded_at = time.time()
            job.percent = 100
            # If user requested mp3 but ffmpeg missing and result isn't mp3, add a hint
            if is_audio_mp3 and not HAS_FFMPEG and not job.file.lower().endswith(".mp3"):
                job.error = ("Downloaded audio file is in original format (ffmpeg not found on server). "
                             "To auto-convert to MP3, install ffmpeg.")
            return
        else:
            # Construct helpful error message
            if last_exc:
                msg = str(last_exc)
                low = msg.lower()
                if "requested format is not available" in msg or "format not available" in low:
                    hint = ("Requested format not available on that video. "
                            "Tried: " + ", ".join(tried_attempts) + ". "
                            "If you need MP3 conversion, ensure ffmpeg is installed on the server.")
                    job.error = hint
                else:
                    job.error = (msg[:400] + " — tried: " + ", ".join(tried_attempts))
            else:
                job.error = "No output file produced; tried: " + ", ".join(tried_attempts)
            job.status = "error"
            return

    except Exception as e:
        job.status = "error"
        job.error = str(e)[:400]

@app.route("/")
def index():
    return render_template_string(HTML)

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(target=run_download, args=(job, d.get("url", ""), d.get("format_choice", "mp4_1080"), d.get("filename")), daemon=True).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url", "")
    try:
        with YoutubeDL({"skip_download": True, "quiet": True, "noplaylist": True, "cookiefile": "cookies.txt"}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title", "")
        channel = info.get("uploader") or info.get("channel", "")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title": title, "thumbnail": thumb, "channel": channel, "duration_str": f"{dur//60}:{dur%60:02d}"})
    except Exception as e:
        return jsonify({"error": "Preview failed", "detail": str(e)[:400]}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    speed_b = getattr(j, "speed_bytes", 0) or 0
    eta_seconds = None
    downloaded = getattr(j, "downloaded_bytes", 0) or 0
    total = getattr(j, "total_bytes", 0) or 0
    if total > 0 and downloaded > 0 and speed_b and speed_b > 0 and downloaded < total:
        try:
            eta_seconds = int((total - downloaded) / speed_b)
        except Exception:
            eta_seconds = None

    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": speed_b,
        "total_bytes": total,
        "downloaded_bytes": downloaded,
        "eta_seconds": eta_seconds
    })

@app.get("/fetch/<id>")
def fetch_file(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error": "File not ready"}), 404

    filename_on_disk = os.path.basename(j.file)
    try:
        mimetype, _ = mimetypes.guess_type(j.file)
        return send_file(j.file, as_attachment=True, download_name=filename_on_disk, mimetype=mimetype or "application/octet-stream")
    except Exception as e:
        return jsonify({"error": "Failed to send file", "detail": str(e)[:300]}), 500

# Optional cleanup endpoint (safe to call manually)
@app.post("/cleanup/<id>")
def cleanup(id):
    j = JOBS.pop(id, None)
    if not j:
        return jsonify({"status": "not_found"}), 404
    try:
        if os.path.exists(j.tmp):
            shutil.rmtree(j.tmp)
    except Exception:
        pass
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
