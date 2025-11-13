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
from flask import Flask, request, jsonify, render_template_string, abort, send_file
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Save cookies if present
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (UI) ----------
HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hyper Downloader</title>
<style>
:root{
  --bg:#050b16; --card:#0a162b; --muted:#a3b5d2;
  --grad1:#2563eb; --grad2:#06b6d4; --accent:linear-gradient(90deg,var(--grad1),var(--grad2));
  --radius:14px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:#e8f0ff;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans",sans-serif;padding:18px}
.wrap{max-width:920px;margin:0 auto}
.card{background:rgba(255,255,255,0.02);border-radius:var(--radius);padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.5)}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.logo{width:52px;height:52px;border-radius:12px;background:var(--accent);display:grid;place-items:center;font-weight:800}
.form-row{display:grid;gap:12px}
@media(min-width:720px){.form-row{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end}}
input,select,button{width:100%;padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,0.06);background:#081a2b;color:var(--muted)}
button{background:var(--grad1);background-image:var(--accent);color:#fff;font-weight:700;border:none;cursor:pointer}
.progress{height:14px;background:rgba(255,255,255,0.03);border-radius:999px;overflow:hidden;margin-top:12px;position:relative}
.bar{height:100%;width:0;background:linear-gradient(90deg,var(--grad1),var(--grad2));transition:width .25s}
.pct{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-weight:800;color:#fff}
.info-row{display:flex;justify-content:space-between;align-items:center;margin-top:10px;color:var(--muted);font-size:13px}
.bad{color:#fb7185}
.bad small{display:block;color:var(--muted)}
.preview{display:none;background:rgba(255,255,255,0.02);padding:10px;border-radius:10px;margin-top:12px}
.preview img{width:120px;height:68px;object-fit:cover;border-radius:8px}
.badge{background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:8px}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div style="display:flex;gap:12px;align-items:center">
      <div class="logo">HD</div>
      <div>
        <div style="font-weight:800;font-size:20px">Hyper <span style="background:var(--accent);-webkit-background-clip:text;color:transparent">Downloader</span></div>
      </div>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <div class="badge" id="ffbadge">Checking...</div>
    </div>
  </div>

  <div class="card">
    <h2>⬇️ Download from YouTube</h2>
    <p style="color:var(--muted);margin-top:6px">Paste link, choose format and download. Live percent, speed and ETA shown below.</p>

    <div id="preview" class="preview"><div style="display:flex;gap:12px;align-items:center"><img id="thumb" alt=""><div><div id="pTitle" style="font-weight:700"></div><div id="pSub" style="color:var(--muted)"></div></div></div></div>

    <form id="frm" style="margin-top:12px">
      <div class="form-row">
        <div>
          <label style="color:var(--muted);font-size:13px">Video URL</label>
          <input id="url" placeholder="https://youtube.com/watch?v=..." required>
        </div>
        <div>
          <label style="color:var(--muted);font-size:13px">Format</label>
          <select id="format">
            <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
            <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
            <option value="mp4_best">4K MP4</option>
            <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
          </select>
        </div>
        <div>
          <label style="color:var(--muted);font-size:13px">Filename (optional)</label>
          <input id="name" placeholder="My video">
        </div>
        <div><button id="goBtn" type="submit">⚡ Start Download</button></div>
      </div>
    </form>

    <div class="progress" aria-hidden="false"><div id="bar" class="bar"></div><div id="pct" class="pct">0%</div></div>

    <div class="info-row">
      <div id="msg" style="min-height:18px;color:var(--muted)"></div>
      <div style="display:flex;gap:12px;align-items:center">
        <div id="speed">0.0 Mbps</div>
        <div id="eta" style="background:rgba(255,255,255,0.03);padding:6px 8px;border-radius:8px">ETA: --</div>
      </div>
    </div>
  </div>

  <p style="color:var(--muted);font-size:12px;margin-top:14px">© 2025 Hyper Downloader — Auto cleanup enabled</p>
</div>

<script>
let job=null,HAS_FFMPEG=false;
const bar=document.getElementById("bar"),pct=document.getElementById("pct"),msg=document.getElementById("msg");
const speedEl=document.getElementById("speed"),etaEl=document.getElementById("eta"),ffbadge=document.getElementById("ffbadge");
const urlIn=document.getElementById("url"),preview=document.getElementById("preview"),thumb=document.getElementById("thumb"),pTitle=document.getElementById("pTitle"),pSub=document.getElementById("pSub");

fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG=!!j.ffmpeg;
  ffbadge.textContent = HAS_FFMPEG ? "FFmpeg: available" : "FFmpeg: not found";
  // disable options that need ffmpeg
  [...document.querySelectorAll("option[data-need-ffmpeg]")].forEach(o=>{
    if(o.dataset.needFfmpeg==="1" && !HAS_FFMPEG) o.disabled = true;
  });
}).catch(()=>{ffbadge.textContent="FFmpeg: unknown"});

function toMbps(bytesPerSec){
  if(!bytesPerSec) return "0.0 Mbps";
  const mbps = (bytesPerSec * 8) / (1024*1024); // bits -> megabits
  // one digit before decimal? show with one decimal place (e.g. 6.1 Mbps)
  return mbps < 1 ? mbps.toFixed(2)+" Mbps" : mbps.toFixed(1)+" Mbps";
}
function formatETA(seconds){
  if(!isFinite(seconds) || seconds<=0) return "--";
  seconds = Math.round(seconds);
  const h = Math.floor(seconds/3600), m = Math.floor((seconds%3600)/60), s = seconds%60;
  if(h>0) return `${h}h ${m}m ${s}s`;
  if(m>0) return `${m}m ${s}s`;
  return `${s}s`;
}

async function fetchInfo(url){
  try{
    const r = await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j = await r.json();
    if(!r.ok || j.error){ preview.style.display="none"; return; }
    pTitle.textContent = j.title||"";
    pSub.textContent = [j.channel,j.duration_str].filter(Boolean).join(" • ");
    if(j.thumbnail){ thumb.src = j.thumbnail; thumb.alt = j.title; }
    preview.style.display = "block";
  }catch(e){ preview.style.display="none"; }
}

urlIn.addEventListener("input",()=>{
  clearTimeout(window._deb);
  const u = urlIn.value.trim();
  if(!/^https?:\/\//i.test(u)){ preview.style.display="none"; return; }
  window._deb = setTimeout(()=> fetchInfo(u), 500);
});

document.getElementById("frm").addEventListener("submit", async (e)=>{
  e.preventDefault();
  msg.textContent = "⏳ Starting...";
  etaEl.textContent = "ETA: --";
  speedEl.textContent = "0.0 Mbps";
  const url = urlIn.value.trim();
  const fmt = document.getElementById("format").value;
  const name = document.getElementById("name").value.trim();
  try{
    const r = await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j = await r.json();
    if(!r.ok) throw new Error(j.error||"Failed to start");
    job = j.job_id;
    poll();
  }catch(err){
    msg.textContent = "❌ " + err.message;
    msg.className = "bad";
  }
});

async function poll(){
  if(!job) return;
  try{
    const r = await fetch("/progress/"+job);
    if(r.status===404){ msg.textContent="Job expired."; job=null; return; }
    const p = await r.json();
    const pctv = Math.max(0, Math.min(100, p.percent || 0));
    bar.style.width = pctv + "%";
    pct.textContent = pctv + "%";

    // speed -> convert to Mbps nicely
    speedEl.textContent = toMbps(p.speed_bytes || 0);

    // ETA calculation (frontend) using downloaded_bytes, total_bytes, speed
    let etaText = "--";
    const downloaded = p.downloaded_bytes || 0;
    const total = p.total_bytes || 0;
    const speed = p.speed_bytes || 0;
    if(total > 0 && downloaded > 0 && speed > 0 && downloaded < total){
      const remain = (total - downloaded) / speed;
      etaText = formatETA(remain);
    } else {
      etaText = "--";
    }
    etaEl.textContent = "ETA: " + etaText;

    if(p.status === "finished"){
      msg.textContent = "✅ Preparing file…";
      // trigger fetch (user will download)
      window.location = "/fetch/" + job;
      job = null;
      return;
    }
    if(p.status === "error"){
      msg.textContent = "❌ " + (p.error || "Download failed");
      job = null;
      return;
    }
    // keep polling
    setTimeout(poll, 800);
  }catch(e){
    msg.textContent = "Network error.";
    job = null;
  }
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
        self.total_bytes = 0
        self.downloaded_bytes = 0
        JOBS[self.id] = self

YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    # best behavior: prefer separate video+audio when ffmpeg exists (to merge properly and give good size differences)
    if HAS_FFMPEG:
        return {
            "mp4_720": "bestvideo[height<=720]+bestaudio/best",
            "mp4_1080":"bestvideo[height<=1080]+bestaudio/best",
            "mp4_best":"bestvideo+bestaudio/best",
            "audio_mp3":"bestaudio/best"
        }
    else:
        # without ffmpeg, force single-file mp4 fallbacks (may reduce quality choices)
        return {
            "mp4_720": "best[ext=mp4][height<=720]/best[ext=mp4]",
            "mp4_1080":"best[ext=mp4][height<=1080]/best[ext=mp4]",
            "mp4_best":"best[ext=mp4]/best",
            "audio_mp3": None
        }

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status = "error"
            job.error = "Invalid URL"
            return

        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status = "error"
            job.error = "Format not supported on this server"
            return

        def hook(d):
            try:
                st = d.get("status")
                if st == "downloading":
                    job.status = "downloading"
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0) or 0
                    job.total_bytes = total
                    job.downloaded_bytes = downloaded
                    job.speed_bytes = d.get("speed") or 0
                    if total and total > 0:
                        job.percent = int((downloaded * 100) / total)
                elif st == "finished":
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
            "noplaylist": True,
            # increase retries/timeouts inside yt-dlp if you want:
            "retries": 3,
            "socket_timeout": 30
        }

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(job.tmp + "/*")
        job.file = max(files, key=os.path.getsize) if files else None
        job.status = "finished" if job.file else "error"
        if not job.file:
            job.error = "No output file produced"
    except Exception as e:
        job.status = "error"
        job.error = str(e)[:300]

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(target=run_download, args=(job, d.get("url",""), d.get("format_choice","mp4_best"), d.get("filename")), daemon=True).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url","")
    try:
        with YoutubeDL({"skip_download": True, "quiet": True, "noplaylist": True, "cookiefile": "cookies.txt"}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title","")
        channel = info.get("uploader") or info.get("channel","")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title": title, "thumbnail": thumb, "channel": channel, "duration_str": f"{dur//60}:{dur%60:02d}"})
    except Exception:
        return jsonify({"error":"Preview failed"}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": j.speed_bytes,
        "downloaded_bytes": getattr(j, "downloaded_bytes", 0),
        "total_bytes": getattr(j, "total_bytes", 0)
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error":"File not ready"}), 400
    j.downloaded_at = time.time()
    j.status = "downloaded"
    return send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

# Cleanup worker (auto-clean)
CLEANUP_INTERVAL = 60 * 10
JOB_TTL_SECONDS = 60 * 60      # remove finished/error jobs older than 1 hour
DOWNLOAD_KEEP_SECONDS = 60     # after user downloads file, remove from server after 60s

def cleanup_worker():
    while True:
        try:
            now = time.time()
            remove = []
            for jid, job in list(JOBS.items()):
                # jobs that finished or errored and are older than TTL
                if job.status in ("finished","error") and (now - job.created_at > JOB_TTL_SECONDS):
                    remove.append(jid)
                # jobs that user downloaded; keep short time then remove
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
