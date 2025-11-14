# app.py
# -*- coding: utf-8 -*-
# Hyper Downloader - patched version (audio & mobile download fixes included)
# Works with yt-dlp + ffmpeg if available.

import os
import time
import tempfile
import shutil
import glob
import threading
import uuid
import re
import mimetypes
from flask import Flask, request, jsonify, render_template_string, abort, send_file, make_response
from shutil import which
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Save cookies if present (from environment)
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)

def ffmpeg_path():
    return which("ffmpeg") or "/usr/bin/ffmpeg"
HAS_FFMPEG = os.path.exists(ffmpeg_path())

# ---------- HTML (UI kept as requested) ----------
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
  --pill-bg: rgba(255,255,255,0.03);
  --pill-border: rgba(255,255,255,0.06);
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

/* Status row: message left, ETA pill right */
.status-row{
  display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:12px;
}
.status-left{color:var(--muted);font-size:13px;display:flex;align-items:center;gap:8px;}
.eta-pill{
  display:inline-flex;align-items:center;gap:10px;padding:8px 12px;border-radius:999px;
  background:var(--pill-bg);border:1px solid var(--pill-border);font-weight:700;font-size:13px;color:#fff;
  min-width:90px;justify-content:center;
  box-shadow:0 6px 18px rgba(6,182,212,0.06);
}
/* make ETA number monospaced-ish */
.eta-pill .label{opacity:0.85;color:var(--muted);font-weight:600;font-size:12px;margin-right:6px}
.eta-pill .value{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Roboto Mono,monospace;font-weight:800}

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

footer{margin-top:20px;text-align:center;color:var(--muted);font-size:12px;}
/* responsive tweaks */
@media(max-width:520px){
  .eta-pill{min-width:72px;padding:6px 10px;font-size:12px}
  .brand-title h1{font-size:18px}
}
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
          <optgroup label="Video (MP4)">
            <option value="mp4_144" data-need-ffmpeg="0">144p MP4</option>
            <option value="mp4_240" data-need-ffmpeg="0">240p MP4</option>
            <option value="mp4_360" data-need-ffmpeg="0">360p MP4</option>
            <option value="mp4_480" data-need-ffmpeg="0">480p MP4</option>
            <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
            <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
          </optgroup>
          <optgroup label="Audio">
            <option value="audio_mp3_128" data-need-ffmpeg="1">MP3 — 128 kbps</option>
            <option value="audio_mp3_192" data-need-ffmpeg="1">MP3 — 192 kbps</option>
            <option value="audio_mp3_320" data-need-ffmpeg="1">MP3 — 320 kbps</option>
            <option value="audio_best" data-need-ffmpeg="0">Best audio (original)</option>
          </optgroup>
        </select>
      </div>
      <div><label>Filename</label><input id="name" placeholder="My video"></div>
      <div class="full"><button id="goBtn" type="submit">⚡ Start Download</button></div>
    </div>
  </form>

  <div class="progress"><div id="bar" class="bar"></div><div id="pct" class="pct">0%</div></div>

  <!-- status row: left = message, right = ETA pill -->
  <div class="status-row" aria-live="polite">
    <div id="msg" class="status-left">—</div>
    <div id="eta" class="eta-pill"><span class="label">ETA:</span><span class="value">--</span></div>
  </div>
</main>

<footer>© 2025 Hyper Downloader — Auto cleanup & responsive UI</footer>
</div>

<script>
let job=null;
const bar=document.getElementById("bar"),pct=document.getElementById("pct");
const msg=document.getElementById("msg");
const etaEl=document.getElementById("eta");
const etaVal=document.querySelector("#eta .value");
const urlIn=document.getElementById("url"),thumb=document.getElementById("thumb"),preview=document.getElementById("preview"),pTitle=document.getElementById("pTitle"),pSub=document.getElementById("pSub");

document.getElementById("frm").addEventListener("submit",async(e)=>{
  e.preventDefault();
  msg.textContent="⏳ Starting...";
  etaVal.textContent="--";
  const url=urlIn.value.trim(),fmt=document.getElementById("format").value,name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,format_choice:fmt,filename:name})});
    const j=await r.json();
    if(!r.ok)throw new Error(j.error||"Failed to start");
    job=j.job_id;poll();
  }catch(err){msg.textContent="❌ "+err.message; etaVal.textContent="--";}
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

function formatSeconds(s){
  if(s===null || s===undefined || !isFinite(s) || s<0) return "--";
  s=Math.round(s);
  const h=Math.floor(s/3600); const m=Math.floor((s%3600)/60); const sec=s%60;
  if(h>0) return `${h}h ${m}m ${sec}s`;
  if(m>0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function formatMbps(speed_b){
  if(!speed_b || speed_b <= 0) return "0.0 Mbps";
  const mbps = (speed_b * 8) / 1_000_000;
  return mbps.toFixed(1) + " Mbps";
}

async function poll(){
  if(!job)return;
  try{
    const r=await fetch("/progress/"+job);
    if(r.status===404){msg.textContent="Job expired.";etaVal.textContent="--";job=null;return;}
    const p=await r.json();
    const pctv=Math.max(0,Math.min(100,p.percent||0));
    bar.style.width=pctv+"%";pct.textContent=pctv+"%";

    if(p.status==="finished"){msg.textContent="✅ Preparing file...";}
    else if(p.status==="error"){msg.textContent="❌ "+(p.error||"Download failed");}
    else msg.textContent = p.status==="downloaded" ? "✅ Download complete (fetching file)..." : "Downloading…";

    // ETA preference: server-provided -> client-calc fallback
    let etaText="--";
    if(typeof p.eta_seconds !== "undefined" && p.eta_seconds !== null){
      etaText = formatSeconds(p.eta_seconds);
    } else {
      try{
        const downloaded = p.downloaded_bytes || 0;
        const total = p.total_bytes || 0;
        const speed = p.speed_bytes || 0;
        if(total>0 && downloaded>0 && speed>0 && downloaded < total){
          const remain = (total - downloaded)/speed;
          etaText = formatSeconds(remain);
        } else {
          etaText="--";
        }
      }catch(e){etaText="--";}
    }
    etaVal.textContent = etaText;
    etaEl.title = "Speed: " + formatMbps(p.speed_bytes || 0);

    if(p.status==="finished"){ window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ job=null; return; }
    setTimeout(poll,800);
  }catch(e){msg.textContent="Network error.";etaVal.textContent="--";job=null;}
}
</script>
</body>
</html>
