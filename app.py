#!/usr/bin/env python3
import os
import tempfile
import shutil
import threading
import uuid
import pathlib
import logging
import time
import json
from flask import Flask, request, render_template, render_template_string, send_file, jsonify, abort, Response
from jinja2 import TemplateNotFound

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except Exception:
    Limiter = None
    get_remote_address = None
    HAS_LIMITER = False

from yt_dlp import YoutubeDL

# ----------------- App init -----------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change-this")

if HAS_LIMITER:
    limiter = Limiter(get_remote_address, app=app, default_limits=["100 per day", "5 per minute"])
else:
    limiter = None

# ----------------- Paths / logging -----------------
TEMP_ROOT = pathlib.Path(tempfile.gettempdir()) / "yt_jobs"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt")

JOBS = {}
PROGRESS = {}
ACTIVE = set()

# ----------------- Helpers -----------------

def safe_rm(p: pathlib.Path):
    try:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    except Exception:
        logger.exception("Failed to remove %s", p)


def limit(rule):
    def wrap(func):
        if HAS_LIMITER and limiter is not None:
            return limiter.limit(rule)(func)
        return func
    return wrap


def single_download(func):
    def wrapper(*a, **kw):
        ip = request.remote_addr or request.environ.get('REMOTE_ADDR', 'unknown')
        if ip in ACTIVE:
            return jsonify({"ok": False, "error": "Wait, your previous download is still running."}), 429
        ACTIVE.add(ip)
        try:
            return func(*a, **kw)
        finally:
            # give small delay before releasing so concurrent UI checks don't collide
            threading.Timer(2, lambda: ACTIVE.discard(ip)).start()
    wrapper.__name__ = func.__name__
    return wrapper


def progress_hook(job_id):
    def hook(d):
        try:
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                pct = round(done / total * 100, 2) if total else 0
                PROGRESS[job_id] = {"percent": pct, "eta": d.get("eta")}
            elif status == "finished":
                PROGRESS[job_id] = {"text": "Merging / Processing..."}
        except Exception:
            logger.exception("progress hook failed for %s", job_id)
    return hook

# ----------------- Routes -----------------

@app.route("/")
def index():
    try:
        return render_template("index.html")
    except TemplateNotFound:
        # fallback inline page so app never crashes when template missing
        return render_template_string(
            """
            <!doctype html>
            <html>
              <head><meta charset="utf-8"><title>YT Downloader (fallback)</title></head>
              <body>
                <h1>YT Downloader</h1>
                <form action="/start" method="post">
                  <input name="url" placeholder="YouTube URL" required>
                  <select name="type"><option value="mp4">MP4</option><option value="mp3">MP3</option></select>
                  <button type="submit">Start</button>
                </form>
              </body>
            </html>
            """
        )


@app.route("/start", methods=["POST"])
@limit("3 per minute")
@single_download
def start():
    url = request.form.get("url", "").strip()
    ftype = request.form.get("type", "mp4")

    if not url:
        return jsonify({"ok": False, "error": "Enter a valid YouTube URL"}), 400

    job_id = uuid.uuid4().hex
    work = TEMP_ROOT / job_id
    work.mkdir(parents=True, exist_ok=True)
    PROGRESS[job_id] = {"percent": 0}

    JOBS[job_id] = {"status": "processing", "file": None, "type": ftype}

    def worker():
        try:
            out = str(work / "%(title).200s-%(id)s.%(ext)s")
            opts = {
                "outtmpl": out,
                "noplaylist": True,
                "quiet": True,
                "progress_hooks": [progress_hook(job_id)],
            }

            if ftype == "mp3":
                opts["format"] = "bestaudio/best"
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
            else:
                # choose best video up to 2160p + audio
                opts["format"] = "bestvideo[height<=2160]+bestaudio/best"

            with YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)

            # pick largest file in work dir
            files = list(work.iterdir())
            if not files:
                raise RuntimeError("No output file produced")

            file = max(files, key=lambda x: x.stat().st_size)
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["file"] = str(file)

            # schedule cleanup after 3 minutes
            threading.Timer(180, lambda: safe_rm(work)).start()

        except Exception as e:
            logger.exception("Download failed for %s", job_id)
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
            safe_rm(work)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    if job_id not in JOBS:
        return abort(404)

    def stream():
        # SSE stream
        while True:
            job = JOBS.get(job_id, {})
            data = {"status": job.get("status"), "progress": PROGRESS.get(job_id)}
            yield "data: " + json.dumps(data) + "\n\n"
            if job.get("status") in ("done", "error"):
                break
            time.sleep(1)

    return Response(stream(), mimetype="text/event-stream")


@app.route("/file/<job_id>")
def file(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        return abort(404)
    p = pathlib.Path(job["file"])
    if not p.exists():
        return abort(404)
    return send_file(str(p), as_attachment=True, download_name=p.name)


@app.route("/status/<job_id>")
def status(job_id):
    if job_id not in JOBS:
        return jsonify({"ok": False, "error": "unknown job"}), 404
    return jsonify({"ok": True, "job": JOBS[job_id], "progress": PROGRESS.get(job_id)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port)
