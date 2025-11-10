import os
from flask import Flask, request, jsonify, send_file, render_template_string, abort
import tempfile, shutil, glob, threading, uuid, re
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ✅ Write cookies from Render Environment Variable → cookies.txt
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

# ---------- FFmpeg Detection ----------
def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg" or "/data/data/com.termux/files/usr/bin/ffmpeg"

HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML UI (UNCHANGED) ----------
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Mobile Video Downloader</title>
<style>
  :root{
    --bg:#eef2f7; --card:#fff; --text:#0f172a; --muted:#475569; --border:#cbd5e1;
    --primary:#0077ff; --accent:#00ffaa;
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#0b1220; --card:#0f172a; --text:#e6eefc; --muted:#9fb0c8; --border:#263143;
      --primary:#4da3ff; --accent:#48f7b7; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Noto Sans",sans-serif; padding:clamp(12px,2vw,24px)}
  .wrap{max-width:min(960px,100%);margin-inline:auto}
  .box{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:0 6px 24px rgba(0,0,0,.08);padding:clamp(16px,3vw,28px)}
  h2{margin:0 0 6px;font-size:clamp(18px,2.6vw,28px)}
  .lead{margin:0 0 14px;color:var(--muted);font-size:clamp(13px,1.8vw,15.5px)}

  form{display:grid;gap:12px}
  .grid{display:grid;gap:10px;grid-template-columns:1fr}
  @media (min-width:600px){ .grid{grid-template-columns:2fr 1fr 1.2fr} .full{grid-column:1 / -1} }
  @media (min-width:880px){ .grid{grid-template-columns:2.2fr 1fr 1.2fr auto;align-items:end} #goBtn{min-width:140px} }

  label{display:block;margin-bottom:6px;font-size:13px;color:var(--muted)}
  input,select,button{
    width:100%;padding:14px 12px;border-radius:12px;border:1px solid var(--border);
    background:transparent;color:var(--text);font-size:16px
  }
  input::placeholder{color:color-mix(in oklab, var(--muted) 70%, transparent)}
  select{appearance:none;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 22px) 18px, calc(100% - 12px) 18px;background-size:10px 10px, 10px 10px;background-repeat:no-repeat;}
  button{border:none;background:var(--primary);color:#fff;font-weight:700;cursor:pointer;transition:transform .04s ease,opacity .2s ease}
  button:active{transform:scale(.98)}
  button[disabled]{opacity:.6;cursor:not-allowed}

  .progress{width:100%;height:14px;background:color-mix(in oklab, var(--border) 65%, transparent);border-radius:999px;overflow:hidden}
  .bar{height:100%;width:0;background:linear-gradient(90deg,var(--primary),var(--accent));transition:width .25s ease}
  #msg{min-height:1.2em;font-size:14px}
  .tip{color:var(--muted);font-size:13px}

  .preview{display:none; margin:8px 0 4px; border:1px solid var(--border); border-radius:14px; overflow:hidden; background:var(--card)}
  .preview-row{display:flex; gap:12px; padding:10px; align-items:center}
  .thumb{width:120px; aspect-ratio:16/9; border-radius:10px; object-fit:cover; background:#ddd}
  .meta{min-width:0}
  .title{font-size:15px; font-weight:700; margin:0 0 4px; line-height:1.3}
  .sub{font-size:13px; color:var(--muted); margin:0}
  @media (max-width:480px){ .thumb{width:104px} }
</style>
</head>
<body>
  <main class="wrap">
    <section class="box">
      <h2>📥 Mobile Video Downloader</h2>
      <p class="lead">Paste a YouTube link, see preview, pick format, and download.</p>

      <div id="preview" class="preview" aria-live="polite">
        <div class="preview-row">
          <img id="thumb" class="thumb" alt="Thumbnail preview">
          <div class="meta">
            <p id="pTitle" class="title"></p>
            <p id="pSub" class="sub"></p>
          </div>
        </div>
      </div>

      <form id="frm">
        <div class="grid">
          <div>
            <label for="url">Video URL</label>
            <input id="url" inputmode="url" placeholder="https://www.youtube.com/watch?v=..." required>
          </div>

          <div>
            <label for="format">Format</label>
            <select id="format">
              <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
              <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
              <option value="mp4_best">4K MP4</option>
              <option value="audio_mp3" data-need-ffmpeg="1">Audio MP3 Only</option>
            </select>
          </div>

          <div>
            <label for="name">Filename (optional)</label>
            <input id="name" placeholder="My video">
          </div>

          <div class="full">
            <button id="goBtn" type="submit">Download</button>
          </div>
        </div>

        <div style="margin-top:12px">
          <div class="progress" role="progressbar" aria-label="Download progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div id="bar" class="bar"></div>
          </div>
        </div>

        <p id="msg" role="status" aria-live="polite"></p>
        <p class="tip">Tip: Same Wi-Fi/LAN. If high-quality merge fails, install FFmpeg in Termux.</p>
      </form>
    </section>
  </main>

<script>
let job=null, debounceTimer=null, HAS_FFMPEG=false;
const frm = document.getElementById("frm");
const bar = document.getElementById("bar");
const msg = document.getElementById("msg");
const btn = document.getElementById("goBtn");
const pbar = document.querySelector(".progress");
const urlIn = document.getElementById("url");
const preview = document.getElementById("preview");
const pTitle = document.getElementById("pTitle");
const pSub = document.getElementById("pSub");
const thumb = document.getElementById("thumb");
const formatSel = document.getElementById("format");

fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG = !!j.ffmpeg;
  if(!HAS_FFMPEG){
    [...formatSel.options].forEach(o=>{
      if(o.dataset.needFfmpeg==="1"){ o.disabled = true; }
    });
    setMsg("FFmpeg not found: using single-file MP4.", false);
  }
}).catch(()=>{});

function setMsg(t, isErr=false){ msg.style.color = isErr ? "#b91c1c" : "inherit"; msg.textContent = t || ""; }
function setBusy(b){ btn.disabled = b; pbar.style.opacity = b ? "1" : ".7"; }
function hidePreview(){ preview.style.display="none"; thumb.removeAttribute("src"); pTitle.textContent=""; pSub.textContent=""; }
function showPreview(d){
  if(!d||!d.title){ hidePreview(); return; }
  pTitle.textContent = d.title||"";
  pSub.textContent = [d.channel,d.duration_str].filter(Boolean).join(" • ");
  if(d.thumbnail){ thumb.src=d.thumbnail; thumb.alt=d.title; }
  preview.style.display="block";
}

urlIn.addEventListener("input", ()=>{
  clearTimeout(debounceTimer);
  const url = urlIn.value.trim();
  if(!/^https?:\/\//i.test(url)){ hidePreview(); return; }
  debounceTimer = setTimeout(()=>fetchInfo(url), 500);
});

async function fetchInfo(url){
  try{
    const r = await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j = await r.json();
    if(!r.ok || j.error){ hidePreview(); return; }
    showPreview(j); setMsg("");
  }catch(e){ hidePreview(); }
}

frm.addEventListener("submit", async (e)=>{
  e.preventDefault();
  setMsg(""); setBusy(true); bar.style.width="0%"; document.querySelector(".progress").setAttribute("aria-valuenow","0");

  const url = urlIn.value.trim();
  const fmt = formatSel.value;
  const name = document.getElementById("name").value.trim();

  if(!/^https?:\/\//i.test(url)){
    setMsg("Please paste a valid URL.", true); setBusy(false); return;
  }

  try{
    const r = await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url, format_choice:fmt, filename:name})});
    const j = await r.json();
    if(!r.ok){ throw new Error(j.error||"Failed to start"); }
    job = j.job_id; setMsg("Downloading…"); poll();
  }catch(err){
    setMsg(err.message||"Error starting download.", true);
    setBusy(false);
  }
});

async function poll(){
  if(!job) return;
  try{
    const r = await fetch("/progress/"+job);
    if(r.status===404){ setMsg("Job expired.", true); setBusy(false); job=null; return; }
    const p = await r.json();
    const pct = Math.max(0, Math.min(100, p.percent||0));
    bar.style.width = pct + "%"; document.querySelector(".progress").setAttribute("aria-valuenow", String(pct));
    if(p.status==="finished"){ setMsg("Done! Preparing file…"); setBusy(false); window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ setMsg(p.error||"Download failed.", true); setBusy(false); job=null; return; }
    setTimeout(poll, 700);
  }catch(e){
    setMsg("Network error.", true); setBusy(false); job=null;
  }
}
</script>
</body>
</html>
"""

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

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error"; job.error="Invalid URL"; return

        fmt = format_map_for_env()[fmt_key]

        def hook(d):
            if d.get("status")=="downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                job.percent = int((d.get("downloaded_bytes",0) * 100) / total)
            elif d.get("status")=="finished":
                job.percent = 100

        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        out = os.path.join(job.tmp, base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": out,
            "merge_output_format": "mp4",
            "cookiefile": "cookies.txt",
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True
        }

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(job.tmp + "/*")
        job.file = max(files, key=os.path.getsize)
        job.status = "finished"

    except Exception as e:
        job.status="error"; job.error=str(e)[:200]

# ---------- Routes ----------
@app.post("/start")
def start():
    d = request.json
    job = Job()
    threading.Thread(target=run_download, args=(job, d["url"], d["format_choice"], d.get("filename")), daemon=True).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json
    url = d["url"]
    try:
        with YoutubeDL({"skip_download":True,"quiet":True,"noplaylist":True,"cookiefile":"cookies.txt"}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title","")
        channel = info.get("uploader") or info.get("channel","")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":f"{dur//60}:{dur%60:02d}"})
    except:
        return jsonify({"error":"Preview failed"}),400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j: abort(404)
    return jsonify({"percent": j.percent, "status": j.status, "error": j.error})

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j: abort(404)
    resp = send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    threading.Thread(target=lambda: (shutil.rmtree(j.tmp, ignore_errors=True), JOBS.pop(id,None)), daemon=True).start()
    return resp

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
