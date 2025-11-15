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
APP_PREFIX = os.environ.get("APP_PREFIX", "Hyper_Downloader")
JOB_TTL_SECONDS = 60 * 60
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

# ---------- HTML UI ----------
HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hyper Downloader</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#050b16;--muted:#a3b5d2;--grad1:#2563eb;--grad2:#06b6d4;--accent:linear-gradient(90deg,var(--grad1),var(--grad2));--radius:16px}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 800px at 30% 20%,rgba(37,99,235,.08),transparent),radial-gradient(1000px 600px at 80% 90%,rgba(6,182,212,.1),transparent),var(--bg);color:#e8f0ff;font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans",sans-serif;padding:20px}
.wrap{max-width:960px;margin:auto}header{display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.02);border-radius:var(--radius);padding:12px 18px} .logo{width:48px;height:48px;border-radius:12px;background:var(--accent);display:grid;place-items:center;font-weight:800} .card{background:rgba(255,255,255,0.02);border-radius:16px;padding:20px;margin-top:16px}label{display:block;margin-bottom:6px;color:var(--muted);font-size:13px}input,select,button{width:100%;padding:10px;border-radius:10px;border:1px solid rgba(255,255,255,0.06);background:#0d1c33;color:#e8f0ff}button{background:var(--accent);border:none;color:#fff;font-weight:700} .grid{display:grid;gap:12px} @media(min-width:700px){.grid{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end}} .progress{margin-top:14px;height:12px;border-radius:999px;background:rgba(255,255,255,0.04);overflow:hidden} .bar{width:0;height:100%;background:var(--accent);transition:width .2s} .pct{position:relative;text-align:center;margin-top:6px;color:var(--muted)}
.preview{display:none;margin-top:10px;padding:10px;background:rgba(255,255,255,0.02);border-radius:12px}
.status-row{display:flex;align-items:center;justify-content:space-between;margin-top:10px;color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
<header><div style="display:flex;gap:12px;align-items:center"><div class="logo">HD</div><div><strong>Hyper Downloader</strong></div></div></header>

<main class="card">
  <h3>Download</h3>
  <p style="color:var(--muted)">Paste URL, choose format & quality, start.</p>

  <div id="preview" class="preview">
    <div><img id="thumb" style="width:160px;height:90px;object-fit:cover;border-radius:8px" alt=""></div>
    <div id="pTitle" style="font-weight:700"></div>
    <div id="pSub" style="color:var(--muted)"></div>
  </div>

  <form id="frm">
    <div class="grid">
      <div><label>Video URL</label><input id="url" placeholder="https://youtube.com/watch?v=..." required></div>
      <div><label>Format</label>
        <select id="format">
          <option value="video">Video (video + audio)</option>
          <option value="audio" selected>Audio only (MP3)</option>
        </select>
      </div>

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

      <div>
        <label>Audio bitrate (kbps)</label>
        <select id="audio_bitrate">
          <option value="128">128</option>
          <option value="160">160</option>
          <option value="192" selected>192</option>
          <option value="256">256</option>
          <option value="320">320</option>
        </select>
      </div>

      <div><label>Filename</label><input id="name" placeholder="My audio name (optional)"></div>
      <div style="grid-column:1/-1"><button id="goBtn" type="submit">Start</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div></div>
  <div class="pct"><span id="pct">0%</span></div>

  <div class="status-row">
    <div id="msg">—</div>
    <div id="eta">ETA: --</div>
  </div>
</main>

</div>

<script>
let job=null;
const bar=document.getElementById("bar"), pctEl=document.getElementById("pct"), msg=document.getElementById("msg"), eta=document.getElementById("eta");
document.getElementById("frm").addEventListener("submit", async (e) => {
  e.preventDefault();
  msg.textContent = "Starting...";
  const url = document.getElementById("url").value.trim();
  const fmt = document.getElementById("format").value;
  const name = document.getElementById("name").value.trim();
  const video_res = document.getElementById("video_res").value;
  const audio_bitrate = document.getElementById("audio_bitrate").value;
  try {
    const r = await fetch("/start", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({url, format_choice: fmt, filename: name, video_res, audio_bitrate})});
    const j = await r.json();
    if(!r.ok) throw new Error(j.error || "Failed");
    job = j.job_id; poll();
  } catch(err) { msg.textContent = "Error: " + err.message; }
});

async function poll(){
  if(!job) return;
  try {
    const r = await fetch("/progress/" + job);
    if(r.status === 404){ msg.textContent = "Job expired"; job=null; return; }
    const p = await r.json();
    const pct = Math.max(0, Math.min(100, p.percent || 0));
    bar.style.width = pct + "%"; pctEl.textContent = pct + "%";
    msg.textContent = p.status || "Downloading...";
    eta.textContent = "ETA: " + (p.eta_seconds ? p.eta_seconds + "s" : "--");
    if(p.status === "finished"){ window.location = "/fetch/" + job; job = null; return; }
    if(p.status === "error"){ job = null; return; }
    setTimeout(poll, 800);
  } catch(e){ msg.textContent = "Network error"; job = null; }
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

URL_RE = re.compile(r"^https?://", re.I)
_FILENAME_SANITIZE_RE = re.compile(r'[\\/:*?"<>|]')

def sanitize_filename(name: str, max_len: int = 240) -> str:
    if not name:
        return "file"
    s = name.strip()
    s = _FILENAME_SANITIZE_RE.sub("_", s)
    s = re.sub(r'\s+', ' ', s)
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s

def _build_video_format(video_res):
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

        # normalize
        try:
            video_res = int(video_res) if video_res else None
        except Exception:
            video_res = None
        try:
            audio_bitrate = int(audio_bitrate) if audio_bitrate else None
        except Exception:
            audio_bitrate = None

        # strict audio format if requested
        if fmt_key == "audio":
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
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

        # filename handling & sanitize
        base_template = (filename.strip() if filename else "%(title)s").rstrip(".")
        if "%(" in base_template and ")" in base_template:
            def _replace_outside_tokens(s):
                out = []
                i = 0
                while i < len(s):
                    if s[i] == '%' and i+1 < len(s) and s[i+1] == '(':
                        j = i+2
                        while j < len(s) and s[j] != ')':
                            j += 1
                        if j < len(s):
                            out.append(s[i:j+1]); i = j+1; continue
                        else:
                            out.append(s[i:]); break
                    else:
                        out.append(s[i]); i += 1
                joined = "".join(out)
                return _FILENAME_SANITIZE_RE.sub("_", joined)
            safe_base = _replace_outside_tokens(base_template)
        else:
            safe_base = sanitize_filename(base_template)

        prefix_safe = _FILENAME_SANITIZE_RE.sub("_", APP_PREFIX.strip() or "Hyper_Downloader")
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

        # AUDIO: use postprocessor to extract mp3 if ffmpeg present; DO NOT set merge_output_format
        if fmt_key == "audio":
            if HAS_FFMPEG:
                pp = {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
                pp["preferredquality"] = str(audio_bitrate) if audio_bitrate else "192"
                opts["postprocessors"] = [pp]
            else:
                # no ffmpeg: will download original audio container (m4a/webm) — still audio-only and small
                pass
        else:
            # video path: set ffmpeg location and prefer mp4 merging for <=1080
            if HAS_FFMPEG:
                opts["ffmpeg_location"] = ffmpeg_path()
                try:
                    if video_res and int(video_res) <= 1080:
                        opts["merge_output_format"] = "mp4"
                    else:
                        opts["merge_output_format"] = "mp4"
                except Exception:
                    opts["merge_output_format"] = "mp4"

        # run yt-dlp
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
            d.get("format_choice", "audio"),
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
