# -*- coding: utf-8 -*-
import os
import time
import tempfile
import shutil
import glob
import threading
import uuid
import re
from flask import Flask, request, jsonify, Response, render_template_string, abort, send_file
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

# ---------- BEAUTIFIED HTML UI ----------
HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hyper Downloader — Clean & Fast</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
  /* ---------- Typography & root ---------- */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
  :root{
    --bg:#071229;
    --card:#081427;
    --muted:#9fb0c8;
    --glass: rgba(255,255,255,0.04);
    --accent-1: #7c3aed; /* purple */
    --accent-2: #06b6d4; /* teal */
    --accent-grad: linear-gradient(90deg, var(--accent-1), var(--accent-2));
    --soft-shadow: 0 10px 30px rgba(2,6,23,0.6), inset 0 1px 0 rgba(255,255,255,0.02);
    --card-radius: 16px;
    --glass-border: rgba(255,255,255,0.03);
  }
  *{box-sizing:border-box}
  html,body{height:100%;margin:0;background: radial-gradient(1200px 600px at 10% 10%, rgba(124,58,237,0.08), transparent), radial-gradient(1000px 500px at 90% 90%, rgba(6,182,212,0.06), transparent), var(--bg); color:#e6eefc; font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial; -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale; }
  .wrap{max-width:1040px;margin:36px auto;padding:18px}

  /* ---------- Header ---------- */
  header.site{
    display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px;
    padding:10px 14px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); border:1px solid var(--glass-border);
    box-shadow:var(--soft-shadow);
    backdrop-filter: blur(6px) saturate(120%);
  }
  .brand{display:flex;align-items:center;gap:12px}
  .logo{
    width:52px;height:52px;border-radius:12px;background:var(--accent-grad);display:grid;place-items:center;font-weight:800;color:white;font-size:18px;box-shadow:0 8px 28px rgba(124,58,237,0.16);
    transform:translateY(0);transition:transform .28s cubic-bezier(.2,.9,.2,1);
  }
  .brand h1{margin:0;font-size:18px;letter-spacing:-0.2px}
  .brand h1 span{background:var(--accent-grad); -webkit-background-clip:text; color:transparent; font-weight:800}
  .controls{display:flex;gap:8px;align-items:center}
  .pill{padding:8px 12px;border-radius:999px;background:transparent;border:1px solid rgba(255,255,255,0.03);color:var(--muted);font-weight:600;font-size:13px}
  .cta{padding:10px 14px;border-radius:12px;background:var(--accent-grad);box-shadow:0 12px 30px rgba(6,182,212,0.08);font-weight:800;border:none;color:#fff;cursor:pointer;transition:transform .12s}
  .cta:hover{transform:translateY(-3px);box-shadow:0 18px 40px rgba(6,182,212,0.12)}

  /* ---------- Layout ---------- */
  .grid{
    display:grid;
    grid-template-columns: 1fr 400px;
    gap:18px;
    align-items:start;
  }
  @media (max-width:980px){ .grid{grid-template-columns:1fr} }

  /* ---------- Main card ---------- */
  .card{
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border:1px solid var(--glass-border);
    border-radius:var(--card-radius);
    padding:18px;
    box-shadow:var(--soft-shadow);
    transition:transform .18s ease, box-shadow .18s ease;
  }
  .card:hover{transform:translateY(-4px);box-shadow:0 18px 60px rgba(2,6,23,0.7)}

  label{display:block;color:var(--muted);font-size:13px;margin-bottom:8px;font-weight:600}

  .input, select, button{
    width:100%;
    padding:14px 12px;
    border-radius:12px;
    border:1px solid rgba(255,255,255,0.03);
    background: linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));
    color:var(--text);
    font-size:15px;
    outline:none;
    transition:box-shadow .12s,transform .08s;
  }
  .input::placeholder{color:rgba(159,176,200,0.5)}

  .row{display:flex;gap:12px}
  .row .col{flex:1}

  .btn-primary{
    display:inline-grid;place-items:center;
    padding:12px 16px;border-radius:12px;border:none;background:var(--accent-grad);color:white;font-weight:800;cursor:pointer;
    box-shadow:0 10px 30px rgba(124,58,237,0.12);
    transform:translateZ(0);
  }
  .btn-primary:active{transform:translateY(1px) scale(.997)}

  .muted{color:var(--muted);font-size:13px}

  /* ---------- Preview card ---------- */
  .preview{
    display:flex;gap:12px;align-items:center;padding:10px;border-radius:12px;border:1px solid rgba(255,255,255,0.02);background:linear-gradient(180deg, rgba(255,255,255,0.006), transparent);
    min-height:88px;overflow:hidden;
  }
  .thumb{
    width:140px;height:80px;border-radius:10px;flex:0 0 140px;object-fit:cover;background:linear-gradient(90deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    box-shadow:0 8px 20px rgba(2,6,23,0.6);
  }
  .meta .title{font-weight:800;font-size:15px;margin-bottom:6px}
  .meta .sub{color:var(--muted);font-size:13px}

  /* shimmer skeleton for preview while loading */
  .skeleton{position:relative;overflow:hidden;background:linear-gradient(90deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));}
  .skeleton::after{
    content:"";position:absolute;inset:0;background:linear-gradient(90deg, rgba(255,255,255,0.00) 0%, rgba(255,255,255,0.02) 50%, rgba(255,255,255,0.00) 100%);
    transform:translateX(-100%);animation: shimmer 1.6s linear infinite;
  }
  @keyframes shimmer{100%{transform:translateX(100%)}}

  /* ---------- Progress bar ---------- */
  .progress-wrap{margin-top:14px}
  .progress{
    height:18px;border-radius:999px;background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.005));border:1px solid rgba(255,255,255,0.02);overflow:hidden;position:relative
  }
  .progress .bar{
    height:100%;width:0%;background:linear-gradient(90deg, rgba(124,58,237,0.95), rgba(6,182,212,0.95));
    transition:width .28s cubic-bezier(.2,.9,.2,1), box-shadow .18s;
    box-shadow:0 8px 30px rgba(124,58,237,0.12);
    transform-origin:left center;
  }
  .progress .pct{
    position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-weight:800;font-size:13px;color:white;text-shadow:0 1px 0 rgba(0,0,0,0.5)
  }

  .meta-row{display:flex;justify-content:space-between;align-items:center;margin-top:10px}
  .speed{font-weight:700;font-size:13px;color:var(--muted)}

  /* small helper */
  .small{font-size:13px;color:var(--muted)}

  /* ---------- Footer card ---------- */
  .side{
    display:flex;flex-direction:column;gap:12px;
  }
  .card.alt{padding:12px;display:flex;flex-direction:column;gap:12px;align-items:stretch;min-height:180px}
  .feature{display:flex;gap:10px;align-items:center}
  .feature .dot{width:12px;height:12px;border-radius:4px;background:var(--accent-1);box-shadow:0 6px 18px rgba(124,58,237,0.14)}

  /* small animation for success */
  .flash {
    position:relative;
    animation: pop .42s cubic-bezier(.2,.9,.2,1) both;
  }
  @keyframes pop{0%{transform:scale(.96);opacity:.0}100%{transform:scale(1);opacity:1}}

</style>
</head>
<body>
  <div class="wrap">
    <header class="site">
      <div class="brand">
        <div class="logo">HD</div>
        <div>
          <h1>Hyper <span>Downloader</span></h1>
          <div class="small muted">Fast — Clean — Responsive</div>
        </div>
      </div>

      <div class="controls">
        <div class="pill small">Server: Live</div>
        <button class="cta">Go Premium</button>
      </div>
    </header>

    <div class="grid">
      <main class="card" aria-labelledby="mainTitle">
        <h2 id="mainTitle">⬇️ Download from YouTube</h2>
        <p class="small muted">Paste a video link, choose format & filename, and click start. Progress shows percent & speed.</p>

        <div id="previewArea" style="margin-top:12px">
          <div id="preview" class="preview" aria-live="polite" style="display:none">
            <img id="thumb" class="thumb" alt="">
            <div class="meta">
              <div id="pTitle" class="title">Title</div>
              <div id="pSub" class="sub">Channel • Duration</div>
            </div>
          </div>

          <div id="previewSkeleton" class="preview skeleton" style="display:none">
            <div style="width:140px;height:80px;border-radius:8px"></div>
            <div style="flex:1">
              <div style="height:16px;width:70%;border-radius:6px;margin-bottom:8px"></div>
              <div style="height:14px;width:40%;border-radius:6px"></div>
            </div>
          </div>
        </div>

        <form id="frm" style="margin-top:14px">
          <label>Video URL</label>
          <input id="url" class="input" placeholder="https://youtube.com/watch?v=..." required>

          <div class="row" style="margin-top:10px">
            <div class="col">
              <label>Format</label>
              <select id="format" class="input">
                <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
                <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
                <option value="mp4_best">4K MP4</option>
                <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
              </select>
            </div>
            <div class="col" style="flex:0.8">
              <label>Filename (optional)</label>
              <input id="name" class="input" placeholder="My video">
            </div>
            <div style="width:120px;align-self:end">
              <button id="goBtn" class="btn-primary" type="submit">⚡ Download</button>
            </div>
          </div>

          <div class="progress-wrap">
            <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100">
              <div id="bar" class="bar" style="width:0%"></div>
              <div id="pct" class="pct">0%</div>
            </div>
            <div class="meta-row">
              <div id="msg" class="small muted"></div>
              <div id="speed" class="speed">0 MB/s</div>
            </div>
          </div>
        </form>
      </main>

      <aside class="side">
        <div class="card alt">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="font-weight:800">Premium Features</div>
              <div class="small muted">Upgrade for faster queues & larger files</div>
            </div>
            <div style="font-size:28px">💎</div>
          </div>

          <div style="margin-top:12px;display:flex;flex-direction:column;gap:10px">
            <div class="feature"><div class="dot"></div><div class="small muted">4K & MP3 support</div></div>
            <div class="feature"><div class="dot" style="background:#06b6d4"></div><div class="small muted">Progress & speed</div></div>
            <div class="feature"><div class="dot"></div><div class="small muted">Auto-cleanup</div></div>
          </div>
        </div>

        <div class="card alt">
          <div style="font-weight:800;margin-bottom:8px">Quick Tips</div>
          <div class="small muted">• If a format is disabled, install FFmpeg on the server.</div>
          <div class="small muted">• Use the preview to confirm correct video before download.</div>
        </div>
      </aside>
    </div>
  </div>

<script>
/* ---------- Client JS: keep your existing behavior but with nicer UI updates ---------- */
let job = null, HAS_FFMPEG = false;
const urlIn = document.getElementById("url"), nameIn = document.getElementById("name"), formatSel = document.getElementById("format");
const bar = document.getElementById("bar"), pct = document.getElementById("pct"), msg = document.getElementById("msg"), speed = document.getElementById("speed");
const preview = document.getElementById("preview"), previewSkeleton = document.getElementById("previewSkeleton");
const thumb = document.getElementById("thumb"), pTitle = document.getElementById("pTitle"), pSub = document.getElementById("pSub");
const goBtn = document.getElementById("goBtn");

function setMsg(t, isErr=false){
  msg.textContent = t || "";
  msg.style.color = isErr ? "#fb7185" : "";
}
function setBusy(b){
  goBtn.disabled = b;
  goBtn.style.opacity = b ? 0.7 : 1;
}

fetch("/env").then(r=>r.json()).then(j=>{ HAS_FFMPEG = !!j.ffmpeg; if(!HAS_FFMPEG) setMsg("FFmpeg not found — some formats disabled"); });

let _deb=null;
urlIn.addEventListener("input", ()=>{
  clearTimeout(_deb);
  const u = urlIn.value.trim();
  if(!/^https?:\/\//i.test(u)){ preview.style.display='none'; previewSkeleton.style.display='none'; return; }
  previewSkeleton.style.display = 'flex'; preview.style.display = 'none';
  _deb = setTimeout(()=> fetchInfo(u), 450);
});

async function fetchInfo(url){
  try{
    const r = await fetch("/info", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({url})});
    const j = await r.json();
    if(!r.ok || j.error){ preview.style.display='none'; previewSkeleton.style.display='none'; setMsg("Preview failed", true); return; }
    pTitle.textContent = j.title || '';
    pSub.textContent = [j.channel, j.duration_str].filter(Boolean).join(' • ');
    if(j.thumbnail){ thumb.src = j.thumbnail; thumb.alt = j.title; }
    previewSkeleton.style.display = 'none';
    preview.style.display = 'flex';
    setMsg('');
  }catch(e){
    previewSkeleton.style.display = 'none';
    preview.style.display = 'none';
    setMsg('Preview error', true);
  }
}

document.getElementById("frm").addEventListener("submit", async (ev)=>{
  ev.preventDefault();
  setMsg('Starting download...');
  setBusy(true);
  const url = urlIn.value.trim(), fmt = formatSel.value, filename = nameIn.value.trim();
  if(!/^https?:\/\//i.test(url)){ setMsg('Please paste a valid URL', true); setBusy(false); return; }
  try{
    const r = await fetch('/start', {method:'POST', headers:{"Content-Type":"application/json"}, body: JSON.stringify({url, format_choice: fmt, filename})});
    const j = await r.json();
    if(!r.ok){ setMsg(j.error || 'Failed to start', true); setBusy(false); return; }
    job = j.job_id; setMsg('Downloading…'); poll();
  }catch(err){
    setMsg('Network error', true);
    setBusy(false);
  }
});

function fmtBytes(n){ if(!n) return '0 MB/s'; const mb = n/1024/1024; return (mb<0.1?mb.toFixed(2):mb.toFixed(1))+' MB/s'; }

async function poll(){
  if(!job) return;
  try{
    const r = await fetch('/progress/' + job);
    if(r.status === 404){ setMsg('Job expired', true); setBusy(false); job=null; return; }
    const p = await r.json();
    const pctv = Math.max(0, Math.min(100, p.percent || 0));
    bar.style.width = pctv + '%';
    pct.textContent = pctv + '%';
    speed.textContent = fmtBytes(p.speed_bytes);
    if(p.status === 'finished'){
      setMsg('Done — preparing file...');
      // small flash animation
      pct.classList.add('flash'); setTimeout(()=>pct.classList.remove('flash'), 600);
      // give UI a short moment before redirecting to fetch (so users see Done)
      setTimeout(()=> { window.location = '/fetch/' + job; job=null; setBusy(false); }, 700);
      return;
    } else if(p.status === 'error'){
      setMsg('Error: ' + (p.error || 'Download failed'), true);
      setBusy(false); job=null; return;
    }
    setTimeout(poll, 700);
  }catch(e){
    setMsg('Network error', true);
    setBusy(false); job=null;
  }
}
</script>
</body>
</html>
"""

# ---------- Jobs & server logic (unchanged core) ----------
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
        JOBS[self.id] = self

YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    if HAS_FFMPEG:
        return {
            "mp4_720":"bestvideo[height<=720]+bestaudio/best",
            "mp4_1080":"bestvideo[height<=1080]+bestaudio/best",
            "mp4_best":"bestvideo+bestaudio/best",
            "audio_mp3":"bestaudio/best"
        }
    else:
        return {"mp4_best":"best[ext=mp4]/best"}

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error"; job.error="Invalid URL"; return
        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status="error"; job.error="Selected format requires FFmpeg"; return

        def hook(d):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                    downloaded = d.get("downloaded_bytes", 0)
                    job.percent = int((downloaded * 100) / total) if total else 0
                    job.speed_bytes = d.get("speed") or 0
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
            "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True
        }
        opts = {k:v for k,v in opts.items() if v is not None}

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(job.tmp + "/*")
        job.file = max(files, key=os.path.getsize) if files else None
        job.status = "finished"
    except Exception as e:
        job.status = "error"
        job.error = str(e)[:300]

@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    t = threading.Thread(target=run_download, args=(job, d.get("url",""), d.get("format_choice","mp4_best"), d.get("filename")))
    t.daemon = True
    t.start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url","")
    try:
        with YoutubeDL({"skip_download":True,"quiet":True,"noplaylist":True,"cookiefile":"cookies.txt" if os.path.exists("cookies.txt") else None}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title","")
        channel = info.get("uploader") or info.get("channel","")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}"})
    except Exception:
        return jsonify({"error":"Preview failed"}),400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j: abort(404)
    return jsonify({"percent":j.percent,"status":j.status,"error":j.error,"speed_bytes":j.speed_bytes})

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j: abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error":"File not ready"}), 400

    filename = os.path.basename(j.file)
    j.downloaded_at = time.time()
    j.status = "downloaded"
    try:
        return send_file(j.file, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error":"Failed to stream file","detail":str(e)}), 500

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

# Background cleanup
CLEANUP_INTERVAL = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", 60 * 10))
JOB_TTL_SECONDS   = int(os.environ.get("JOB_TTL_SECONDS", 60 * 60 * 1))
DOWNLOAD_KEEP_SECONDS = int(os.environ.get("DOWNLOAD_KEEP_SECONDS", 60))

def cleanup_worker():
    while True:
        try:
            now = time.time()
            remove = []
            for jid, job in list(JOBS.items()):
                status = getattr(job, "status", None)
                created_at = getattr(job, "created_at", None) or now
                age = now - created_at

                if status in ("finished", "error") and age > JOB_TTL_SECONDS:
                    remove.append(jid)

                if status == "downloaded":
                    downloaded_at = getattr(job, "downloaded_at", None) or 0
                    if (now - downloaded_at) > DOWNLOAD_KEEP_SECONDS:
                        remove.append(jid)

                if status == "queued" and age > (JOB_TTL_SECONDS * 6):
                    remove.append(jid)

            for rid in remove:
                j = JOBS.pop(rid, None)
                if j:
                    try:
                        shutil.rmtree(getattr(j, "tmp", ""), ignore_errors=True)
                    except Exception as e:
                        print(f"[cleanup] failed to remove {rid}: {e}")
                    print(f"[cleanup] removed job {rid}")
        except Exception as e:
            print("[cleanup] error:", e)
        time.sleep(CLEANUP_INTERVAL)

_cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
_cleanup_thread.start()

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
