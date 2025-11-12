# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify, send_file, render_template_string, abort
import tempfile, shutil, glob, threading, uuid, re, time
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Save cookies from environment variable -> cookies.txt
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
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>💎 Hyper Downloader</title>

<style>
:root{
  --bg:#0b0f19;
  --card:#121827;
  --text:#e5e7eb;
  --muted:#9ca3af;
  --border:#1f2937;
  --grad:linear-gradient(90deg,#8b5cf6,#06b6d4);
  --accent:#8b5cf6;
}
body{
  margin:0;
  font-family: 'Inter',system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;
  background:var(--bg);
  color:var(--text);
  padding:16px;
}
.wrap{max-width:820px;margin:auto;}
h1,h2{margin:0;font-weight:800;}
h1 span{background:var(--grad);-webkit-background-clip:text;color:transparent;}
p{margin:0;}
a{text-decoration:none;color:inherit;}
.card{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:16px;
  padding:20px;
  box-shadow:0 8px 20px rgba(0,0,0,.2);
  margin-top:18px;
}

/* HEADER */
.header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:20px;}
.logo{display:flex;align-items:center;gap:10px;}
.logo-icon{
  width:46px;height:46px;border-radius:12px;background:var(--grad);
  display:grid;place-items:center;font-weight:800;font-size:18px;color:#fff;
  box-shadow:0 6px 18px rgba(0,0,0,.3);
}
.brand{font-size:22px;font-weight:800;}
nav a{margin-left:14px;font-weight:500;color:var(--muted);}
nav a:hover{color:#fff;}
.btn-premium{
  padding:10px 16px;
  border-radius:12px;
  background:var(--grad);
  color:#fff;
  font-weight:700;
  box-shadow:0 0 20px rgba(139,92,246,.5);
}

/* FORM */
form{display:grid;gap:14px;}
label{font-size:14px;color:var(--muted);}
input,select,button{
  width:100%;padding:12px 12px;border-radius:10px;border:1px solid var(--border);
  background:#0f172a;color:#fff;font-size:15px;
}
input::placeholder{color:#64748b;}
button{
  background:var(--grad);font-weight:700;color:#fff;border:none;cursor:pointer;
  transition:transform .1s ease;
}
button:hover{transform:scale(1.03);}
button:disabled{opacity:.6;cursor:not-allowed;}

/* PROGRESS BAR */
.progress{
  width:100%;height:16px;border-radius:999px;overflow:hidden;background:#1e293b;margin-top:10px;
  position:relative;
}
.bar{
  position:absolute;left:0;top:0;bottom:0;width:0%;
  background:var(--grad);
  transition:width .3s ease;
}
.pct{position:absolute;inset:0;display:grid;place-items:center;font-size:13px;font-weight:700;color:#fff;}

/* FOOTER INFO */
.footer{display:flex;justify-content:space-between;align-items:center;font-size:14px;margin-top:8px;color:var(--muted);}

/* PREVIEW */
.preview{display:none;margin:12px 0;padding:10px;border-radius:10px;background:#0f172a;border:1px solid var(--border);}
.preview-row{display:flex;gap:10px;align-items:center;}
.thumb{width:110px;aspect-ratio:16/9;object-fit:cover;border-radius:8px;}
.meta p{margin:0;}
.title{font-weight:700;font-size:15px;}
.sub{font-size:13px;color:var(--muted);}

/* RESPONSIVE */
@media(max-width:640px){
  .brand{font-size:18px;}
  .logo-icon{width:40px;height:40px;font-size:16px;}
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
        <a href="#" class="btn-premium">Go Premium</a>
      </nav>
    </header>

    <div class="card">
      <h2>⬇️ Download from YouTube</h2>
      <p style="color:var(--muted);margin-top:6px;">🎬 Paste your video link, preview it, choose quality, and hit download.</p>

      <div id="preview" class="preview">
        <div class="preview-row">
          <img id="thumb" class="thumb" alt="">
          <div class="meta">
            <p id="pTitle" class="title"></p>
            <p id="pSub" class="sub"></p>
          </div>
        </div>
      </div>

      <form id="frm">
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
        <div>
          <button id="goBtn" type="submit">⚡ Start Download</button>
        </div>
      </form>

      <div class="progress"><div id="bar" class="bar"></div><div class="pct" id="pctTxt">0%</div></div>
      <div class="footer"><span id="msg"></span><span id="speedTxt">0 MB/s</span></div>
    </div>

    <div id="features" class="card">
      <h2>💎 Premium Features</h2>
      <ul>
        <li>4K + MP3 download support</li>
        <li>Progress bar with speed</li>
        <li>Beautiful gradient UI</li>
        <li>Fully mobile responsive</li>
      </ul>
    </div>

    <div id="faq" class="card">
      <h2>❓ FAQ</h2>
      <p>If options are greyed out, FFmpeg is not installed on your server.</p>
    </div>
  </div>

<script>
let job=null, HAS_FFMPEG=false;
const bar=document.getElementById("bar"),pctTxt=document.getElementById("pctTxt"),msg=document.getElementById("msg"),speedTxt=document.getElementById("speedTxt");

fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG=!!j.ffmpeg;
  if(!HAS_FFMPEG){msg.textContent="⚠️ FFmpeg missing. Using simple MP4.";msg.style.color="#fbbf24";}
});

document.getElementById("frm").addEventListener("submit",async e=>{
  e.preventDefault();
  msg.textContent="⏳ Starting download...";
  const url=document.getElementById("url").value.trim(),fmt=document.getElementById("format").value,name=document.getElementById("name").value.trim();
  const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
  const j=await r.json();job=j.job_id;poll();
});
async function poll(){
  if(!job)return;
  const r=await fetch("/progress/"+job);
  const p=await r.json();
  bar.style.width=p.percent+"%";
  pctTxt.textContent=p.percent+"%";
  speedTxt.textContent=(p.speed_bytes?(p.speed_bytes/1024/1024).toFixed(1)+" MB/s":"—");
  if(p.status==="finished"){msg.textContent="✅ Done! Preparing file...";window.location="/fetch/"+job;job=null;}
  else if(p.status==="error"){msg.textContent="❌ "+p.error;job=null;}
  else setTimeout(poll,800);
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
        self.percent=0;self.status="queued"
        self.file=None;self.error=None
        self.speed_bytes=0.0
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
        fmt=format_map_for_env().get(fmt_key)
        def hook(d):
            if d.get("status")=="downloading":
                total=d.get("total_bytes") or 1
                job.percent=int((d.get("downloaded_bytes",0)*100)/total)
                job.speed_bytes=d.get("speed") or 0
            elif d.get("status")=="finished": job.percent=100
        base=(filename.strip() if filename else "%(title)s").rstrip(".")
        out=os.path.join(job.tmp,base+".%(ext)s")
        opts={"format":fmt,"outtmpl":out,"merge_output_format":"mp4","progress_hooks":[hook],"quiet":True}
        if HAS_FFMPEG: opts["ffmpeg_location"]=ffmpeg_path()
        with YoutubeDL(opts) as y: y.extract_info(url,download=True)
        files=glob.glob(job.tmp+"/*");job.file=max(files,key=os.path.getsize);job.status="finished"
    except Exception as e: job.status="error";job.error=str(e)

@app.post("/start")
def start():
    d=request.json;job=Job()
    threading.Thread(target=run_download,args=(job,d["url"],d["format_choice"],d.get("filename")),daemon=True).start()
    return jsonify({"job_id":job.id})

@app.get("/progress/<id>")
def progress(id):
    j=JOBS.get(id); 
    if not j: abort(404)
    return jsonify({"percent":j.percent,"status":j.status,"error":j.error,"speed_bytes":j.speed_bytes})

@app.get("/fetch/<id>")
def fetch(id):
    j=JOBS.get(id); 
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
