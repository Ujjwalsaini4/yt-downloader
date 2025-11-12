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

# ---------- UI with shine + background pulse effects + speed/eta UI ----------
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
}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:var(--bg);color:#e8f0ff;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Noto Sans",sans-serif;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;padding:20px;}
.wrap{max-width:980px;margin:28px auto;padding:12px;position:relative;z-index:10}

/* animated background layers */
.bg-layer{position:fixed;inset:0;z-index:0;pointer-events:none;mix-blend-mode:screen}
.ring{position:absolute;border-radius:50%;filter:blur(90px);opacity:0.12}
.r1{width:820px;height:520px;left:-8%;top:-10%;background:radial-gradient(circle at 30% 30%, rgba(37,99,235,0.95), rgba(37,99,235,0.25), transparent)}
.r2{width:600px;height:400px;right:-6%;bottom:-6%;background:radial-gradient(circle at 70% 70%, rgba(6,182,212,0.85), rgba(6,182,212,0.18), transparent)}
.r3{width:300px;height:300px;left:50%;top:10%;transform:translateX(-10%);background:radial-gradient(circle at 50% 50%, rgba(124,58,237,0.65), rgba(124,58,237,0.08), transparent);opacity:0.06}

/* aurora overlay */
.aurora{position:fixed;inset:0;z-index:1;pointer-events:none;mix-blend-mode:overlay;opacity:0.35;background: linear-gradient(120deg, rgba(20,40,120,0.14), rgba(6,140,160,0.12), rgba(100,40,160,0.08));background-size:200% 200%;animation: aurora 18s linear infinite}
@keyframes aurora{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}

/* bokeh */
.bokeh{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:0.06}
.bokeh span{position:absolute;border-radius:50%;background:radial-gradient(circle, rgba(255,255,255,0.85), rgba(255,255,255,0.2));filter:blur(8px);animation: floaty 12s linear infinite}
.b1{left:5%;top:20%;width:18px;height:18px;animation-duration:14s}
.b2{left:18%;top:72%;width:26px;height:26px;animation-duration:20s}
.b3{left:82%;top:30%;width:20px;height:20px;animation-duration:16s}
.b4{left:70%;top:78%;width:14px;height:14px;animation-duration:18s}
@keyframes floaty{0%{transform:translateY(0) translateX(0)}50%{transform:translateY(-18px) translateX(10px)}100%{transform:translateY(0) translateX(0)}}

/* Header */
header{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);border:1px solid rgba(255,255,255,0.02);padding:12px 18px;border-radius:12px;margin-bottom:18px;box-shadow:0 10px 30px rgba(2,6,23,0.6);backdrop-filter: blur(6px) saturate(110%);z-index:10}
.brand{display:flex;align-items:center;gap:12px}
.logo{width:56px;height:56px;border-radius:12px;background:var(--accent);display:grid;place-items:center;font-weight:800;color:white;font-size:18px;box-shadow:0 12px 40px rgba(30,64,175,0.12);transition:transform .28s cubic-bezier(.2,.9,.2,1), box-shadow .28s;transform-origin:center;will-change:transform,box-shadow;animation: breathe 4s ease-in-out infinite}
@keyframes breathe{0%{transform:scale(1)}50%{transform:scale(1.03)}100%{transform:scale(1)}}
.logo.celebrate{animation: celebrate .9s ease-in-out both}
@keyframes celebrate{0%{transform:scale(1)}30%{transform:scale(1.08)}100%{transform:scale(1)}}
.brand-title span{background:var(--accent);-webkit-background-clip:text;color:transparent}

/* Card */
.card{background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));border:1px solid rgba(255,255,255,0.03);border-radius:14px;padding:18px;box-shadow:0 12px 42px rgba(2,6,23,0.6);transition:transform .18s ease,box-shadow .18s ease;z-index:10}
.card:hover{transform:translateY(-4px);box-shadow:0 18px 60px rgba(2,6,23,0.72)}

/* form */
label{display:block;color:var(--muted);font-size:13px;margin-bottom:6px;font-weight:600}
input,select,button{width:100%;padding:12px 14px;border-radius:12px;border:1px solid rgba(255,255,255,0.04);background:#0b2031;color:#eaf4ff;font-size:15px}
input::placeholder{color:#7a8da4}
button{background:var(--accent);border:none;color:#fff;font-weight:800;cursor:pointer;box-shadow:0 12px 36px rgba(6,182,212,0.12);transition:transform .08s}
button:active{transform:translateY(1px)}button[disabled]{opacity:.6;cursor:not-allowed}

/* grid */
.grid{display:grid;gap:12px}
@media (min-width:900px){ .grid{grid-template-columns:2fr 380px} }

/* preview */
.preview{display:none;margin-top:12px;padding:10px;border-radius:10px;background:rgba(255,255,255,0.01);border:1px solid rgba(255,255,255,0.03);box-shadow:inset 0 1px 0 rgba(255,255,255,0.02)}
.preview-row{display:flex;gap:12px;align-items:center}
.thumb{width:140px;height:80px;border-radius:8px;object-fit:cover;background:#071a27}
.meta .title{font-weight:800;font-size:15px}
.meta .sub{color:var(--muted);font-size:13px;margin-top:6px}

/* progress */
.progress{margin-top:14px;height:16px;border-radius:999px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.03);position:relative;overflow:hidden}
.bar{height:100%;width:0%;background:linear-gradient(90deg,var(--grad1),var(--grad2));transition:width .28s cubic-bezier(.22,.9,.3,1);box-shadow:0 10px 30px rgba(30,64,175,0.12);position:relative}
.bar::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02), rgba(255,255,255,0.06));mix-blend-mode:overlay;transform:translateX(-50%);opacity:0.65;filter:blur(6px);animation:sheen 2.4s linear infinite}
@keyframes sheen{100%{transform:translateX(120%)}}
.pct{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-weight:800;color:#fff;z-index:2;text-shadow:0 1px 0 rgba(0,0,0,0.6)}

/* meta-row contains speed (MBps/Mbps) and eta */
.meta-row{display:flex;justify-content:space-between;align-items:center;margin-top:10px;gap:10px}
.small-muted{color:var(--muted);font-size:13px}
.meta-right{display:flex;gap:12px;align-items:center}
.meta-item{background:rgba(255,255,255,0.02);padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,0.02);font-weight:700;font-size:13px;color:#e8f0ff}

/* footer */
footer{margin-top:18px;text-align:center;color:var(--muted);font-size:13px;z-index:10}

/* responsive */
@media (max-width:520px){.thumb{width:96px;height:60px}header{flex-direction:column;align-items:flex-start;gap:10px}}
</style>
</head>
<body>
  <div class="bg-layer" aria-hidden="true">
    <div class="r1 ring"></div>
    <div class="r2 ring"></div>
    <div class="r3 ring"></div>
  </div>
  <div class="aurora" aria-hidden="true"></div>
  <div class="bokeh" aria-hidden="true">
    <span class="b1"></span><span class="b2"></span><span class="b3"></span><span class="b4"></span>
  </div>

  <div class="wrap">
    <header>
      <div class="brand">
        <div id="logo" class="logo">HD</div>
        <div class="brand-title"><h1>Hyper <span>Downloader</span></h1><div class="small-muted">Clean • Fast • Responsive</div></div>
      </div>
    </header>

    <main class="card" aria-labelledby="mainTitle">
      <h2 id="mainTitle">📥 Download from YouTube</h2>
      <p class="small-muted">Paste link, choose format, and start. Progress bar has sheen & speed/ETA info.</p>

      <div id="preview" class="preview" aria-live="polite" style="display:none">
        <div class="preview-row">
          <img id="thumb" class="thumb" alt="">
          <div class="meta">
            <div id="pTitle" class="title"></div>
            <div id="pSub" class="sub"></div>
          </div>
        </div>
      </div>

      <div id="previewSkeleton" class="preview" style="display:none;margin-top:12px">
        <div style="width:140px;height:80px;border-radius:8px;background:linear-gradient(90deg, rgba(255,255,255,0.01), rgba(255,255,255,0.02));"></div>
        <div style="flex:1;padding-left:12px">
          <div style="height:16px;width:70%;border-radius:8px;background:rgba(255,255,255,0.02);margin-bottom:8px"></div>
          <div style="height:14px;width:40%;border-radius:8px;background:rgba(255,255,255,0.01)"></div>
        </div>
      </div>

      <form id="frm" style="margin-top:12px">
        <div class="grid">
          <div>
            <label>Video URL</label>
            <input id="url" placeholder="https://youtube.com/watch?v=..." required>
          </div>

          <div>
            <label>Format</label>
            <select id="format">
              <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
              <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
              <option value="mp4_best">4K MP4</option>
              <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
            </select>
          </div>

          <div>
            <label>Filename (optional)</label>
            <input id="name" placeholder="My video">
          </div>

          <div style="align-self:end">
            <button id="goBtn" type="submit">⚡ Start Download</button>
          </div>
        </div>
      </form>

      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" style="margin-top:14px">
        <div id="bar" class="bar" style="width:0%"></div>
        <div id="pct" class="pct">0%</div>
      </div>

      <div class="meta-row" style="margin-top:10px">
        <div id="msg" class="small-muted"> </div>
        <div class="meta-right">
          <div id="speedLabel" class="meta-item">0 Mbps</div>
          <div id="etaLabel" class="meta-item">ETA: --:--</div>
        </div>
      </div>
    </main>

    <footer>© 2025 Hyper Downloader — Auto cleanup & responsive UI</footer>
  </div>

<script>
/* ----------------- Client JS: show Mbps and ETA ----------------- */
let job = null;
const urlIn = document.getElementById('url'), nameIn = document.getElementById('name'), fmtSel = document.getElementById('format');
const bar = document.getElementById('bar'), pct = document.getElementById('pct'), msg = document.getElementById('msg');
const speedLabel = document.getElementById('speedLabel'), etaLabel = document.getElementById('etaLabel');
const preview = document.getElementById('preview'), previewSkeleton = document.getElementById('previewSkeleton');
const thumb = document.getElementById('thumb'), pTitle = document.getElementById('pTitle'), pSub = document.getElementById('pSub');
const logo = document.getElementById('logo');

// randomize bokeh
document.querySelectorAll('.bokeh span').forEach((el)=>{
  el.style.left = (5 + Math.random()*90) + '%';
  el.style.top = (5 + Math.random()*90) + '%';
  el.style.opacity = (0.03 + Math.random()*0.07).toFixed(2);
});

// helper formatting
function mbpsFromBytesPerSec(bps){
  if(!bps || bps <= 0) return 0;
  // convert bytes/sec -> megabits/sec (decimal megabit)
  return (bps * 8 / 1_000_000);
}
function fmtMbps(n){
  if(!n) return '0 Mbps';
  return n >= 1 ? n.toFixed(2) + ' Mbps' : n.toFixed(2) + ' Mbps';
}
function fmtTimeSecs(s){
  if(!isFinite(s) || s <= 0) return '--:--';
  const sec = Math.round(s);
  const m = Math.floor(sec / 60);
  const ss = sec % 60;
  return String(m).padStart(2,'0') + ':' + String(ss).padStart(2,'0');
}

fetch('/env').then(r=>r.json()).then(j=>{ if(!j.ffmpeg){ msg.textContent='FFmpeg not found — some formats disabled'; msg.style.color='#f59e0b'; }});

// preview debounce
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
    if(!r.ok || j.error){ preview.style.display='none'; previewSkeleton.style.display='none'; msg.textContent='Preview failed'; return; }
    pTitle.textContent = j.title || ''; pSub.textContent = [j.channel, j.duration_str].filter(Boolean).join(' • ');
    if(j.thumbnail) thumb.src = j.thumbnail;
    previewSkeleton.style.display='none'; preview.style.display='block'; msg.textContent='';
  }catch(e){
    previewSkeleton.style.display='none'; preview.style.display='none'; msg.textContent='Preview error';
  }
}

document.getElementById('frm').addEventListener('submit', async function(e){
  e.preventDefault();
  msg.textContent = 'Starting...'; msg.style.color = '';
  document.getElementById('goBtn').disabled = true;
  const url = urlIn.value.trim(), fmt = fmtSel.value, filename = nameIn.value.trim();
  if(!/^https?:\/\//i.test(url)){ msg.textContent='Please paste a valid URL'; msg.style.color='#fb7185'; document.getElementById('goBtn').disabled = false; return; }
  try{
    const r = await fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, format_choice: fmt, filename})});
    const j = await r.json();
    if(!r.ok){ throw new Error(j.error || 'Failed to start'); }
    job = j.job_id; msg.textContent='Downloading...'; poll();
  }catch(err){
    msg.textContent = '❌ ' + (err.message || 'Network error'); msg.style.color = '#fb7185'; document.getElementById('goBtn').disabled = false;
  }
});

function fmtBytes(n){ if(!n) return '0 MB/s'; const mb = n/1024/1024; return (mb<0.1?mb.toFixed(2):mb.toFixed(1)) + ' MB/s'; }

async function poll(){
  if(!job) return;
  try{
    const r = await fetch('/progress/' + job);
    if(r.status === 404){ msg.textContent='Job expired.'; document.getElementById('goBtn').disabled = false; job = null; return; }
    const p = await r.json();
    const pctv = Math.max(0, Math.min(100, p.percent || 0));
    bar.style.width = pctv + '%'; pct.textContent = pctv + '%';

    // speed -> Mbps
    const mbps = mbpsFromBytesPerSec(p.speed_bytes || 0);
    speedLabel.textContent = fmtMbps(mbps);

    // ETA calculation: if total_bytes & downloaded_bytes & speed known
    let etaText = '--:--';
    if(p.total_bytes && p.downloaded_bytes && p.speed_bytes && p.speed_bytes > 0 && p.total_bytes > p.downloaded_bytes){
      const remaining = (p.total_bytes - p.downloaded_bytes);
      const secs = remaining / p.speed_bytes;
      etaText = fmtTimeSecs(secs);
    } else if(p.percent && p.percent > 0 && p.speed_bytes && p.speed_bytes > 0){
      // fallback estimate using percent if total_bytes missing:
      // assume total size based on percent: downloaded = percent% of total -> estimate total
      const assumedTotal = (p.downloaded_bytes && p.downloaded_bytes > 0) ? p.downloaded_bytes * 100 / p.percent : None;
      if(assumedTotal && p.downloaded_bytes && assumedTotal > p.downloaded_bytes){
        const remaining = assumedTotal - p.downloaded_bytes;
        const secs = remaining / p.speed_bytes;
        if(isFinite(secs) && secs > 0) etaText = fmtTimeSecs(secs);
      }
    }
    etaLabel.textContent = 'ETA: ' + etaText;

    if(p.status === 'finished'){
      msg.textContent = '✅ Done — preparing file...';
      logo.classList.add('celebrate');
      setTimeout(()=> logo.classList.remove('celebrate'), 1200);
      setTimeout(()=> { window.location = '/fetch/' + job; job = null; document.getElementById('goBtn').disabled = false; }, 800);
      return;
    } else if(p.status === 'error'){
      msg.textContent = '❌ ' + (p.error || 'Download failed'); msg.style.color = '#fb7185';
      document.getElementById('goBtn').disabled = false; job = null; return;
    }
    setTimeout(poll, 700);
  }catch(e){
    msg.textContent = 'Network error.'; document.getElementById('goBtn').disabled = false; job = null;
  }
}
</script>
</body>
</html>
"""

# ---------- Backend (updated: tracks downloaded_bytes & total_bytes) ----------
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
        self.downloaded_bytes = 0
        self.total_bytes = 0
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
            job.status = "error"; job.error = "Invalid URL"; return
        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status = "error"; job.error = "Selected format requires FFmpeg"; return

        def hook(d):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    job.total_bytes = int(total or 0)
                    job.downloaded_bytes = int(downloaded or 0)
                    job.percent = int((downloaded * 100) / total) if total else job.percent
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
    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": j.speed_bytes,
        "downloaded_bytes": j.downloaded_bytes,
        "total_bytes": j.total_bytes
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j: abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error":"File not ready"}), 400
    # mark as fetched — cleanup will remove after DOWNLOAD_KEEP_SECONDS
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
JOB_TTL_SECONDS   = int(os.environ.get("JOB_TTL_SECONDS", 60 * 60))
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
