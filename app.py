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

# Save cookies if present (from environment)
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (kept UI, same as before with format options) ----------
HTML = r"""
<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /><title>Hyper Downloader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
/* (Same styling as before - trimmed for brevity in this embed) */
:root{--bg:#050b16;--grad1:#2563eb;--grad2:#06b6d4;--accent:linear-gradient(90deg,var(--grad1),var(--grad2));--radius:16px;}
body{margin:0;background:var(--bg);color:#e8f0ff;font-family:'Inter',sans-serif;padding:16px;}
.wrap{max-width:960px;margin:auto;}
.card{background:rgba(255,255,255,0.02);padding:20px;border-radius:14px;}
input,select,button{width:100%;padding:10px;border-radius:10px;background:#0d1c33;color:#e8f0ff;border:1px solid rgba(255,255,255,0.06);}
.button{background:var(--accent);border:none;color:#fff;padding:12px;border-radius:12px;}
.progress{height:14px;border-radius:999px;background:rgba(255,255,255,0.03);overflow:hidden;margin-top:12px}
.bar{width:0%;height:100%;background:var(--accent);transition:width .25s}
.pct{position:relative;top:-14px;text-align:center;font-weight:700}
.status-row{display:flex;justify-content:space-between;margin-top:8px;color:#a3b5d2}
.thumb{width:120px;height:68px;object-fit:cover}
.preview{display:none;margin-top:10px}
</style>
</head>
<body>
<div class="wrap">
<main class="card">
  <h2>⬇️ Download from YouTube</h2>
  <p class="small">Paste link, choose format (video resolutions / mp3 bitrate), start.</p>

  <div id="preview" class="preview">
    <img id="thumb" class="thumb" alt=""><div id="pTitle"></div><div id="pSub"></div>
  </div>

  <form id="frm">
    <div style="display:grid;gap:10px">
      <div><label>Video URL</label><input id="url" placeholder="https://youtube.com/watch?v=..." required></div>
      <div><label>Format</label>
        <select id="format">
          <!-- Video -->
          <option value="mp4_144">144p MP4</option>
          <option value="mp4_240">240p MP4</option>
          <option value="mp4_360">360p MP4</option>
          <option value="mp4_480">480p MP4</option>
          <option value="mp4_720">720p MP4</option>
          <option value="mp4_1080">1080p MP4</option>

          <!-- Audio -->
          <option value="mp3_128">MP3 128kbps</option>
          <option value="mp3_192">MP3 192kbps</option>
          <option value="mp3_256">MP3 256kbps</option>
          <option value="mp3_320">MP3 320kbps</option>
        </select>
      </div>
      <div><label>Filename (optional)</label><input id="name" placeholder="My video"></div>
      <div><button class="button" id="goBtn" type="submit">⚡ Start Download</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div></div><div class="pct" id="pct">0%</div>
  <div class="status-row"><div id="msg">—</div><div id="eta">ETA: --</div></div>
</main>
</div>

<script>
let job=null;
const bar=document.getElementById("bar"), pct=document.getElementById("pct"), msg=document.getElementById("msg"), eta=document.getElementById("eta");
document.getElementById("frm").addEventListener("submit", async (e)=> {
  e.preventDefault();
  msg.textContent="Starting…";
  const url=document.getElementById("url").value.trim();
  const fmt=document.getElementById("format").value;
  const name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({url, format_choice: fmt, filename: name})});
    const j=await r.json();
    if(!r.ok) throw new Error(j.error||"Failed to start");
    job=j.job_id; poll();
  }catch(err){msg.textContent="❌ "+err.message;}
});

async function poll(){
  if(!job) return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){msg.textContent="Job expired"; job=null; return;}
    const p=await r.json();
    const pctv = Math.max(0, Math.min(100, p.percent||0));
    bar.style.width = pctv + "%";
    pct.innerText = pctv + "%";
    if(p.status==="finished") msg.textContent="✅ Ready";
    else if(p.status==="error") msg.textContent="❌ "+(p.error||"Error");
    else msg.textContent = p.status || "Working";
    eta.innerText = "ETA: " + (p.eta_seconds!=null ? formatSeconds(p.eta_seconds) : "--");
    if(p.status==="finished"){ window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ job=null; return; }
    setTimeout(poll,800);
  }catch(e){msg.textContent="Network error"; job=null;}
}

function formatSeconds(s){ if(!s||s<0) return "--"; s=Math.round(s); const h=Math.floor(s/3600); const m=Math.floor((s%3600)/60); const sec=s%60; if(h>0) return h+"h "+m+"m"; if(m>0) return m+"m "+sec+"s"; return sec+"s"; }
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
    """
    Keep selectors that pick bestvideo + bestaudio for video,
    and bestaudio for audio keys. We avoid forcing container changes
    so yt-dlp/ffmpeg will remux using copy (no re-encode) when possible.
    """
    return {
        # video
        "mp4_144":  "bestvideo[height<=144]+bestaudio/best",
        "mp4_240":  "bestvideo[height<=240]+bestaudio/best",
        "mp4_360":  "bestvideo[height<=360]+bestaudio/best",
        "mp4_480":  "bestvideo[height<=480]+bestaudio/best",
        "mp4_720":  "bestvideo[height<=720]+bestaudio/best",
        "mp4_1080": "bestvideo[height<=1080]+bestaudio/best",
        # audio (we will extract to mp3 with requested bitrate)
        "mp3_128": "bestaudio/best",
        "mp3_192": "bestaudio/best",
        "mp3_256": "bestaudio/best",
        "mp3_320": "bestaudio/best",
    }

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status = "error"
            job.error = "Invalid URL"
            return

        fmt = format_map_for_env().get(fmt_key)
        if not fmt:
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
                    job.percent = 100
            except Exception:
                pass

        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        safe_base = f"{job.id}__{base}"
        out = os.path.join(job.tmp, safe_base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": out,
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            "cookiefile": "cookies.txt",
            # don’t force remux/container changes here; let yt-dlp choose best and remux with copy
            "prefer_insecure": False,
        }

        # If ffmpeg available, set its location so yt-dlp can remux (copy) without re-encoding.
        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            # For audio->mp3 conversions we will ask FFmpegExtractAudio with preferredquality (kbps)
            if fmt_key.startswith("mp3_"):
                # preferredquality expects kbps string (yt-dlp understands string numbers)
                bitrate_value = fmt_key.split("_", 1)[1]
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate_value
                }]
                # Ensure we keep the original file too (yt-dlp may remove intermediate) if you want:
                # opts["keepvideo"] = True
            else:
                # Video jobs: do not set "merge_output_format" forcefully.
                # yt-dlp will remux/merge with ffmpeg using stream copy by default when possible,
                # preserving original codecs and thus original size (no re-encode).
                pass
        else:
            # No ffmpeg: for video, try to pick single-file formats (mp4/webm) via yt-dlp format selector fallback.
            # Audio bitrate conversion to mp3 won't be possible without ffmpeg; user will get source audio container.
            if fmt_key.startswith("mp3_"):
                # inform user via job.error later if ffmpeg missing and mp3 requested
                pass

        # Run extraction/download
        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        # find largest file in tmp
        files = glob.glob(os.path.join(job.tmp, "*"))
        job.file = max(files, key=os.path.getsize) if files else None
        job.status = "finished" if job.file else "error"
        if not job.file and job.status == "error":
            job.error = job.error or "No output file produced"
    except Exception as e:
        job.status = "error"
        # trim long errors for JSON
        job.error = str(e)[:400]

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(target=run_download, args=(job, d.get("url", ""), d.get("format_choice", "mp4_720"), d.get("filename")), daemon=True).start()
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
    return jsonify({"ffmpeg": HAS_FFMPEG, "ffmpeg_path": ffmpeg_path() if HAS_FFMPEG else None})

# Cleanup
CLEANUP_INTERVAL = 60 * 10
JOB_TTL_SECONDS = 60 * 60
DOWNLOAD_KEEP_SECONDS = 60

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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
