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

# ---------- UI with extra shine & animations ----------
HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hyper Downloader</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#050b16;
  --card:#071827;
  --muted:#9fb0c8;
  --grad1:#1e40af; /* royal blue */
  --grad2:#06b6d4; /* cyan */
  --accent: linear-gradient(90deg,var(--grad1),var(--grad2));
  --radius:16px;
  --glass: rgba(255,255,255,0.03);
  --glow: rgba(6,182,212,0.12);
}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:
  radial-gradient(800px 400px at 10% 10%, rgba(30,64,175,0.06), transparent),
  radial-gradient(900px 450px at 90% 90%, rgba(6,182,212,0.05), transparent),
  var(--bg);
  color:#e8f0ff;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans",sans-serif;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;padding:20px;}
.wrap{max-width:980px;margin:28px auto;padding:12px}

/* Header */
header{
  display:flex;align-items:center;justify-content:space-between;
  background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);
  border:1px solid var(--glass);padding:12px;border-radius:12px;margin-bottom:18px;
  box-shadow:0 10px 30px rgba(2,6,23,0.6);
  backdrop-filter: blur(6px) saturate(110%);
}
.brand{display:flex;align-items:center;gap:12px}
.logo{
  width:56px;height:56px;border-radius:12px;background:var(--accent);
  display:grid;place-items:center;font-weight:800;color:white;font-size:18px;
  box-shadow:0 12px 40px rgba(30,64,175,0.12);
  transition:transform .28s cubic-bezier(.2,.9,.2,1), box-shadow .28s;
  transform-origin:center;
  will-change:transform,box-shadow;
}
/* gentle breathing/pulse */
@keyframes breathe {
  0% { transform: scale(1); box-shadow:0 10px 30px rgba(30,64,175,0.08); }
  50% { transform: scale(1.03); box-shadow:0 20px 50px rgba(6,182,212,0.14); }
  100% { transform: scale(1); box-shadow:0 10px 30px rgba(30,64,175,0.08); }
}
.logo { animation: breathe 4s ease-in-out infinite; }

/* celebrate glow (on download complete) */
@keyframes celebrate {
  0% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(6,182,212,0)); }
  30% { transform: scale(1.08); filter: drop-shadow(0 18px 40px rgba(6,182,212,0.22)); }
  100% { transform: scale(1); filter: drop-shadow(0 0 0 rgba(6,182,212,0)); }
}
.logo.celebrate { animation: celebrate .9s ease-in-out both; }

/* sparkle ring */
.logo.celebrate::after{
  content:"";position:absolute;left:-12px;top:-12px;width:80px;height:80px;border-radius:50%;
  background: radial-gradient(circle at 30% 20%, rgba(6,182,212,0.18), transparent 20%),
              radial-gradient(circle at 70% 80%, rgba(124,58,237,0.12), transparent 18%);
  opacity:0.95;filter:blur(8px);pointer-events:none;
}

/* header texts */
.brand-title h1{margin:0;font-size:18px}
.brand-title h1 span{background:var(--accent);-webkit-background-clip:text;color:transparent}

/* Card */
.card{
  background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));
  border:1px solid var(--glass);border-radius:14px;padding:18px;box-shadow:0 12px 42px rgba(2,6,23,0.6);
}
.lead{color:var(--muted);margin-top:8px;margin-bottom:12px;font-size:14px}

/* form */
label{display:block;color:var(--muted);font-size:13px;margin-bottom:6px;font-weight:600}
.input, select, button{width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,0.04);background:#0b2031;color:#eaf4ff;font-size:15px}
.input::placeholder{color:#7a8da4}
button{background:var(--accent);border:none;color:#fff;font-weight:800;cursor:pointer;box-shadow:0 12px 36px rgba(6,182,212,0.12);transition:transform .08s}
button:active{transform:translateY(1px)}button[disabled]{opacity:.6;cursor:not-allowed}

/* layout responsive */
.grid{display:grid;gap:12px}
@media (min-width:900px){ .grid{grid-template-columns:2fr 380px} }

/* preview */
.preview{display:none;margin-top:12px;padding:10px;border-radius:10px;background:rgba(255,255,255,0.01);border:1px solid rgba(255,255,255,0.03)}
.preview-row{display:flex;gap:12px;align-items:center}
.thumb{width:140px;height:80px;border-radius:8px;object-fit:cover;background:#071a27}
.meta .title{font-weight:800;font-size:15px}
.meta .sub{color:var(--muted);font-size:13px}

/* skeleton shimmer for preview loading */
.skeleton{position:relative;overflow:hidden;background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));}
.skeleton::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg, rgba(255,255,255,0.00) 0%, rgba(255,255,255,0.03) 50%, rgba(255,255,255,0.00) 100%);transform:translateX(-120%);animation:shimmer 1.6s linear infinite}
@keyframes shimmer{100%{transform:translateX(120%)}}

/* progress bar with animated sheen */
.progress{margin-top:14px;height:16px;border-radius:999px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.03);position:relative;overflow:hidden}
.bar{height:100%;width:0%;background:linear-gradient(90deg,var(--grad1),var(--grad2));position:relative;transition:width .28s cubic-bezier(.22,.9,.3,1);box-shadow:0 10px 30px rgba(30,64,175,0.12)}
/* sheen overlay */
.bar::after{
  content:"";position:absolute;inset:0;background:linear-gradient(90deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02), rgba(255,255,255,0.06));mix-blend-mode:overlay;
  transform:translateX(-40%);opacity:0.65;filter:blur(6px);animation: sheen 2.4s linear infinite;
}
@keyframes sheen{100%{transform:translateX(120%)}}
.pct{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-weight:800;color:#fff;z-index:2;text-shadow:0 1px 0 rgba(0,0,0,0.6)}

/* small meta row */
.meta-row{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.small-muted{color:var(--muted);font-size:13px}

/* celebration pulse when complete */
.pulse {
  position:relative;
  overflow:visible;
}
.pulse:after{
  content:"";position:absolute;left:50%;top:50%;width:10px;height:10px;background:radial-gradient(circle at 30% 30%, rgba(255,255,255,0.12), transparent 40%);border-radius:50%;transform:translate(-50%,-50%) scale(0);animation: pop 900ms ease forwards;
}
@keyframes pop{0%{transform:translate(-50%,-50%) scale(0);}50%{transform:translate(-50%,-50%) scale(1.6);}100%{transform:translate(-50%,-50%) scale(0);}}

/* footer */
footer{margin-top:18px;text-align:center;color:var(--muted);font-size:13px}

/* responsive tweaks */
@media (max-width:520px){
  .thumb{width:96px;height:60px}
  header{flex-direction:column;align-items:flex-start;gap:10px}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div id="logo" class="logo">HD</div>
      <div class="brand-title"><h1>Hyper <span>Downloader</span></h1><div class="small-muted">Clean • Fast • Responsive</div></div>
    </div>
  </header>

  <section class="card" aria-labelledby="mainTitle">
    <h2 id="mainTitle">⬇️ Download from YouTube</h2>
    <p class="lead small-muted">Paste the video link, select format, and press start. We'll show percent & speed.</p>

    <div id="preview" class="preview" aria-live="polite" style="display:none">
      <div class="preview-row">
        <img id="thumb" class="thumb" alt="">
        <div class="meta">
          <div id="pTitle" class="title"></div>
          <div id="pSub" class="sub"></div>
        </div>
      </div>
    </div>

    <div id="previewSkeleton" class="preview skeleton" style="display:none;margin-top:12px">
      <div style="width:140px;height:80px;border-radius:8px"></div>
      <div style="flex:1;padding-left:10px">
        <div style="height:16px;width:70%;border-radius:8px;margin-bottom:8px"></div>
        <div style="height:14px;width:40%;border-radius:8px"></div>
      </div>
    </div>

    <form id="frm" style="margin-top:12px">
      <div class="grid">
        <div>
          <label>Video URL</label>
          <input id="url" class="input" placeholder="https://youtube.com/watch?v=..." required>
        </div>
        <div>
          <label>Format</label>
          <select id="format" class="input">
            <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
            <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
            <option value="mp4_best">4K MP4</option>
            <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
          </select>
        </div>
        <div>
          <label>Filename (optional)</label>
          <input id="name" class="input" placeholder="My video">
        </div>
        <div style="align-self:end">
          <button id="goBtn" class="pulse" type="submit">⚡ Start Download</button>
        </div>
      </div>
    </form>

    <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" style="margin-top:14px">
      <div id="bar" class="bar" style="width:0%"></div>
      <div id="pct" class="pct">0%</div>
    </div>
    <div class="meta-row" style="margin-top:10px">
      <div id="msg" class="small-muted"></div>
      <div id="speed" class="small-muted">0 MB/s</div>
    </div>
  </section>

  <footer>© 2025 Hyper Downloader — Auto cleanup enabled</footer>
</div>

<script>
/* ---------- UI behavior + celebrate animation ---------- */
let job = null;
const urlIn = document.getElementById('url'), nameIn = document.getElementById('name'), fmtSel = document.getElementById('format');
const bar = document.getElementById('bar'), pct = document.getElementById('pct'), msg = document.getElementById('msg'), speed = document.getElementById('speed');
const preview = document.getElementById('preview'), previewSkeleton = document.getElementById('previewSkeleton');
const thumb = document.getElementById('thumb'), pTitle = document.getElementById('pTitle'), pSub = document.getElementById('pSub');
const logo = document.getElementById('logo');

function setMsg(t, isErr=false){ msg.textContent = t || ''; msg.style.color = isErr ? '#fb7185' : ''; }
function setBusy(b){ document.getElementById('goBtn').disabled = b; }

fetch('/env').then(r=>r.json()).then(j=>{ if(!j.ffmpeg){ setMsg('FFmpeg not found — some formats disabled'); }});

let _deb = null;
urlIn.addEventListener('input', ()=>{
  clearTimeout(_deb);
  const u = urlIn.value.trim();
  if(!/^https?:\/\//i.test(u)){ preview.style.display='none'; previewSkeleton.style.display='none'; return; }
  preview.style.display='none'; previewSkeleton.style.display='block';
  _deb = setTimeout(()=> fetchInfo(u), 450);
});

async function fetchInfo(url){
  try{
    const r = await fetch('/info', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url})});
    const j = await r.json();
    if(!r.ok || j.error){ preview.style.display='none'; previewSkeleton.style.display='none'; setMsg('Preview failed', true); return; }
    pTitle.textContent = j.title || ''; pSub.textContent = [j.channel, j.duration_str].filter(Boolean).join(' • ');
    if(j.thumbnail){ thumb.src = j.thumbnail; thumb.alt = j.title; }
    previewSkeleton.style.display='none'; preview.style.display='block'; setMsg('');
  }catch(e){
    previewSkeleton.style.display='none'; preview.style.display='none'; setMsg('Preview error', true);
  }
}

document.getElementById('frm').addEventListener('submit', async function(e){
  e.preventDefault();
  setMsg('Starting...');
  setBusy(true);
  const url = urlIn.value.trim(), fmt = fmtSel.value, filename = nameIn.value.trim();
  if(!/^https?:\/\//i.test(url)){ setMsg('Please paste a valid URL', true); setBusy(false); return; }
  try{
    const r = await fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, format_choice: fmt, filename})});
    const j = await r.json();
    if(!r.ok){ setMsg(j.error || 'Failed to start', true); setBusy(false); return; }
    job = j.job_id; setMsg('Downloading...'); poll();
  }catch(err){
    setMsg('Network error', true); setBusy(false);
  }
});

function fmtBytes(n){ if(!n) return '0 MB/s'; const mb = n/1024/1024; return (mb<0.1?mb.toFixed(2):mb.toFixed(1)) + ' MB/s'; }

async function poll(){
  if(!job) return;
  try{
    const r = await fetch('/progress/' + job);
    if(r.status === 404){ setMsg('Job expired', true); job = null; setBusy(false); return; }
    const p = await r.json();
    const pctv = Math.max(0, Math.min(100, p.percent || 0));
    bar.style.width = pctv + '%'; pct.textContent = pctv + '%';
    speed.textContent = fmtBytes(p.speed_bytes);
    if(p.status === 'finished'){
      setMsg('✅ Done — preparing file...');
      // celebrate: brief logo glow + small pulse on button
      logo.classList.add('celebrate');
      const btn = document.getElementById('goBtn');
      btn.classList.add('pulse');
      setTimeout(()=>{ logo.classList.remove('celebrate'); btn.classList.remove('pulse'); }, 1200);
      // small delay so user sees done, then trigger fetch
      setTimeout(()=>{ window.location = '/fetch/' + job; job = null; setBusy(false); }, 800);
      return;
    } else if(p.status === 'error'){
      setMsg('❌ ' + (p.error || 'Download failed'), true);
      job = null; setBusy(false); return;
    }
    setTimeout(poll, 700);
  }catch(e){
    setMsg('Network error', true); setBusy(false); job = null;
  }
}
</script>
</body>
</html>
"""

# ---------- Backend logic (same core: downloads, progress, cleanup) ----------
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
    j.downloaded_at = time.time(); j.status = "downloaded"
    try:
        return send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    except Exception as e:
        return jsonify({"error":"Failed to stream file","detail":str(e)}), 500

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

# Cleanup settings
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
