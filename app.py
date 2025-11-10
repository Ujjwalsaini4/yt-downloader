import os
from flask import Flask, request, jsonify, send_file, render_template_string, abort
import tempfile, shutil, os, glob, threading, uuid, io, re
from shutil import which

try:
    import ssl  # noqa: F401
except Exception as e:
    raise RuntimeError("Install official Python with SSL support.") from e

from yt_dlp import YoutubeDL

app = Flask(__name__)

# ✅ 1) COOKIES ENV → cookies.txt auto write (VERY IMPORTANT)
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)


# ---------- Env detection ----------
def ffmpeg_path():
    # Prefer system ffmpeg, else common Termux location
    return which("ffmpeg") or "/data/data/com.termux/files/usr/bin/ffmpeg"

HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML UI ----------
HTML = """YOUR EXISTING HTML HERE (UNTOUCHED)"""
# ✅ मैं HTML को नहीं छू रहा — ये तुम पहले जैसा रखो


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


def run_download(job: Job, url: str, fmt_key: str, name: str | None):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status = "error"; job.error = "Invalid URL."; return

        fmt_map = format_map_for_env()
        fmt = fmt_map.get(fmt_key)
        if not fmt:
            job.status = "error"; job.error = "This format requires FFmpeg."; return

        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                dl = d.get("downloaded_bytes", 0)
                job.percent = max(0, min(100, int(dl * 100 / total)))
                job.status = "downloading"
            elif d.get("status") == "finished":
                job.percent = 100

        base = (name.strip() if name else "%(title)s").rstrip(".")
        out = os.path.join(job.tmp, base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": out,
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 10,
            "socket_timeout": 30,
            # ✅ 2) COOKIES APPLY
            "cookiefile": "cookies.txt"
        }

        # ✅ 3) ffmpeg apply
        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = sorted(glob.glob(os.path.join(job.tmp,"*")), key=os.path.getsize)
        if not files:
            job.status="error"; job.error="No output file."; return

        job.file = files[-1]
        job.status="finished"

    except Exception as e:
        job.status="error"
        job.error = (str(e) or "Unexpected error.")[:200]


# ---------- Routes ----------
@app.post("/start")
def start():
    d = request.get_json(silent=True) or {}
    job = Job()
    threading.Thread(
        target=run_download,
        args=(job, d.get("url","").strip(), d.get("format_choice","mp4_best").strip(), d.get("filename") or None),
        daemon=True
    ).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.get_json(silent=True) or {}
    url = (d.get("url") or "").strip()
    if not url.startswith(("http://","https://")):
        return jsonify({"error":"Invalid URL"}), 400
    try:
        with YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True, "noplaylist": True}) as y:
            info = y.extract_info(url, download=False)
        return jsonify({
            "title": info.get("title",""),
            "thumbnail": info.get("thumbnail"),
            "channel": info.get("uploader") or info.get("channel",""),
            "duration_str": f"{info.get('duration',0)//60}:{info.get('duration',0)%60:02d}"
        })
    except:
        return jsonify({"error":"Preview failed"}), 400

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

@app.get("/progress/<job_id>")
def prog(job_id):
    j = JOBS.get(job_id)
    if not j: abort(404)
    return jsonify({"percent": j.percent, "status": j.status, "error": j.error})

@app.get("/fetch/<job_id>")
def fetch(job_id):
    j = JOBS.get(job_id)
    if not j or not j.file or not os.path.exists(j.file): abort(404)
    resp = send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    threading.Thread(target=lambda: (shutil.rmtree(j.tmp, ignore_errors=True), JOBS.pop(job_id,None)), daemon=True).start()
    return resp

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
