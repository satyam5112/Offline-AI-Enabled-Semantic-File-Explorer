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
# Use USERPROFILE (always real Desktop) not expanduser (may give OneDrive Desktop)
def _get_desktop():
    """Returns the real Desktop path, avoiding OneDrive Desktop duplication."""
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        real = os.path.join(userprofile, "Desktop", "shared")
        if os.path.exists(os.path.join(userprofile, "Desktop")):
            return real
    # Fallback
    return os.path.join(os.path.expanduser("~"), "Desktop", "shared")

SHARED_FOLDER = _get_desktop()
os.makedirs(SHARED_FOLDER, exist_ok=True)

# ---- Track pending index prompt ----
pending_index_prompt = {"active": False, "files": [], "folder": SHARED_FOLDER}

router = APIRouter()


def get_local_ip():
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
@app.get("/mobile", response_class=None)
def mobile_page():
    """The page your phone opens in its browser to send files."""
    from fastapi.responses import HTMLResponse
    ip = _get_local_ip()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>Send to PC — DocS AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300;14..32,400;14..32,500;14..32,600;14..32,700;14..32,800&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        :root {{
            /* Primary Colors */
            --color-p: #021A54;
            --color-s: #FF85BB;
            --color-t: #FFCEE3;
            --color-q: #000000;
            
            --color-p-dark: #011447;
            --color-p-light: #E8EDF9;
            --color-s-dark: #e66ba1;
            --color-s-light: #fff0f5;
            
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-error: #ef4444;
            --color-info: #3b82f6;
            
            /* Background Colors */
            --bg-primary: #F8F5F0;
            --bg-secondary: #FFFDF9;
            --bg-tertiary: #F0EDE8;
            --bg-card: rgba(255, 255, 255, 0.85);
            --bg-card-solid: #FFFFFF;
            --bg-overlay: rgba(255, 255, 255, 0.6);
            --bg-sidebar: linear-gradient(135deg, var(--color-p), var(--color-s));
            
            /* Text Colors */
            --text-primary: #021A54;
            --text-secondary: #000000;
            --text-muted: #8B8BA0;
            --text-dark: #021A54;
            --text-light: #FFFFFF;
            
            /* Borders */
            --border-glow: rgba(2, 26, 84, 0.15);
            --border-glow-hover: rgba(255, 133, 187, 0.4);
            --border-light: rgba(2, 26, 84, 0.08);
            --border-dark: rgba(0, 0, 0, 0.1);
            
            /* Gradients */
            --gradient-1: linear-gradient(135deg, var(--color-p), var(--color-s));
            --gradient-2: linear-gradient(135deg, var(--color-s), var(--color-t));
            --gradient-3: linear-gradient(135deg, var(--color-p), var(--color-t));
            --gradient-pink: linear-gradient(135deg, var(--color-s), var(--color-t));
            
            /* Shadows */
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.03);
            --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06), 0 2px 4px rgba(0, 0, 0, 0.04);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
            --shadow-glow: 0 0 20px rgba(255, 133, 187, 0.15);
            --shadow-pink: 0 4px 20px rgba(255, 133, 187, 0.2);
            
            --transition-fast: 0.15s ease;
            --transition-normal: 0.2s ease;
            --transition-slow: 0.3s ease;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-primary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 32px 20px 60px;
        }}
        
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
            border-radius: 10px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--gradient-1);
            border-radius: 10px;
        }}
        
        header {{
            width: 100%;
            max-width: 520px;
            text-align: center;
            margin-bottom: 32px;
        }}
        
        .logo {{
            font-size: 32px;
            font-weight: 800;
            background: var(--gradient-3);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            letter-spacing: -0.5px;
            margin-bottom: 8px;
        }}
        
        .sub {{
            font-size: 14px;
            color: var(--text-muted);
            font-weight: 500;
        }}
        
        .glass-card {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            border: 1px solid var(--border-glow);
            padding: 28px;
            width: 100%;
            max-width: 520px;
            margin-bottom: 24px;
            transition: all var(--transition-slow);
            position: relative;
            overflow: hidden;
        }}
        
        .glass-card:hover {{
            border-color: var(--border-glow-hover);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md), var(--shadow-glow);
        }}
        
        .drop-zone {{
            background: rgb(255, 255, 255);
            border: 2px dashed var(--border-glow);
            border-radius: 20px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all var(--transition-normal);
            margin-bottom: 16px;
            position: relative;
        }}
        
        .drop-zone:hover {{
            border-color: var(--color-p);
            background: rgba(2, 26, 84, 0.03);
            transform: scale(1.01);
            box-shadow: var(--shadow-sm);
        }}
        
        .drop-icon {{
            font-size: 48px;
            margin-bottom: 12px;
            display: block;
            opacity: 0.9;
        }}
        
        .drop-label {{
            font-weight: 700;
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        
        .drop-hint {{
            font-size: 13px;
            color: var(--text-muted);
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
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 16px;
        }}
        
        .file-item {{
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(4px);
            border: 1px solid var(--border-light);
            border-radius: 16px;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            position: relative;
            overflow: hidden;
            transition: all var(--transition-normal);
        }}
        
        .file-item:hover {{
            border-color: var(--border-glow-hover);
            background: rgba(255, 133, 187, 0.04);
            transform: translateX(4px);
        }}
        
        .file-prog {{
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(2, 26, 84, 0.12), rgba(255, 133, 187, 0.12));
            width: 0%;
            transition: width 0.3s ease;
            z-index: 0;
            border-radius: 16px;
        }}
        
        .file-icon {{
            font-size: 22px;
            z-index: 1;
        }}
        
        .file-name {{
            flex: 1;
            font-weight: 600;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            z-index: 1;
        }}
        
        .file-size {{
            font-size: 11px;
            color: var(--text-muted);
            z-index: 1;
        }}
        
        .file-stat {{
            font-size: 16px;
            z-index: 1;
            min-width: 32px;
            text-align: center;
        }}
        
        .allowed {{
            font-size: 11px;
            color: var(--text-muted);
            text-align: center;
            margin-top: 16px;
            border-top: 1px solid var(--border-light);
            padding-top: 14px;
        }}
        
        .btn-primary {{
            background: var(--gradient-1);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 14px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: all var(--transition-normal);
            position: relative;
            overflow: hidden;
            width: 100%;
            max-width: 520px;
            display: block;
            text-align: center;
            box-shadow: var(--shadow-sm);
        }}
        
        .btn-primary::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.25);
            transform: translate(-50%, -50%);
            transition: width 0.5s, height 0.5s;
        }}
        
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(2, 26, 84, 0.25), var(--shadow-pink);
        }}
        
        .btn-primary:hover::before {{
            width: 300px;
            height: 300px;
        }}
        
        .btn-primary:active {{
            transform: translateY(0);
        }}
        
        .btn-primary:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}
        
        .status-card {{
            display: none;
            background: var(--bg-card-solid);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-glow);
            border-radius: 28px;
            padding: 32px 28px;
            width: 100%;
            max-width: 520px;
            text-align: center;
            margin-bottom: 24px;
            transition: all var(--transition-slow);
            animation: fadeSlideUp 0.4s ease;
            box-shadow: var(--shadow-lg);
        }}
        
        .status-card:hover {{
            border-color: var(--border-glow-hover);
            transform: translateY(-3px);
        }}
        
        @keyframes fadeSlideUp {{
            from {{
                opacity: 0;
                transform: translateY(12px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .status-icon {{
            font-size: 56px;
            margin-bottom: 16px;
        }}
        
        .status-title {{
            font-size: 24px;
            font-weight: 800;
            background: var(--gradient-3);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            margin-bottom: 10px;
        }}
        
        .status-msg {{
            font-size: 14px;
            color: var(--text-muted);
            line-height: 1.5;
        }}
        
        .spinner {{
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255,255,255,0.4);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
            vertical-align: middle;
            margin-right: 8px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        @media (max-width: 560px) {{
            body {{
                padding: 24px 16px 48px;
            }}
            .glass-card {{
                padding: 20px;
            }}
            .file-item {{
                padding: 10px 12px;
            }}
            .btn-primary {{
                padding: 12px 20px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="logo">⚡ DocS AI</div>
        <div class="sub">Send files to your PC wirelessly</div>
    </header>

    <div class="glass-card" id="pick-card">
        <div class="drop-zone" id="drop-zone">
            <input type="file" id="file-input" multiple accept=".pdf,.txt,.jpg,.jpeg,.png,.csv,.docx" />
            <span class="drop-icon">📁</span>
            <div class="drop-label">Tap to choose files</div>
            <div class="drop-hint">PDF · TXT · JPG · PNG · CSV · DOCX</div>
        </div>
        <div class="file-list" id="file-list"></div>
        <p class="allowed">Supported: .pdf .txt .jpg .png .csv .docx</p>
    </div>

    <button class="btn-primary" id="send-btn" disabled onclick="uploadFiles()">
        Send to PC
    </button>

    <div class="status-card" id="status-card">
        <div class="status-icon" id="s-icon">✅</div>
        <div class="status-title" id="s-title">Done!</div>
        <div class="status-msg" id="s-msg">A prompt will appear on your PC to index the files.</div>
    </div>

    <script>
        const input = document.getElementById('file-input');
        const fileListDiv = document.getElementById('file-list');
        const sendBtn = document.getElementById('send-btn');
        const pickCard = document.getElementById('pick-card');
        const statusCard = document.getElementById('status-card');
        const sIcon = document.getElementById('s-icon');
        const sTitle = document.getElementById('s-title');
        const sMsg = document.getElementById('s-msg');
        
        const ICONS = {{
            pdf: '📄', txt: '📝', jpg: '🖼️', jpeg: '🖼️',
            png: '🖼️', csv: '📊', docx: '📘', 'default': '📎'
        }};
        
        let files = [];
        
        function getFileIcon(fileName) {{
            const ext = fileName.split('.').pop().toLowerCase();
            return ICONS[ext] || ICONS['default'];
        }}
        
        function formatSize(bytes) {{
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1048576).toFixed(1) + ' MB';
        }}
        
        function renderFileList() {{
            if (!fileListDiv) return;
            fileListDiv.innerHTML = '';
            if (files.length === 0) return;
            
            files.forEach((file, idx) => {{
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.id = `file-item-${{idx}}`;
                fileItem.innerHTML = `
                    <div class="file-prog" id="fp-${{idx}}"></div>
                    <span class="file-icon">${{getFileIcon(file.name)}}</span>
                    <span class="file-name" title="${{file.name}}">${{file.name}}</span>
                    <span class="file-size">${{formatSize(file.size)}}</span>
                    <span class="file-stat" id="fs-${{idx}}">⏳</span>
                `;
                fileListDiv.appendChild(fileItem);
            }});
        }}
        
        function updateFileStatus(index, statusIcon, progressWidth = null) {{
            const statSpan = document.getElementById(`fs-${{index}}`);
            const progDiv = document.getElementById(`fp-${{index}}`);
            if (statSpan) statSpan.textContent = statusIcon;
            if (progDiv && progressWidth !== undefined) {{
                progDiv.style.width = progressWidth + '%';
            }}
        }}
        
        input.addEventListener('change', (e) => {{
            files = Array.from(e.target.files);
            renderFileList();
            sendBtn.disabled = files.length === 0;
        }});
        
        const dropZone = document.getElementById('drop-zone');
        if (dropZone) {{
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
                dropZone.addEventListener(eventName, preventDefaults, false);
            }});
            
            function preventDefaults(e) {{
                e.preventDefault();
                e.stopPropagation();
            }}
            
            ['dragenter', 'dragover'].forEach(eventName => {{
                dropZone.addEventListener(eventName, () => {{
                    dropZone.style.borderColor = 'var(--color-p)';
                    dropZone.style.background = 'rgba(2, 26, 84, 0.03)';
                }});
            }});
            
            ['dragleave', 'drop'].forEach(eventName => {{
                dropZone.addEventListener(eventName, () => {{
                    dropZone.style.borderColor = 'var(--border-glow)';
                    dropZone.style.background = 'rgb(255, 255, 255)';
                }});
            }});
            
            dropZone.addEventListener('drop', (e) => {{
                const dt = e.dataTransfer;
                const droppedFiles = Array.from(dt.files);
                if (droppedFiles.length) {{
                    files = droppedFiles;
                    renderFileList();
                    const dataTransfer = new DataTransfer();
                    droppedFiles.forEach(f => dataTransfer.items.add(f));
                    input.files = dataTransfer.files;
                    sendBtn.disabled = files.length === 0;
                }}
            }});
            
            dropZone.addEventListener('click', (e) => {{
                if (e.target !== input && !input.contains(e.target)) {{
                    input.click();
                }}
            }});
        }}
        
        window.uploadFiles = async function uploadFiles() {{
            if (!files.length) return;
            
            sendBtn.disabled = true;
            const originalBtnText = sendBtn.innerHTML;
            sendBtn.innerHTML = '<span class="spinner"></span>Sending...';
            
            let successCount = 0;
            let failCount = 0;
            
            for (let i = 0; i < files.length; i++) {{
                const file = files[i];
                const progDiv = document.getElementById(`fp-${{i}}`);
                const statSpan = document.getElementById(`fs-${{i}}`);
                if (statSpan) statSpan.textContent = '📤';
                
                try {{
                    await new Promise((resolve, reject) => {{
                        const xhr = new XMLHttpRequest();
                        const formData = new FormData();
                        formData.append('file', file);
                        
                        xhr.upload.addEventListener('progress', (e) => {{
                            if (e.lengthComputable && progDiv) {{
                                const percent = (e.loaded / e.total) * 100;
                                progDiv.style.width = percent + '%';
                            }}
                        }});
                        
                        xhr.onload = () => {{
                            if (xhr.status === 200) {{
                                if (statSpan) statSpan.textContent = '✅';
                                successCount++;
                                resolve();
                            }} else {{
                                if (statSpan) statSpan.textContent = '❌';
                                failCount++;
                                resolve();
                            }}
                        }};
                        
                        xhr.onerror = () => {{
                            if (statSpan) statSpan.textContent = '❌';
                            failCount++;
                            resolve();
                        }};
                        
                        xhr.open('POST', '/mobile/upload', true);
                        xhr.send(formData);
                    }});
                }} catch (err) {{
                    if (statSpan) statSpan.textContent = '❌';
                    failCount++;
                }}
            }}
            
            try {{
                await fetch('/mobile/transfer-complete', {{ method: 'POST' }});
            }} catch(e) {{
                console.warn("complete notification failed", e);
            }}
            
            if (pickCard) pickCard.style.display = 'none';
            if (sendBtn) sendBtn.style.display = 'none';
            
            if (statusCard) {{
                statusCard.style.display = 'block';
                if (failCount === 0) {{
                    sIcon.textContent = '✅';
                    sTitle.textContent = `${{successCount}} file${{successCount !== 1 ? 's' : ''}} sent!`;
                    sMsg.textContent = 'A prompt will appear on your PC to index them.';
                }} else {{
                    sIcon.textContent = '⚠️';
                    sTitle.textContent = `${{successCount}} sent, ${{failCount}} failed`;
                    sMsg.textContent = 'Some files could not be transferred. Check connection and try again.';
                }}
            }}
        }};
        
        sendBtn.disabled = true;
    </script>
</body>
</html>"""
    return HTMLResponse(html)

# -------------------------------------------------------
# POST /mobile/upload  — receives one file at a time
# -------------------------------------------------------
@router.post("/mobile/upload")
async def mobile_upload(file: UploadFile = File(...)):
    try:
        # ✅ Always recreate shared folder if deleted
        os.makedirs(SHARED_FOLDER, exist_ok=True)

        # ✅ Ignore shared folder during upload
        try:
            from backend.automation.file_watcher import add_ignore_path
            add_ignore_path(SHARED_FOLDER)
        except:
            pass

        dest = os.path.join(SHARED_FOLDER, file.filename)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        pending_index_prompt["files"].append(file.filename)
        print(f"📱 Received from phone: {file.filename}")
        return JSONResponse({"status": "ok", "file": file.filename})

    except Exception as e:
        print(f"❌ Mobile upload error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)



# -------------------------------------------------------
# POST /mobile/transfer-complete  — all files sent
# -------------------------------------------------------
@router.post("/mobile/transfer-complete")
async def transfer_complete():
    pending_index_prompt["active"] = True
    pending_index_prompt["folder"] = SHARED_FOLDER

    # ✅ Recreate shared folder if deleted
    os.makedirs(SHARED_FOLDER, exist_ok=True)

    # ✅ Re-enable watcher
    try:
        from backend.automation.file_watcher import remove_ignore_path
        remove_ignore_path(SHARED_FOLDER)
    except:
        pass

    print(f"📱 Transfer complete — {len(pending_index_prompt['files'])} file(s) ready to index")

    # ✅ Restart watcher for shared folder
    try:
        from backend.automation.file_watcher import stop_watching, start_watching
        stop_watching(SHARED_FOLDER)
        threading.Thread(
            target=start_watching,
            args=(SHARED_FOLDER,),
            daemon=True
        ).start()
        print(f"👀 Watcher restarted: {SHARED_FOLDER}")
    except Exception as e:
        print(f"❌ Watcher error: {e}")

    # ✅ Save to DB
    try:
        from backend.configuration import DB_LOCATION
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path FROM watched_folders WHERE path = ?",
            (SHARED_FOLDER,)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO watched_folders (path) VALUES (?)",
                (SHARED_FOLDER,)
            )
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ DB error: {e}")

    return JSONResponse({"status": "prompt_pending"})

# -------------------------------------------------------
# GET /mobile/pending  — polled by main UI to show popup
# -------------------------------------------------------
@router.get("/mobile/pending")
async def get_pending():
    print(f"📊 Pending check: active={pending_index_prompt['active']}, files={len(pending_index_prompt['files'])}")
    # Build full paths so the UI can index specific files directly
    full_paths = [
        os.path.join(SHARED_FOLDER, f)
        for f in pending_index_prompt["files"]
        if os.path.exists(os.path.join(SHARED_FOLDER, f))
    ]
    return JSONResponse({
        "active": pending_index_prompt["active"],
        "files": pending_index_prompt["files"],
        "full_paths": full_paths,
        "folder": pending_index_prompt["folder"]
    })


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