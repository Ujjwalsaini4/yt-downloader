# -*- coding: utf-8 -*-
import os, tempfile, shutil, glob, threading, uuid, re, time, json
from flask import Flask, request, jsonify, send_file, render_template_string, abort
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Save cookies if provided in env
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (UI) ----------
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>💎 Hyper Downloader</title>
<style>
:root{
  --bg:#0b0f19; --card:#0f1724; --text:#e6eefc; --muted:#97a6b2;
  --border:#192230; --grad-1:#8b5cf6; --grad-2:#06b6d4; --grad:linear-gradient(90deg,var(--grad-1),var(--grad-2));
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Noto Sans",sans-serif}
.wrap{max-width:920px;margin:auto;padding:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;box-shadow:0 8px 30px rgba(0,0,0,.28);margin-top:16px}
.header{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:44px;height:44px;border-radius:12px;background:var(--grad);display:grid;place-items:center;font-weight:800;color:#fff;box-shadow:0 6px 18px rgba(0,0,0,.28);font-size:18px}
.brand{font-size:20px;font-weight:800;display:flex;align-items:center;gap:8px}
.brand span{background:var(--grad);-webkit-background-clip:text;color:transparent}
nav{display:flex;align-items:center;gap:10px}
nav a{color:var(--muted);text-decoration:none;font-weight:600;padding:6px 8px;border-radius:10px}
nav a.btn{background:var(--grad);color:#fff;padding:8px 14px;box-shadow:0 8px 24px rgba(107,60,246,.18);font-weight:800}
.lead{color:var(--muted);margin-top:6px;margin-bottom:8px;font-size:14px}

/* form */
form{display:grid;gap:12px;margin-top:10px}
label{display:block;color:var(--muted);font-size:13px;margin-bottom:6px}
input,select,button{width:100%;padding:12px;border-radius:10px;border:1px solid var(--border);background:#081223;color:var(--text);font-size:15px}
input::placeholder{color:#546171}
button{background:var(--grad);color:#fff;border:none;font-weight:800;cursor:pointer;padding:12px;border-radius:10px;transition:transform .08s}
button:active{transform:scale(.99)}
button:disabled{opacity:.6;cursor:not-allowed}

/* progress with centered percent */
.progress{position:relative;width:100%;height:14px;background:#0b1623;border-radius:999px;overflow:hidden;margin-top:10px;border:1px solid rgba(255,255,255,0.02)}
.bar{position:absolute;left:0;top:0;bottom:0;width:0%;background:var(--grad);transition:width .24s ease;z-index:1}
.pct{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:inline-grid;place-items:center;font-weight:800;color:#fff;font-size:13px;z-index:3;pointer-events:none;white-space:nowrap;text-shadow:0 1px 0 rgba(0,0,0,0.6)}
.footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;color:var(--muted);font-size:13px}

/* job small info row */
.job-info{display:flex;gap:10px;align-items:center;margin-top:8px;color:var(--muted);font-size:13px}
.job-info .jid{background:#101826;padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,0.02)}
.job-info button{padding:6px 8px;border-radius:8px;border:1px solid rgba(255,255,255,0.03);background:transparent;color:var(--muted);cursor:pointer}

/* preview */
.preview{display:none;margin-top:12px;background:#07101a;padding:10px;border-radius:10px;border:1px solid var(--border)}
.preview-row{display:flex;gap:12px;align-items:center}
.thumb{width:100px;aspect-ratio:16/9;border-radius:8px;object-fit:cover;background:#0a0a0a}
.meta .title{font-weight:800;font-size:14px;margin-bottom:4px}
.meta .sub{color:var(--muted);font-size:13px}

/* responsive */
@media (max-width:640px){
  .wrap{padding:12px}
  .card{padding:12px}
  .logo-icon{width:38px;height:38px;font-size:15px}
  .brand{font-size:18px}
  h2{font-size:19px}
  input,select,button{padding:10px;font-size:14px}
  .progress{height:10px}
  .pct{font-size:12px}
  .footer{font-size:12px}
  .thumb{width:86px}
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
        <a href="#" class="btn">Go Premium</a>
      </nav>
    </header>

    <section class="card" aria-labelledby="downloadTitle">
      <h2 id="downloadTitle">⬇️ Download from YouTube</h2>
      <p class="lead">🎬 Paste your video link, preview it, choose quality, and start download.</p>

      <div id="preview" class="preview" aria-live="polite">
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
        <div style="display:flex;gap:8px;align-items:center">
          <button id="goBtn" type="submit">⚡ Start Download</button>
          <label style="color:var(--muted);font-size:13px"><input id="detach" type="checkbox" style="margin-right:6px"> Run in background</label>
        </div>
      </form>

      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100">
        <div id="bar" class="bar"></div>
        <div id="pctTxt" class="pct">0%</div>
      </div>

      <div class="footer"><span id="msg"></span><span id="speedTxt">0 MB/s</span></div>

      <!-- small job info + resume -->
      <div class="job-info" id="jobInfo" style="display:none">
        <div>Job:</div>
        <div class="jid" id="jobId">—</div>
        <button id="resumeBtn" style="display:none">Resume</button>
        <button id="clearBtn" style="display:none">Clear</button>
      </div>
    </section>

    <section id="features" class="card">
      <h2>💎 Premium Features</h2>
      <ul>
        <li>4K + MP3 download support</li>
        <li>Progress bar with percent & speed</li>
        <li>Resume from other tab (job-id stored locally)</li>
      </ul>
    </section>

    <section id="faq" class="card">
      <h2>❓ FAQ</h2>
      <p>If options are disabled, server may not have FFmpeg installed.</p>
    </section>
  </div>

<script>
/*
  Client behavior:
  - Save job_id to localStorage when detached or always (so user can reopen later).
  - Warn beforeunload only while a job is running AND "Run in background" is NOT checked.
  - Provide Resume button if a job_id exists in localStorage and job still running.
*/

let job=null, HAS_FFMPEG=false;
const bar=document.getElementById("bar"), pctTxt=document.getElementById("pctTxt");
const msg=document.getElementById("msg"), speedTxt=document.getElementById("speedTxt");
const preview=document.getElementById("preview"), thumb=document.getElementById("thumb");
const pTitle=document.getElementById("pTitle"), pSub=document.getElementById("pSub");
const jobInfo=document.getElementById("jobInfo"), jobIdEl=document.getElementById("jobId");
const resumeBtn=document.getElementById("resumeBtn"), clearBtn=document.getElementById("clearBtn");
const detachCheckbox=document.getElementById("detach");

const LOCAL_KEY = "hd_last_job"; // store job id

// Get environment (ffmpeg)
fetch("/env").then(r=>r.json()).then(j=>{
  HAS_FFMPEG=!!j.ffmpeg;
  if(!HAS_FFMPEG){ msg.textContent="⚠️ FFmpeg not found — MP3/merge disabled."; msg.style.color="#f59e0b"; }
}).catch(()=>{});

// Helper: format bytes -> MB/s
function fmtBytes(n){
  if(!n) return "0 MB/s";
  const mb = n/1024/1024;
  return (mb<0.1?mb.toFixed(2):mb.toFixed(1))+" MB/s";
}

// Fetch preview info (debounced)
let _deb=null;
document.getElementById("url").addEventListener("input", ()=>{
  clearTimeout(_deb);
  const url=document.getElementById("url").value.trim();
  if(!/^https?:\/\//i.test(url)){ preview.style.display="none"; return; }
  _deb=setTimeout(()=>fetchInfo(url), 500);
});
async function fetchInfo(url){
  try{
    const r=await fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});
    const j=await r.json();
    if(!r.ok || j.error){ preview.style.display="none"; return; }
    pTitle.textContent=j.title||"";
    pSub.textContent=[j.channel,j.duration_str].filter(Boolean).join(" • ");
    if(j.thumbnail){ thumb.src=j.thumbnail; thumb.alt=j.title; }
    preview.style.display="block";
  }catch(e){ preview.style.display="none"; }
}

// Beforeunload warning (only when job running AND not detached)
window.addEventListener("beforeunload", (e)=>{
  // if a job running and user did not choose detach, warn
  const running = job != null;
  const detached = detachCheckbox.checked;
  if(running && !detached){
    e.preventDefault();
    e.returnValue = "A download is in progress. Are you sure you want to leave?";
    return "A download is in progress. Are you sure you want to leave?";
  }
});

// Start/resume/clear UI
function showJobUI(jid){
  jobInfo.style.display="flex";
  jobIdEl.textContent = jid;
  resumeBtn.style.display = "inline-block";
  clearBtn.style.display = "inline-block";
  localStorage.setItem(LOCAL_KEY, jid);
}
function clearJobUI(){
  jobInfo.style.display="none";
  jobIdEl.textContent="—";
  resumeBtn.style.display="none";
  clearBtn.style.display="none";
  localStorage.removeItem(LOCAL_KEY);
}

// Resume handler (if user opens another tab)
resumeBtn.addEventListener("click", ()=>{
  const saved = localStorage.getItem(LOCAL_KEY);
  if(!saved) return;
  job = saved;
  msg.textContent = "Resumed job " + job;
  poll();
});
clearBtn.addEventListener("click", ()=>{
  clearJobUI();
  job = null;
  msg.textContent = "";
});

// Auto-check localStorage on load to resume
window.addEventListener("load", ()=>{
  const saved = localStorage.getItem(LOCAL_KEY);
  if(saved){
    // show info and allow immediate resume
    showJobUI(saved);
    // auto-resume polling in background (do not force open file)
    job = saved;
    msg.textContent = "Resuming job " + job;
    poll();
  }
});

// Form submit
document.getElementById("frm").addEventListener("submit", async (e)=>{
  e.preventDefault();
  msg.style.color = "";
  msg.textContent = "⏳ Starting download...";
  const url=document.getElementById("url").value.trim();
  const fmt=document.getElementById("format").value;
  const name=document.getElementById("name").value.trim();
  const detached = detachCheckbox.checked;

  if(!/^https?:\/\//i.test(url)){ msg.textContent="Please paste a valid URL."; msg.style.color="#fb7185"; return; }

  try{
    const r = await fetch("/start", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({url, format_choice: fmt, filename: name})});
    const j = await r.json();
    if(!r.ok){ throw new Error(j.error || "Failed to start"); }
    job = j.job_id;
    // show job id / save if detached
    showJobUI(job);
    if(detached) localStorage.setItem(LOCAL_KEY, job);
    msg.textContent = "Download started — job id " + job;
    // begin polling
    poll();
  }catch(err){
    msg.textContent = "Error starting download: " + (err.message||err);
    msg.style.color="#fb7185";
  }
});

// Polling function (updates UI even if client throttled)
// Note: even if polling slows in background, server download continues independently.
async function poll(){
  if(!job) return;
  try{
    const r = await fetch("/progress/" + job);
    if(r.status === 404){
      msg.textContent = "Job expired or not found.";
      job = null;
      // keep job-id in localStorage so user can inspect later if desired
      return;
    }
    const p = await r.json();
    const pct = Math.max(0, Math.min(100, p.percent || 0));

    // update bar first then percent (keeps centered)
    bar.style.width = pct + "%";
    pctTxt.textContent = pct + "%";

    speedTxt.textContent = p.speed_bytes ? fmtBytes(p.speed_bytes) : "0 MB/s";

    if(p.status === "finished"){
      msg.textContent = "✅ Done — preparing file...";
      // clear job localStorage (user can still fetch via the download link when ready)
      // but do not automatically clear job UI - let user keep ID for record
      localStorage.removeItem(LOCAL_KEY);
      // redirect to fetch file automatically:
      window.location = "/fetch/" + job;
      job = null;
      return;
    } else if(p.status === "error"){
      msg.textContent = "❌ " + (p.error || "Download failed");
      job = null;
      return;
    }

    // schedule next poll; when tab is backgrounded browser may throttle timers
    // but server download keeps running.
    setTimeout(poll, 800);
  }catch(e){
    msg.textContent = "Network error";
    job = null;
  }
}
</script>
</body>
</html>
"""

# ---------- Server side jobs ----------
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
        self._lock = threading.Lock()
        JOBS[self.id] = self

# simple url check
YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    if HAS_FFMPEG:
        return {
            "mp4_720": "bestvideo[height<=720]+bestaudio/best",
            "mp4_1080": "bestvideo[height<=1080]+bestaudio/best",
            "mp4_best": "bestvideo+bestaudio/best",
            "audio_mp3": "bestaudio/best"
        }
    else:
        return {
            "mp4_720": "best[ext=mp4][height<=720]/best[ext=mp4]",
            "mp4_1080": "best[ext=mp4][height<=1080]/best[ext=ext=mp4]",
            "mp4_best": "best[ext=mp4]/best",
            "audio_mp3": None
        }

def run_download(job, url, fmt_key, filename):
    """
    Run yt-dlp download in a background thread. Updates job.percent and job.speed_bytes.
    This thread is independent of the client's tab; even if client disconnects, this keeps running
    as long as the process is alive on the server.
    """
    try:
        if not YTDLP_URL_RE.match(url):
            job.status = "error"; job.error = "Invalid URL"; return

        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status = "error"; job.error = "Selected format requires FFmpeg"; return

        def hook(d):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                    downloaded = d.get("downloaded_bytes", 0)
                    with job._lock:
                        job.percent = max(0, min(100, int((downloaded * 100) / total)))
                        job.speed_bytes = d.get("speed") or 0.0
                elif d.get("status") == "finished":
                    with job._lock:
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

        # remove None values
        opts = {k: v for k, v in opts.items() if v is not None}

        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            if fmt_key == "audio_mp3":
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(job.tmp + "/*")
        job.file = max(files, key=os.path.getsize) if files else None
        job.status = "finished"
    except Exception as e:
        job.status = "error"
        job.error = str(e)[:300]

# ---------- Routes ----------
@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

@app.post("/start")
def start():
    d = request.json or {}
    url = d.get("url", "")
    fmt = d.get("format_choice", "mp4_best")
    filename = d.get("filename")
    job = Job()
    # start background thread (non-daemon) so it survives if main thread temporarily busy
    t = threading.Thread(target=run_download, args=(job, url, fmt, filename))
    t.daemon = True  # keep as daemon so server can exit cleanly; thread runs while process alive
    t.start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url", "")
    try:
        with YoutubeDL({"skip_download": True, "quiet": True, "noplaylist": True, "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None}) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title", "")
        channel = info.get("uploader") or info.get("channel", "")
        thumb = info.get("thumbnail")
        dur = info.get("duration") or 0
        return jsonify({"title": title, "thumbnail": thumb, "channel": channel, "duration_str": f"{dur//60}:{dur%60:02d}"})
    except Exception:
        return jsonify({"error": "Preview failed"}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    return jsonify({
        "percent": j.percent,
        "status": j.status,
        "error": j.error,
        "speed_bytes": j.speed_bytes
    })

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j:
        abort(404)
    if not j.file or not os.path.exists(j.file):
        return jsonify({"error": "File not ready"}), 400
    resp = send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    # cleanup in background
    threading.Thread(target=lambda: (shutil.rmtree(j.tmp, ignore_errors=True), JOBS.pop(id, None)), daemon=True).start()
    return resp

@app.get("/")
def home():
    return render_template_string(HTML)

# Run app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
