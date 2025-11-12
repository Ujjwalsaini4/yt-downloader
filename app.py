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

# ---------- Beautiful Modern HTML (added speed & ETA UI) ----------
HTML = r"""
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

/* Header */
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
/* gentle background pulse for subtle shine */
@keyframes bgPulse {
  0% { filter: hue-rotate(0deg) saturate(100%); }
  50% { filter: hue-rotate(8deg) saturate(110%); }
  100% { filter: hue-rotate(0deg) saturate(100%); }
}
.logo { animation: bgPulse 8s ease-in-out infinite; }
.brand-title span{
  background:var(--accent);
  -webkit-background-clip:text;
  color:transparent;
}

/* Card */
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

/* Form */
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

/* Grid responsive */
.grid{display:grid;gap:12px;}
@media(min-width:700px){.grid{grid-template-columns:2fr 1fr 1.2fr auto;align-items:end;}}
.full{grid-column:1/-1;}

/* Progress bar */
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

/* sheen overlay on progress */
.bar::after{
  content:"";
  position:absolute;inset:0;
  background:linear-gradient(90deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02), rgba(255,255,255,0.06));
  transform:translateX(-40%);opacity:0.6;filter:blur(6px);
  animation: sheen 2.4s linear infinite;
}
@keyframes sheen{100%{transform:translateX(120%)}}

/* Preview */
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

.meta-row{display:flex;justify-content:space-between;align-items:center;margin-top:10px}
.small-muted{color:var(--muted);font-size:13px}
.meta-right{display:flex;gap:12px;align-items:center}
.meta-item{background:rgba(255,255,255,0.02);padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,0.02);font-weight:700;font-size:13px;color:#e8f0ff}

footer{margin-top:20px;text-align:center;color:var(--muted);font-size:12px;}
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
  <h2>⬇️ Download from YouTube</h2>
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
          <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
          <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
          <option value="mp4_best">4K MP4</option>
          <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
        </select>
      </div>
      <div><label>Filename</label><input id="name" placeholder="My video"></div>
      <div class="full"><button id="goBtn" type="submit">⚡ Start Download</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div><div id="pct" class="pct">0%</div></div>

  <!-- ADDED: speed (one decimal) and ETA -->
  <div class="meta-row">
    <div id="msg" class="small-muted"></div>
    <div class="meta-right">
      <div id="speedLabel" class="meta-item">0.0 Mbps</div>
      <div id="etaLabel" class="meta-item">ETA: 00:00</div>
    </div>
  </div>

</main>

<footer>© 2025 Hyper Downloader — Auto cleanup & responsive UI</footer>
</div>

<script>
let job=null;
const bar=document.getElementById("bar"),pct=document.getElementById("pct"),msg=document.getElementById("msg");
const urlIn=document.getElementById("url"),thumb=document.getElementById("thumb"),preview=document.getElementById("preview"),pTitle=document.getElementById("pTitle"),pSub=document.getElementById("pSub");
const speedLabel = document.getElementById("speedLabel"), etaLabel = document.getElementById("etaLabel");

document.getElementById("frm").addEventListener("submit",async(e)=>{
  e.preventDefault();
  msg.textContent="⏳ Starting...";
  document.getElementById("goBtn").disabled = true;
  const url=urlIn.value.trim(),fmt=document.getElementById("format").value,name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j=await r.json();
    if(!r.ok)throw new Error(j.error||"Failed to start");
    job=j.job_id;msg.textContent="Downloading...";poll();
  }catch(err){msg.textContent="❌ "+err.message;document.getElementById("goBtn").disabled = false;}
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

// helper functions
function mbpsFromBytesPerSec(bps){
  if(!bps || bps <= 0) return 0.0;
  return (bps * 8) / 1_000_000;  // megabits per second
}
// show one decimal place only (e.g. 60.4 Mbps, 6.1 Mbps, 0.0 Mbps)
function fmtMbps(n){
  if(!n || n === 0) return '0.0 Mbps';
  return n.toFixed(1) + ' Mbps';
}
function fmtTimeSecs(s){
  if(!isFinite(s) || s <= 0) return '00:00';
  const sec = Math.round(s);
  const m = Math.floor(sec / 60);
  const ss = sec % 60;
  return String(m).padStart(2,'0') + ':' + String(ss).padStart(2,'0');
}

async function poll(){
  if(!job)return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){msg.textContent="Job expired.";document.getElementById("goBtn").disabled = false;job=null;return;}
    const p=await r.json();
    const pctv=Math.max(0,Math.min(100,p.percent||0));
    bar.style.width=pctv+"%";pct.textContent=pctv+"%";

    // update speed label (speed_bytes provided by backend)
    const mbps = mbpsFromBytesPerSec(p.speed_bytes || 0);
    speedLabel.textContent = fmtMbps(mbps);

    // calculate ETA using total_bytes, downloaded_bytes, speed_bytes
    let etaText = '00:00';
    if(p.total_bytes && p.downloaded_bytes && p.speed_bytes && p.speed_bytes > 0 && p.total_bytes > p.downloaded_bytes){
      const remaining = (p.total_bytes - p.downloaded_bytes);
      const secs = remaining / p.speed_bytes;
      etaText = fmtTimeSecs(secs);
    } else if (p.percent && p.percent > 0 && p.downloaded_bytes && p.speed_bytes && p.speed_bytes > 0) {
      // fallback: estimate total from percent
      const assumedTotal = (p.downloaded_bytes * 100) / p.percent;
      if(assumedTotal > p.downloaded_bytes){
        const remaining = assumedTotal - p.downloaded_bytes;
        const secs = remaining / p.speed_bytes;
        if(isFinite(secs) && secs > 0) etaText = fmtTimeSecs(secs);
      }
    }
    etaLabel.textContent = 'ETA: ' + etaText;

    if(p.status==="finished"){msg.textContent="✅ Preparing file...";setTimeout(()=>window.location="/fetch/"+job,600);job=null;document.getElementById("goBtn").disabled = false;return;}
    if(p.status==="error"){msg.textContent="❌ "+p.error;document.getElementById("goBtn").disabled = false;job=null;return;}
    setTimeout(poll,800);
  }catch(e){msg.textContent="Network error.";document.getElementById("goBtn").disabled = false;job=null;}
}
</script>
</body>
</html>
"""

# ---------- Backend (track bytes + speed for ETA) ----------
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

def run_download(job,url,fmt_key,filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error";job.error="Invalid URL";return
        fmt=format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status="error";job.error="Format not available";return

        def hook(d):
            try:
                if d.get("status")=="downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    job.total_bytes = int(total or 0)
                    job.downloaded_bytes = int(downloaded or 0)
                    if total:
                        job.percent = int((downloaded * 100) / total)
                    job.speed_bytes = d.get("speed") or 0
                elif d.get("status")=="finished":
                    job.percent = 100
            except Exception:
                pass

        base=(filename.strip() if filename else "%(title)s").rstrip(".")
        out=os.path.join(job.tmp,base+".%(ext)s")
        opts={
            "format":fmt,
            "outtmpl":out,
            "merge_output_format":"mp4",
            "cookiefile":"cookies.txt" if os.path.exists("cookies.txt") else None,
            "progress_hooks":[hook],
            "quiet":True,
            "no_warnings":True,
            "noplaylist":True
        }
        opts = {k:v for k,v in opts.items() if v is not None}
        if HAS_FFMPEG:
            opts["ffmpeg_location"]=ffmpeg_path()
            if fmt_key=="audio_mp3":
                opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url,download=True)

        files=glob.glob(job.tmp+"/*")
        job.file = max(files, key=os.path.getsize) if files else None
        job.status="finished"
    except Exception as e:
        job.status="error";job.error=str(e)[:300]

@app.post("/start")
def start():
    d=request.json or {}
    job=Job()
    threading.Thread(target=run_download,args=(job,d.get("url",""),d.get("format_choice","mp4_best"),d.get("filename")),daemon=True).start()
    return jsonify({"job_id":job.id})

@app.post("/info")
def info():
    d=request.json or {}
    url=d.get("url","")
    try:
        with YoutubeDL({"skip_download":True,"quiet":True,"noplaylist":True,"cookiefile":"cookies.txt" if os.path.exists("cookies.txt") else None}) as y:
            info=y.extract_info(url,download=False)
        title=info.get("title","")
        channel=info.get("uploader") or info.get("channel","")
        thumb=info.get("thumbnail")
        dur=info.get("duration") or 0
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}"})
    except Exception:
        return jsonify({"error":"Preview failed"}),400

@app.get("/progress/<id>")
def progress(id):
    j=JOBS.get(id)
    if not j:abort(404)
    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": j.speed_bytes,
        "downloaded_bytes": getattr(j,"downloaded_bytes",0),
        "total_bytes": getattr(j,"total_bytes",0)
    })

@app.get("/fetch/<id>")
def fetch(id):
    j=JOBS.get(id)
    if not j:abort(404)
    if not j.file or not os.path.exists(j.file):return jsonify({"error":"File not ready"}),400
    j.downloaded_at=time.time();j.status="downloaded"
    try:
        return send_file(j.file,as_attachment=True,download_name=os.path.basename(j.file))
    except Exception as e:
        return jsonify({"error":"Failed to send file","detail":str(e)}),500

@app.get("/env")
def env(): return jsonify({"ffmpeg":HAS_FFMPEG})

# Cleanup settings
CLEANUP_INTERVAL = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", 60 * 10))
JOB_TTL_SECONDS   = int(os.environ.get("JOB_TTL_SECONDS", 60 * 60))
DOWNLOAD_KEEP_SECONDS = int(os.environ.get("DOWNLOAD_KEEP_SECONDS", 60))

def cleanup_worker():
    while True:
        try:
            now=time.time()
            remove=[]
            for jid,job in list(JOBS.items()):
                if job.status in("finished","error") and now-job.created_at>JOB_TTL_SECONDS: remove.append(jid)
                if job.status=="downloaded" and job.downloaded_at and now-job.downloaded_at>DOWNLOAD_KEEP_SECONDS: remove.append(jid)
            for rid in remove:
                j=JOBS.pop(rid,None)
                if j:
                    try:
                        shutil.rmtree(j.tmp,ignore_errors=True)
                    except Exception:
                        pass
        except Exception as e:
            print("[cleanup]",e)
        time.sleep(CLEANUP_INTERVAL)
threading.Thread(target=cleanup_worker,daemon=True).start()

@app.get("/")
def home(): return render_template_string(HTML)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
