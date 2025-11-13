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

# Minimal UI kept (your UI earlier). I won't change the visual layout.
HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Hyper Downloader</title>
<style>/* minimal inline CSS — original UI kept by you; shortened for brevity */body{background:#050b16;color:#e8f0ff;font-family:Inter,system-ui;padding:16px}input,select,button{padding:10px;border-radius:8px} .progress{height:12px;background:rgba(255,255,255,0.04);border-radius:999px;overflow:hidden} .bar{height:100%;width:0%;background:linear-gradient(90deg,#2563eb,#06b6d4)} .pct{position:relative;display:block;text-align:center;color:#fff;margin-top:6px} .status-row{display:flex;justify-content:space-between;margin-top:10px}</style>
</head><body>
<h1>Hyper Downloader</h1>
<form id="frm">
  <label>Video URL</label><input id="url" placeholder="https://youtube.com/watch?v=..." style="width:100%"/><br/>
  <label>Format</label>
  <select id="format" style="width:100%">
    <option value="mp4_720">720p MP4</option>
    <option value="mp4_1080">1080p MP4</option>
    <option value="mp4_1440">1440p (2K) MKV</option>
    <option value="mp4_2160">2160p (4K) MKV</option>
    <option value="audio_mp3">MP3 Only</option>
  </select><br/>
  <label>Filename (optional)</label><input id="name" placeholder="My video" style="width:100%"/><br/>
  <button id="goBtn" type="submit">Start Download</button>
</form>

<div class="progress" style="margin-top:12px"><div id="bar" class="bar"></div></div>
<div class="pct" id="pct">0%</div>
<div class="status-row">
  <div id="msg">—</div>
  <div id="eta">ETA: --</div>
</div>

<script>
let job=null;
const bar=document.getElementById("bar"), pct=document.getElementById("pct"), msg=document.getElementById("msg"), eta=document.getElementById("eta");
document.getElementById("frm").addEventListener("submit", async (e)=>{
  e.preventDefault();
  msg.textContent="Starting…"; eta.textContent="ETA: --";
  const url=document.getElementById("url").value.trim();
  const fmt=document.getElementById("format").value;
  const name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j=await r.json();
    if(!r.ok) throw new Error(j.error||"Failed");
    job=j.job_id; poll();
  }catch(err){ msg.textContent="Error: "+err.message; }
});

function formatSeconds(s){
  if(!s || isNaN(s)) return "--";
  s=Math.round(s); const h=Math.floor(s/3600), m=Math.floor((s%3600)/60), sec=s%60;
  if(h>0) return `${h}h ${m}m ${sec}s`; if(m>0) return `${m}m ${sec}s`; return `${sec}s`;
}
async function poll(){
  if(!job) return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){ msg.textContent="Job expired"; job=null; return;}
    const p=await r.json();
    const v=Math.max(0,Math.min(100,p.percent||0));
    bar.style.width=v+"%"; pct.textContent=v+"%";
    if(p.status==="error"){ msg.textContent="❌ "+(p.error||"Download failed"); job=null; return;}
    msg.textContent = p.status==="finished" ? "✅ Done — preparing file..." : (p.status==="downloaded" ? "✅ Downloaded" : "Downloading…");
    if(p.eta_seconds) eta.textContent="ETA: "+formatSeconds(p.eta_seconds); else eta.textContent="ETA: --";
    if(p.status==="finished"){ window.location="/fetch/"+job; job=null; return;}
    setTimeout(poll,800);
  }catch(e){ msg.textContent="Network error"; job=null; }
}
</script>
</body></html>
"""

# ---------- Backend ----------
JOBS = {}
YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def height_from_choice(choice):
    # map UI names to height integers (None for audio)
    return {"mp4_720":720, "mp4_1080":1080, "mp4_1440":1440, "mp4_2160":2160, "audio_mp3": None}.get(choice)

def format_map_for_env_has_ffmpeg():
    # fallback textual formats (used only if we cannot pick explicit IDs)
    return {
        "mp4_720":"bestvideo[height<=720]+bestaudio/best",
        "mp4_1080":"bestvideo[height<=1080]+bestaudio/best",
        "mp4_1440":"bestvideo[height<=1440]+bestaudio/best",
        "mp4_2160":"bestvideo[height<=2160]+bestaudio/best",
        "audio_mp3":"bestaudio/best"
    }

class Job:
    def __init__(self):
        self.id=str(uuid.uuid4())
        self.tmp=tempfile.mkdtemp(prefix="mvd_")
        self.percent=0
        self.status="queued"
        self.file=None
        self.error=None
        self.speed_bytes=0.0
        self.created_at=time.time()
        self.downloaded_at=None
        self.total_bytes=0
        self.downloaded_bytes=0
        JOBS[self.id]=self

def choose_video_format_id(info, target_height):
    """
    Given extract_info (download=False) info dict, find a video-only format id matching target_height exactly.
    Prefer native video-only (acodec == 'none'). If exact not found, return a closest lower height. If nothing, return None.
    """
    if not info: return None
    formats = info.get("formats", [])
    # gather video-only formats with height
    candidates = []
    for f in formats:
        if f.get("vcodec") and f.get("vcodec") != "none" and f.get("height"):
            # if audio is included too (acodec != 'none'), skip for video-only selection but we will accept if needed later
            candidates.append(f)
    # first try exact height (video-only or progressive)
    exact = [f for f in candidates if f.get("height")==target_height]
    if exact:
        # prefer those that are video-only (acodec == 'none') so we can add +bestaudio
        exact_video_only = [f for f in exact if f.get("acodec") in (None,"none","") or f.get("acodec")=="none"]
        if exact_video_only: return exact_video_only[0].get("format_id")
        return exact[0].get("format_id")
    # if no exact, pick best candidate with height <= target sorted by height desc
    lower = sorted([f for f in candidates if f.get("height")<target_height], key=lambda x: x.get("height") or 0, reverse=True)
    if lower:
        return lower[0].get("format_id")
    # as last resort, pick best overall video-only
    video_only = [f for f in formats if f.get("vcodec") and f.get("acodec") in (None,"none","")]
    if video_only:
        return video_only[0].get("format_id")
    return None

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error"; job.error="Invalid URL"; return

        target_height = height_from_choice(fmt_key)
        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        safe_base = f"{job.id}__{base}"
        out = os.path.join(job.tmp, safe_base + ".%(ext)s")

        # Hook to update job progress
        def hook(d):
            st = d.get("status")
            if st == "downloading":
                job.status = "downloading"
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes",0) or 0
                job.total_bytes = int(total or 0)
                job.downloaded_bytes = int(downloaded or 0)
                job.speed_bytes = d.get("speed") or 0
                if job.total_bytes:
                    try:
                        job.percent = int((job.downloaded_bytes * 100) / job.total_bytes)
                    except Exception:
                        pass
            elif st == "finished":
                job.percent = 100

        # Build basic opts
        opts = {
            "outtmpl": out,
            "progress_hooks":[hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "socket_timeout": 30,
            "cookiefile": "cookies.txt",
        }

        # Try to select exact video format id by inspecting available formats
        selected_format = None
        try:
            with YoutubeDL({"skip_download": True, "quiet": True, "noplaylist": True, "cookiefile": "cookies.txt"}) as y:
                info = y.extract_info(url, download=False)
            if target_height is None:
                # audio-only
                selected_format = "bestaudio"
            else:
                vid_id = choose_video_format_id(info, target_height)
                if vid_id:
                    # form "video_id+bestaudio/best" to ensure merging video+audio
                    selected_format = f"{vid_id}+bestaudio/best"
        except Exception:
            selected_format = None

        # fallback to textual format expression
        if not selected_format:
            fm = format_map_for_env_has_ffmpeg()
            selected_format = fm.get(fmt_key, "best")

        opts["format"] = selected_format

        # decide merge_output_format to preserve source codecs for >1080
        if HAS_FFMPEG:
            if target_height and target_height > 1080:
                # remux to mkv to preserve AV1/VP9 etc
                opts["merge_output_format"] = "mkv"
            else:
                opts["merge_output_format"] = "mp4"
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]

        # Start download
        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(os.path.join(job.tmp, "*"))
        job.file = max(files, key=os.path.getsize) if files else None
        job.status = "finished" if job.file else "error"
        if not job.file and job.status == "error":
            job.error = job.error or "No output file produced"
    except Exception as e:
        job.status="error"
        job.error=str(e)[:400]

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    # spawn background thread
    threading.Thread(target=run_download, args=(job, d.get("url",""), d.get("format_choice","mp4_2160"), d.get("filename")), daemon=True).start()
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
        # build simple formats summary for frontend (format_id, ext, height, filesize)
        fm_list = []
        for f in info.get("formats", []):
            fm_list.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "height": f.get("height"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "filesize": f.get("filesize") or f.get("filesize_approx")
            })
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}", "formats": fm_list})
    except Exception as e:
        return jsonify({"error":"Preview failed", "detail": str(e)[:400]}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j: abort(404)
    speed_b = getattr(j, "speed_bytes", 0) or 0
    speed_mbps = round((speed_b * 8) / 1_000_000, 1) if speed_b and speed_b > 0 else 0.0
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
        "speed_mbps": speed_mbps,
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "eta_seconds": eta_seconds
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j: abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error":"File not ready"}), 400
    j.downloaded_at = time.time(); j.status = "downloaded"
    return send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

# Cleanup worker
CLEANUP_INTERVAL = 60 * 10
JOB_TTL_SECONDS = 60 * 60      # remove finished/error jobs older than 1 hour
DOWNLOAD_KEEP_SECONDS = 60     # after user downloads file, remove from server after 60s

def cleanup_worker():
    while True:
        try:
            now = time.time()
            remove = []
            for jid, job in list(JOBS.items()):
                if job.status in ("finished","error") and (now - job.created_at > JOB_TTL_SECONDS):
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

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
