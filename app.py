# app.py
# -*- coding: utf-8 -*-
import os
import time
import tempfile
import shutil
import glob
import threading
import uuid
import re
import math
from flask import Flask, request, jsonify, render_template_string, abort, send_file
from shutil import which
from yt_dlp import YoutubeDL

# ---------- CONFIG ----------
DEBUG_LOG = os.environ.get("DEBUG_LOG", "") not in ("", "0", "false", "False")
PORT = int(os.environ.get("PORT", 5000))
# Filename prefix (default)
APP_PREFIX = os.environ.get("APP_PREFIX", "Hyper_Downloader")
# How long to keep job objects before cleanup (seconds)
JOB_TTL_SECONDS = 60 * 60
# How long to keep downloaded file available after user fetch (seconds)
DOWNLOAD_KEEP_SECONDS = 60
CLEANUP_INTERVAL = 60 * 10

app = Flask(__name__)

# Save cookies if present (from environment)
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    try:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(cookies_data)
    except Exception:
        pass

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg" or "/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (full UI) ----------
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
.logo { animation: bgPulse 8s ease-in-out infinite; }
@keyframes bgPulse {
  0% { filter: hue-rotate(0deg) saturate(100%); }
  50% { filter: hue-rotate(8deg) saturate(110%); }
  100% { filter: hue-rotate(0deg) saturate(100%); }
}
.brand-title span{
  background:var(--accent);
  -webkit-background-clip:text;
  color:transparent;
}

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

.grid{display:grid;gap:12px;margin:10px 0px;}
@media(min-width:700px){.grid{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end;}}
.full{grid-column:1/-1;}

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
.bar::after{
  content:"";
  position:absolute;inset:0;
  background:linear-gradient(90deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02), rgba(255,255,255,0.06));
  transform:translateX(-40%);opacity:0.6;filter:blur(6px);
  animation: sheen 2.4s linear infinite;
}
@keyframes sheen{100%{transform:translateX(120%)}}
.status-row{
  display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:12px;
}
.status-left{color:var(--muted);font-size:13px;display:flex;align-items:center;gap:8px;}
.eta-pill{
  display:inline-flex;align-items:center;gap:10px;padding:8px 12px;border-radius:999px;
  background:var(--pill-bg);border:1px solid var(--pill-border);font-weight:700;font-size:13px;color:#fff;
  min-width:90px;justify-content:center;
  box-shadow:0 6px 18px rgba(6,182,212,0.06);
}
.eta-pill .label{opacity:0.85;color:var(--muted);font-weight:600;font-size:12px;margin-right:6px}
.eta-pill .value{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Roboto Mono,monospace;font-weight:800}

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
  <h2>📥 Download from YouTube</h2>
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
          <option value="video">Video (merge bestvideo + bestaudio)</option>
          <option value="audio">Audio only (MP3)</option>
        </select>
      </div>

      <!-- Video quality selector -->
      <div>
        <label>Video quality</label>
        <select id="video_res">
          <option value="144">144p</option>
          <option value="240">240p</option>
          <option value="360">360p</option>
          <option value="480">480p</option>
          <option value="720">720p</option>
          <option value="1080" selected>1080p</option>
        </select>
      </div>

      <!-- Audio bitrate selector -->
      <div>
        <label>Audio bitrate (kbps)</label>
        <select id="audio_bitrate">
          <option value="128">128 kbps</option>
          <option value="160">160 kbps</option>
          <option value="192" selected>192 kbps</option>
          <option value="256">256 kbps</option>
          <option value="320">320 kbps</option>
        </select>
      </div>

      <div><label>Filename</label><input id="name" placeholder="My video"></div>
      <div class="full"><button id="goBtn" type="submit">⚡ Start Download</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div><div id="pct" class="pct">0%</div></div>

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
  const url=urlIn.value.trim(),
        fmt=document.getElementById("format").value,
        name=document.getElementById("name").value.trim(),
        video_res=document.getElementById("video_res").value,
        audio_bitrate=document.getElementById("audio_bitrate").value;
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name,video_res,audio_bitrate})});
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
    else msg.textContent = p.status==="downloaded" ? "✅ Download complete (fetching file)..." : p.status || "Downloading…";

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

# ---------- Backend logic ----------
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
        self.total_bytes = 0
        self.downloaded_bytes = 0
        JOBS[self.id] = self

URL_RE = re.compile(r"^https?://", re.I)

# characters to remove/replace for safe filenames on most OSes
_FILENAME_SANITIZE_RE = re.compile(r'[\\/:*?"<>|]')

def sanitize_filename(name: str, max_len: int = 240) -> str:
    """Sanitize filename by replacing problematic chars and trimming length."""
    if not name:
        return "file"
    # strip leading/trailing whitespace
    s = name.strip()
    # replace forbidden characters with underscore
    s = _FILENAME_SANITIZE_RE.sub("_", s)
    # collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    # trim to max_len (preserve extension later)
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s

def _build_video_format(video_res):
    """Build yt-dlp format expression with fallbacks."""
    if not video_res:
        return "bestvideo[vcodec!=none]+bestaudio/best"

    try:
        res = int(video_res)
    except Exception:
        res = None

    if not res:
        return "bestvideo[vcodec!=none]+bestaudio/best"

    parts = []
    if res <= 1080:
        parts.append(f"bestvideo[height<={res}][vcodec!=none][ext=mp4]+bestaudio/best[height<={res}]")
    parts.append(f"bestvideo[height<={res}][vcodec!=none]+bestaudio")
    parts.append("bestvideo+bestaudio/best")
    return "/".join(parts)

def run_download(job, url, fmt_key, filename, video_res=None, audio_bitrate=None):
    try:
        if not URL_RE.match(url):
            job.status = "error"
            job.error = "Invalid URL"
            return

        # normalize inputs
        try:
            video_res = int(video_res) if video_res else None
        except Exception:
            video_res = None
        try:
            audio_bitrate = int(audio_bitrate) if audio_bitrate else None
        except Exception:
            audio_bitrate = None

        # choose format
        if fmt_key == "audio":
            fmt = "bestaudio/best"
        else:
            fmt = _build_video_format(video_res)

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
                    job.percent = 100
            except Exception:
                pass

        # Decide base filename: user provided filename else yt-dlp template
        base_template = (filename.strip() if filename else "%(title)s").rstrip(".")
        # If yt-dlp template used, it will be replaced when extract_info runs; but we still sanitize the given name.
        # We will include APP_PREFIX + '__' + sanitized base as output template.
        # sanitize the provided filename (if it contains template tokens, leave them so yt-dlp can substitute)
        if "%(" in base_template and ")" in base_template:
            # user used template tokens, keep as-is but ensure no unsafe literal chars outside tokens
            # replace forbidden chars except inside %(...) tokens
            def _replace_outside_tokens(s):
                out = []
                i = 0
                while i < len(s):
                    if s[i] == '%' and i+1 < len(s) and s[i+1] == '(':
                        # copy until closing ')'
                        j = i+2
                        while j < len(s) and s[j] != ')':
                            j += 1
                        # include token as-is (if no closing, just copy rest)
                        if j < len(s):
                            out.append(s[i:j+1])
                            i = j+1
                            continue
                        else:
                            out.append(s[i:])
                            break
                    else:
                        out.append(s[i])
                        i += 1
                joined = "".join(out)
                # now sanitize forbidden chars in the joined string (this will also sanitize inside tokens if any remained - but tokens are preserved above)
                return _FILENAME_SANITIZE_RE.sub("_", joined)
            safe_base = _replace_outside_tokens(base_template)
        else:
            safe_base = sanitize_filename(base_template)

        # Construct final outtmpl: prefix + '__' + safe_base + .%(ext)s
        prefix = APP_PREFIX.strip() or "Hyper_Downloader"
        # sanitize prefix too (avoid accidental bad chars)
        prefix_safe = _FILENAME_SANITIZE_RE.sub("_", prefix)
        outtmpl_base = f"{prefix_safe}__{safe_base}"
        outtmpl = os.path.join(job.tmp, outtmpl_base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "progress_hooks": [hook],
            "quiet": not DEBUG_LOG,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            "cookiefile": "cookies.txt",
        }

        if DEBUG_LOG:
            opts["verbose"] = True

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key != "audio":
                try:
                    if video_res and int(video_res) <= 1080:
                        opts["merge_output_format"] = "mp4"
                    else:
                        opts["merge_output_format"] = "mp4"
                except Exception:
                    opts["merge_output_format"] = "mp4"
            else:
                pp = {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
                pp["preferredquality"] = str(audio_bitrate) if audio_bitrate else "192"
                opts["postprocessors"] = [pp]

        # Run yt-dlp
        try:
            with YoutubeDL(opts) as y:
                y.extract_info(url, download=True)
        except Exception as e:
            job.status = "error"
            job.error = f"yt-dlp failed: {str(e)[:400]}"
            return

        files = glob.glob(os.path.join(job.tmp, "*"))
        job.file = max(files, key=os.path.getsize) if files else None
        if job.file:
            job.status = "finished"
        else:
            job.status = "error"
            job.error = "No output file produced"
    except Exception as e:
        job.status = "error"
        job.error = str(e)[:400]

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(
        target=run_download,
        args=(
            job,
            d.get("url", ""),
            d.get("format_choice", "video"),
            d.get("filename"),
            d.get("video_res"),
            d.get("audio_bitrate"),
        ),
        daemon=True,
    ).start()
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
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "eta_seconds": eta_seconds
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error": "File not ready"}), 400
    j.downloaded_at = time.time()
    j.status = "downloaded"
    return send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG, "debug": DEBUG_LOG, "prefix": APP_PREFIX})

def cleanup_worker():
    while True:
        try:
            now = time.time()
            remove = []
            for jid, job in list(JOBS.items()):
                if job.status in ("finished", "error") and (now - job.created_at > JOB_TTL_SECONDS):
                    remove.append(jid)
                if job.status == "downloaded" and job.downloaded_at and (now - job.downloaded_at > DOWNLOAD_KEEP_SECONDS):
                    remove.append(jid)
            for rid in remove:
                j = JOBS.pop(rid, None)
                if j:
                    try:
                        shutil.rmtree(j.tmp, ignore_errors=True)
                    except Exception:
                        pass
        except Exception as e:
            print("[cleanup]", e)
        time.sleep(CLEANUP_INTERVAL)

threading.Thread(target=cleanup_worker, daemon=True).start()

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    print("Starting app on port", PORT, "ffmpeg:", HAS_FFMPEG, "DEBUG_LOG:", DEBUG_LOG, "PREFIX:", APP_PREFIX)
    app.run(host="0.0.0.0", port=PORT)
