"""
mobile_share.py
--------------
Drop this file into your backend/ folder (e.g. backend/mobile_share/mobile_share.py)
Then register the router in main.py with:
    from backend.mobile_share.mobile_share import router as mobile_router
    app.include_router(mobile_router)
"""

import os
import socket
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ---- Config ----
SHARED_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "shared")
os.makedirs(SHARED_FOLDER, exist_ok=True)

# ---- Track pending index prompt ----
pending_index_prompt = {"active": False, "files": [], "folder": SHARED_FOLDER}

router = APIRouter()


def get_local_ip():
    """Get the LAN IP of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# -------------------------------------------------------
# GET /mobile  — the page your phone opens in its browser
# -------------------------------------------------------
@router.get("/mobile", response_class=HTMLResponse)
def mobile_page(request: Request):
    ip = get_local_ip()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0"/>
<title>Send to PC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=DM+Sans:wght@300;400;500&display=swap');

  :root {{
    --bg: #0a0a0f;
    --surface: #13131a;
    --border: #2a2a3a;
    --accent: #7c6bff;
    --accent2: #ff6b9d;
    --text: #e8e8f0;
    --muted: #5a5a7a;
    --success: #4ade80;
    --danger: #f87171;
    --radius: 16px;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 20px 60px;
    background-image:
      radial-gradient(ellipse at 20% 10%, rgba(124,107,255,0.12) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(255,107,157,0.08) 0%, transparent 50%);
  }}

  header {{
    width: 100%;
    max-width: 480px;
    margin-bottom: 40px;
    text-align: center;
  }}

  .logo {{
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 28px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 6px;
  }}

  .subtitle {{
    color: var(--muted);
    font-size: 13px;
    font-weight: 300;
    letter-spacing: 0.5px;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px 24px;
    width: 100%;
    max-width: 480px;
    margin-bottom: 16px;
  }}

  .drop-zone {{
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 48px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    background: rgba(124,107,255,0.03);
  }}

  .drop-zone:active, .drop-zone.drag-over {{
    border-color: var(--accent);
    background: rgba(124,107,255,0.08);
  }}

  .drop-icon {{
    font-size: 48px;
    margin-bottom: 12px;
    display: block;
  }}

  .drop-label {{
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 16px;
    color: var(--text);
    margin-bottom: 6px;
  }}

  .drop-hint {{
    font-size: 12px;
    color: var(--muted);
  }}

  #file-input {{
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }}

  .file-list {{
    margin-top: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}

  .file-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    position: relative;
    overflow: hidden;
  }}

  .file-item .progress-bar {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: rgba(124,107,255,0.15);
    width: 0%;
    transition: width 0.3s;
  }}

  .file-icon {{
    font-size: 18px;
    z-index: 1;
  }}

  .file-name {{
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    z-index: 1;
  }}

  .file-size {{
    font-size: 11px;
    color: var(--muted);
    z-index: 1;
  }}

  .file-status {{
    font-size: 14px;
    z-index: 1;
  }}

  .btn {{
    display: block;
    width: 100%;
    max-width: 480px;
    padding: 16px;
    border: none;
    border-radius: var(--radius);
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 16px;
    cursor: pointer;
    letter-spacing: 0.5px;
    transition: all 0.2s;
  }}

  .btn-primary {{
    background: linear-gradient(135deg, var(--accent), #9b8bff);
    color: white;
    box-shadow: 0 4px 24px rgba(124,107,255,0.4);
  }}

  .btn-primary:active {{ transform: scale(0.97); }}
  .btn-primary:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }}

  .status-card {{
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    width: 100%;
    max-width: 480px;
    text-align: center;
    margin-bottom: 16px;
  }}

  .status-icon {{ font-size: 40px; margin-bottom: 10px; }}

  .status-title {{
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 18px;
    margin-bottom: 6px;
  }}

  .status-msg {{
    font-size: 13px;
    color: var(--muted);
  }}

  .allowed-types {{
    font-size: 11px;
    color: var(--muted);
    text-align: center;
    margin-top: 8px;
  }}

  .spinner {{
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 8px;
  }}

  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>

<header>
  <div class="logo">⚡ Send to PC</div>
  <div class="subtitle">Transfer files wirelessly to your laptop</div>
</header>

<div class="card" id="pick-card">
  <div class="drop-zone" id="drop-zone">
    <input type="file" id="file-input" multiple
      accept=".pdf,.txt,.jpg,.jpeg,.png,.csv,.docx"/>
    <span class="drop-icon">📁</span>
    <div class="drop-label">Tap to choose files</div>
    <div class="drop-hint">or drag &amp; drop here</div>
  </div>

  <div class="file-list" id="file-list"></div>

  <p class="allowed-types">PDF · TXT · JPG · PNG · CSV · DOCX</p>
</div>

<button class="btn btn-primary" id="send-btn" disabled onclick="uploadFiles()">
  Send to PC
</button>

<div class="status-card" id="status-card">
  <div class="status-icon" id="status-icon">⏳</div>
  <div class="status-title" id="status-title">Transferring...</div>
  <div class="status-msg" id="status-msg">Please keep this page open</div>
</div>

<script>
const input = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const sendBtn = document.getElementById('send-btn');
const statusCard = document.getElementById('status-card');
const pickCard = document.getElementById('pick-card');

let selectedFiles = [];

const EXT_ICONS = {{
  pdf: '📄', txt: '📝', jpg: '🖼️', jpeg: '🖼️',
  png: '🖼️', csv: '📊', docx: '📘'
}};

function getIcon(name) {{
  const ext = name.split('.').pop().toLowerCase();
  return EXT_ICONS[ext] || '📎';
}}

function fmtSize(bytes) {{
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/(1024*1024)).toFixed(1) + ' MB';
}}

input.addEventListener('change', () => {{
  selectedFiles = Array.from(input.files);
  renderList();
}});

function renderList() {{
  fileList.innerHTML = '';
  selectedFiles.forEach((f, i) => {{
    const div = document.createElement('div');
    div.className = 'file-item';
    div.id = `file-${{i}}`;
    div.innerHTML = `
      <div class="progress-bar" id="prog-${{i}}"></div>
      <span class="file-icon">${{getIcon(f.name)}}</span>
      <span class="file-name">${{f.name}}</span>
      <span class="file-size">${{fmtSize(f.size)}}</span>
      <span class="file-status" id="status-${{i}}">⏳</span>
    `;
    fileList.appendChild(div);
  }});
  sendBtn.disabled = selectedFiles.length === 0;
}}

async function uploadFiles() {{
  if (!selectedFiles.length) return;

  sendBtn.disabled = true;
  sendBtn.innerHTML = '<span class="spinner"></span> Sending...';

  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < selectedFiles.length; i++) {{
    const file = selectedFiles[i];
    const progBar = document.getElementById(`prog-${{i}}`);
    const statusEl = document.getElementById(`status-${{i}}`);

    statusEl.textContent = '📤';

    try {{
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();
      await new Promise((resolve, reject) => {{
        xhr.upload.onprogress = (e) => {{
          if (e.lengthComputable) {{
            progBar.style.width = (e.loaded / e.total * 100) + '%';
          }}
        }};
        xhr.onload = () => {{
          if (xhr.status === 200) {{
            statusEl.textContent = '✅';
            successCount++;
            resolve();
          }} else {{
            statusEl.textContent = '❌';
            failCount++;
            resolve();
          }}
        }};
        xhr.onerror = () => {{ statusEl.textContent = '❌'; failCount++; resolve(); }};
        xhr.open('POST', '/mobile/upload');
        xhr.send(formData);
      }});
    }} catch(e) {{
      document.getElementById(`status-${{i}}`).textContent = '❌';
      failCount++;
    }}
  }}

  // Notify server that batch is done
  await fetch('/mobile/transfer-complete', {{ method: 'POST' }});

  pickCard.style.display = 'none';
  sendBtn.style.display = 'none';
  statusCard.style.display = 'block';

  if (failCount === 0) {{
    document.getElementById('status-icon').textContent = '✅';
    document.getElementById('status-title').textContent = `${{successCount}} file${{successCount>1?'s':''}} sent!`;
    document.getElementById('status-msg').textContent = 'A prompt will appear on your PC to index the files.';
  }} else {{
    document.getElementById('status-icon').textContent = '⚠️';
    document.getElementById('status-title').textContent = `${{successCount}} sent, ${{failCount}} failed`;
    document.getElementById('status-msg').textContent = 'Some files could not be transferred.';
  }}
}}
</script>

</body>
</html>"""
    return HTMLResponse(content=html)


# -------------------------------------------------------
# POST /mobile/upload  — receives one file at a time
# -------------------------------------------------------
@router.post("/mobile/upload")
async def mobile_upload(file: UploadFile = File(...)):
    try:
        dest = os.path.join(SHARED_FOLDER, file.filename)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        pending_index_prompt["files"].append(file.filename)
        return JSONResponse({"status": "ok", "file": file.filename})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


# -------------------------------------------------------
# POST /mobile/transfer-complete  — all files sent
# -------------------------------------------------------
@router.post("/mobile/transfer-complete")
async def transfer_complete():
    pending_index_prompt["active"] = True
    return JSONResponse({"status": "prompt_pending"})


# -------------------------------------------------------
# GET /mobile/pending  — polled by main UI to show popup
# -------------------------------------------------------
@router.get("/mobile/pending")
async def get_pending():
    return JSONResponse(pending_index_prompt)


# -------------------------------------------------------
# POST /mobile/dismiss-prompt  — user dismissed or indexed
# -------------------------------------------------------
@router.post("/mobile/dismiss-prompt")
async def dismiss_prompt():
    pending_index_prompt["active"] = False
    pending_index_prompt["files"] = []
    return JSONResponse({"status": "dismissed"})


# -------------------------------------------------------
# GET /mobile/qr  — returns connection info for QR display
# -------------------------------------------------------
@router.get("/mobile/qr-info")
async def qr_info():
    ip = get_local_ip()
    return JSONResponse({
        "ip": ip,
        "url": f"http://{ip}:8000/mobile",
        "folder": SHARED_FOLDER
    })