# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify, send_file, render_template_string, abort
import tempfile, shutil, glob, threading, uuid, re
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

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>💎 Hyper Downloader</title>

<style>
:root{
  --bg:#0b0f19;
  --card:#0f1724;
  --text:#e6eefc;
  --muted:#97a6b2;
  --border:#192230;
  --grad-1:#8b5cf6;
  --grad-2:#06b6d4;
  --grad:linear-gradient(90deg,var(--grad-1),var(--grad-2));
}

/* Basic layout */
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Noto Sans",sans-serif}
.wrap{max-width:920px;margin:auto;padding:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;box-shadow:0 8px 30px rgba(0,0,0,.28);margin-top:16px}
h1,h2{margin:0;font-weight:800}
p{margin:0}
.lead{color:var(--muted);margin-top:6px;margin-bottom:8px;font-size:14px}

/* Header */
.header{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:44px;height:44px;border-radius:12px;background:var(--grad);display:grid;place-items:center;font-weight:800;color:#fff;box-shadow:0 6px 18px rgba(0,0,0,.28);font-size:18px}
.brand{font-size:20px;font-weight:800;display:flex;align-items:center;gap:8px}
.brand span{background:var(--grad);-webkit-background-clip:text;color:transparent}
nav{display:flex;align-items:center;gap:10px}
nav a{color:var(--muted);text-decoration:none;font-weight:600;padding:6px 8px;border-radius:10px}
nav a.btn{background:var(--grad);color:#fff;padding:8px 14px;box-shadow:0 8px 24px rgba(107,60,246,.18);font-weight:800}
nav a:hover{color:#fff}

/* Form */
form{display:grid;gap:12px;margin-top:10px}
label{display:block;color:var(--muted);font-size:13px;margin-bottom:6px}
input,select,button{
  width:100%;padding:12px 12px;border-radius:10px;border:1px solid var(--border);
  background:#081223;color:var(--text);font-size:15px;
}
input::placeholder{color:#546171}
button{background:var(--grad);color:#fff;border:none;font-weight:800;cursor:pointer;padding:12px;border-radius:10px;transition:transform .08s}
button:active{transform:scale(.99)}
button:disabled{opacity:.6;cursor:not-allowed}

/* PROGRESS - fixed percent centering */
.progress{
  position:relative;
  width:100%;
  height:20px;
  background:#0b1623;
  border-radius:999px;
  overflow:hidden;
  margin-top:10px;
  border:1px solid rgba(255,255,255,0.02);
}
.bar{
  position:absolute;
  left:0;
  top:0;
  bottom:0;
  width:0%;
  background:var(--grad);
  transition:width .24s ease;
  z-index:1;
}
.pct{
  position:absolute;
  left:50%;
  top:50%;
  transform:translate(-50%,-50%);
  display:inline-grid;
  place-items:center;
  font-weight:800;
  color:#fff;
  font-size:13px;
  z-index:3;
  pointer-events:none;
  white-space:nowrap;
  text-shadow:0 1px 0 rgba(0,0,0,0.6);
}

.footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;color:var(--muted);font-size:13px}

/* Preview */
.preview{display:none;margin-top:12px;background:#07101a;padding:10px;border-radius:10px;border:1px solid var(--border)}
.preview-row{display:flex;gap:12px;align-items:center}
.thumb{width:100px;aspect-ratio:16/9;border-radius:8px;object-fit:cover;background:#0a0a0a}
.meta .title{font-weight:800;font-size:14px;margin-bottom:4px}
.meta .sub{color:var(--muted);font-size:13px}

/* Responsive tweaks */
@media (max-width:640px){
  .wrap{padding:12px}
  .card{padding:12px}
  .logo-icon{width:38px;height:38px;font-size:15px}
  .brand{font-size:18px}
  nav a{font-size:13px;padding:6px}
  nav a.btn{padding:8px 12px}
  h2{font-size:19px}
  .lead{font-size:13px}
  input,select,button{padding:10px;font-size:14px}
  .progress{height:10px}
  .pct{font-size:12px}
  .footer{font-size:12px}
}
</style>
</head>
<body>
  <div class="wrap">
    <header class="header">
      <div class="logo">
        <div class="logo-icon">HD</div>
        <div class="brand">Hyper <span>Downloader</span></div>
      </div>
      <nav>
        <a href="#features">💎 Premium</a>
        <a href="#faq">❓ FAQ</a>
      <!-- <a href="#" class="btn">Go Premium</a> -->
      </nav>
    </header>

    <section class="card">
      <h2>📥 Download from YouTube</h2>
      <p class="lead">🎬 Paste your video link, choose format, and start downloading.</p>

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
        <label>Video URL</label>
        <input id="url" placeholder="https://youtube.com/watch?v=..." required>
        <label>Format</label>
        <select id="format">
          <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
          <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
          <option value="mp4_best">4K MP4</option>
          <option value="audio_mp3" data-need-ffmpeg="1">MP3 Only</option>
        </select>
        <label>Filename (optional)</label>
        <input id="name" placeholder="My video">
        <button id="goBtn" type="submit">⚡ Start Download</button>
      </form>

      <div class="progress"><div id="bar" class="bar"></div><div class="pct" id="pctTxt"></div></div> <!-- 0% -->
      <div class="footer"><span id="msg"></span><span id="speedTxt">0 MB/s</span></div>
    </section>

    <section id="features" class="card">
      <h2>💎 Premium Features</h2>
      <ul>
        <li>4K + MP3 download support</li>
        <li>Progress bar with speed & percent</li>
        <li>Beautiful gradient UI</li>
        <li>Fully mobile responsive</li>
      </ul>
    </section>

    <section id="faq" class="card">
      <h2>❓ FAQ</h2>
      <p>If options are disabled, your server may not have FFmpeg installed.</p>
    </section>
  </div>

<script>
let job=null, HAS_FFMPEG=false;
const bar=document.getElementById("bar"), pctTxt=document.getElementById("pctTxt"), msg=document.getElementById("msg"), speedTxt=document.getElementById("speedTxt");
const previewBlock=document.getElementById("preview"), thumb=document.getElementById("thumb"), pTitle=document.getElementById("pTitle"), pSub=document.getElementById("pSub");

fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG=!!j.ffmpeg;
  if(!HAS_FFMPEG){msg.textContent="⚠️ FFmpeg missing — MP3/merge disabled.";msg.style.color="#f59e0b";}
});

async function fetchInfo(url){
  try{
    const r=await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j=await r.json();
    if(!r.ok || j.error){ previewBlock.style.display="none"; return; }
    pTitle.textContent=j.title||"";
    pSub.textContent=[j.channel,j.duration_str].filter(Boolean).join(" • ");
    if(j.thumbnail){ thumb.src=j.thumbnail; thumb.alt=j.title; }
    previewBlock.style.display="block";
  }catch(e){ previewBlock.style.display="none"; }
}

document.getElementById("url").addEventListener("input", ()=>{
  clearTimeout(window._deb);
  const u=document.getElementById("url").value.trim();
  if(!/^https?:\/\//i.test(u)){ previewBlock.style.display="none"; return; }
  window._deb=setTimeout(()=>fetchInfo(u),500);
});

document.getElementById("frm").addEventListener("submit", async (e)=>{
  e.preventDefault();
  msg.textContent="⏳ Starting...";
  const url=document.getElementById("url").value.trim();
  const fmt=document.getElementById("format").value;
  const name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j=await r.json();job=j.job_id;poll();
  }catch(err){msg.textContent="Error starting download.";msg.style.color="#fb7185";job=null;}
});

function fmtBytes(n){if(!n)return"0 MB/s";const mb=n/1024/1024;return(mb<0.1?mb.toFixed(2):mb.toFixed(1))+" MB/s";}

async function poll(){
  if(!job)return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){msg.textContent="Job expired.";job=null;return;}
    const p=await r.json();
    const pct=Math.max(0,Math.min(100,p.percent||0));
    bar.style.width=pct+"%";
    pctTxt.textContent=pct+"%";
    speedTxt.textContent=fmtBytes(p.speed_bytes);
    if(p.status==="finished"){msg.textContent="✅ Done — preparing file...";window.location="/fetch/"+job;job=null;return;}
    else if(p.status==="error"){msg.textContent="❌ "+(p.error||"Download failed");job=null;return;}
    setTimeout(poll,700);
  }catch(e){msg.textContent="Network error";job=null;}
}
</script>
</body>
</html>
"""

JOBS = {}

class Job:
    def __init__(self):
        self.id=str(uuid.uuid4())
        self.tmp=tempfile.mkdtemp(prefix="mvd_")
        self.percent=0;self.status="queued";self.file=None;self.error=None;self.speed_bytes=0.0
        JOBS[self.id]=self

YTDLP_URL_RE=re.compile(r"^https?://",re.I)
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
        if not YTDLP_URL_RE.match(url): job.status="error"; job.error="Invalid URL"; return
        fmt=format_map_for_env().get(fmt_key)
        def hook(d):
            if d.get("status")=="downloading":
                total=d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                job.percent=int((d.get("downloaded_bytes",0)*100)/total)
                job.speed_bytes=d.get("speed") or 0
            elif d.get("status")=="finished": job.percent=100
        base=(filename.strip() if filename else "%(title)s").rstrip(".")
        out=os.path.join(job.tmp,base+".%(ext)s")
        opts={"format":fmt,"outtmpl":out,"merge_output_format":"mp4","cookiefile":"cookies.txt","progress_hooks":[hook],"quiet":True,"noplaylist":True}
        if HAS_FFMPEG:
            opts["ffmpeg_location"]=ffmpeg_path()
            if fmt_key=="audio_mp3":
                opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]
        with YoutubeDL(opts) as y: y.extract_info(url,download=True)
        files=glob.glob(job.tmp+"/*");job.file=max(files,key=os.path.getsize);job.status="finished"
    except Exception as e:
        job.status="error";job.error=str(e)[:200]

@app.post("/start")
def start():
    d=request.json;job=Job()
    threading.Thread(target=run_download,args=(job,d["url"],d["format_choice"],d.get("filename")),daemon=True).start()
    return jsonify({"job_id":job.id})

@app.post("/info")
def info():
    d=request.json;url=d.get("url")
    try:
        with YoutubeDL({"skip_download":True,"quiet":True,"noplaylist":True,"cookiefile":"cookies.txt"}) as y:
            info=y.extract_info(url,download=False)
        title=info.get("title","")
        channel=info.get("uploader") or info.get("channel","")
        thumb=info.get("thumbnail")
        dur=info.get("duration") or 0
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}"})
    except: return jsonify({"error":"Preview failed"}),400

@app.get("/progress/<id>")
def progress(id):
    j=JOBS.get(id)
    if not j: abort(404)
    return jsonify({"percent":j.percent,"status":j.status,"error":j.error,"speed_bytes":j.speed_bytes})

@app.get("/fetch/<id>")
def fetch(id):
    j=JOBS.get(id)
    if not j: abort(404)
    resp=send_file(j.file,as_attachment=True,download_name=os.path.basename(j.file))
    threading.Thread(target=lambda:(shutil.rmtree(j.tmp,ignore_errors=True),JOBS.pop(id,None)),daemon=True).start()
    return resp

@app.get("/env")
def env(): return jsonify({"ffmpeg":HAS_FFMPEG})

@app.get("/")
def home(): return render_template_string(HTML)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
