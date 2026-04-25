import os
import threading
import subprocess
import shutil
import sqlite3
import tempfile

from backend.task_queue.progress import progress
from backend.automation.file_watcher import watched_paths, start_watching, stop_all_watchers
from backend.scanner.folder_scanner import scan_folder
from backend.task_queue.file_queue import file_queue, queued_files
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Form, UploadFile, File
from typing import List
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from backend.search.search import search_files
from backend.configuration import DB_LOCATION
from contextlib import asynccontextmanager
from backend.resetter.reset import reset_db as do_reset
from backend.vectorizer.faiss_index import index, save_index
from backend.task_queue.notifications import notification_queue
from urllib.parse import quote, unquote
import socket


# ---- Lifespan ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    print("✅ File watcher started alongside FastAPI")
    yield
    print("🛑 FastAPI shutting down")

app = FastAPI(lifespan=lifespan)

# ---- Static + Templates ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ---- Request Model ----
class SearchRequest(BaseModel):
    query: str
    file_type: str | None = None
    folder: str | None = None

# ---- Watcher starter ----
def run_watcher():
    # ✅ Load watched folders from DB on startup
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM watched_folders")
        folders = [row[0] for row in cursor.fetchall()]
        conn.close()

        for folder in folders:
            if os.path.exists(folder):
                threading.Thread(
                    target=start_watching,
                    args=(folder,),
                    daemon=True
                ).start()
                print(f"👀 Restored watcher: {folder}")
    except Exception as e:
        print(f"❌ Error restoring watchers: {e}")

# ---- Status ----
@app.get("/status")
def status():
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.txt'")
    txt_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.pdf'")
    pdf_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension IN ('.jpg','.jpeg','.png')")
    img_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.csv'")
    csv_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vector_mapping")
    total_vectors = cursor.fetchone()[0]
    
    conn.close()
    total_files = txt_count + pdf_count + img_count + csv_count
    return {
        "total_files": total_files,
        "total_vectors": total_vectors,
        "txt_count": txt_count,
        "pdf_count": pdf_count,
        "img_count": img_count,
        "csv_count": csv_count
    }

def save_search(query: str):
    """Save search query to DB — max 10 recent searches"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()

        # ✅ Insert or update timestamp if query exists
        cursor.execute("""
            INSERT INTO recent_searches (query, searched_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(query) DO UPDATE SET searched_at = CURRENT_TIMESTAMP
        """, (query,))

        # ✅ Keep only last 10
        cursor.execute("""
            DELETE FROM recent_searches
            WHERE id NOT IN (
                SELECT id FROM recent_searches
                ORDER BY searched_at DESC
                LIMIT 10
            )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error saving search: {e}")

def get_recent_searches():
    """Get last 10 searches"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query FROM recent_searches
            ORDER BY searched_at DESC
            LIMIT 10
        """)
        searches = [row[0] for row in cursor.fetchall()]
        conn.close()
        return searches
    except:
        return []

def get_folders():
    """Get watched folders"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM watched_folders")
        folders = [row[0] for row in cursor.fetchall()]
        conn.close()
        return folders
    except:
        return []

def save_recent_results(query: str, results: list):
    """Save top 3 results from each search"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()

        # ✅ Save top 3 results
        for r in results[:3]:
            cursor.execute("""
                INSERT INTO recent_results 
                (query, file_name, file_path, score)
                VALUES (?, ?, ?, ?)
            """, (query, r["file_name"], r["file_path"], r["score"]))

        # ✅ Keep only last 9 results total
        cursor.execute("""
            DELETE FROM recent_results
            WHERE id NOT IN (
                SELECT id FROM recent_results
                ORDER BY searched_at DESC
                LIMIT 9
            )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error saving results: {e}")

def get_recent_results():
    """Get last 9 recent results"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query, file_name, file_path, score, searched_at
            FROM recent_results
            ORDER BY searched_at DESC
            LIMIT 9
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "query": row[0],
                "file_name": row[1],
                "file_path": row[2],
                "score": row[3],
                "searched_at": row[4]
            }
            for row in rows
        ]
    except:
        return []

# ---- Routes ----
@app.get("/")
def home(request: Request, msg: str = ""):
    msg = unquote(msg)
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM watched_folders")
        folders = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print("❌ Error loading folders:", e)
        folders = []

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stats": status(), "msg": "", "folders": get_folders(),
                "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
    )

@app.get("/files")
def my_files(request: Request):
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("SELECT name, extension, path FROM files ORDER BY name")
    rows = cursor.fetchall()
    conn.close()

    files = {"Text Files": [], "PDF Files": [], "Image Files": [], "CSV Files": []}

    for name, extension, file_path in rows:
        if extension == ".txt":
            files["Text Files"].append({"name": name, "extension": extension, "path": file_path})
        elif extension == ".pdf":
            files["PDF Files"].append({"name": name, "extension": extension, "path": file_path})
        elif extension in (".jpg", ".jpeg", ".png"):
            files["Image Files"].append({"name": name, "extension": extension, "path": file_path})
        elif extension == ".csv":
            files["CSV Files"].append({"name": name, "extension": extension, "path": file_path})

    return templates.TemplateResponse(
        request=request,
        name="files.html",
        context={"files": files, "stats": status()}
    )

@app.post("/search-ui")
def search_ui(request: Request,
              query: str = Form(...),
              file_type: str = Form(None),
              folder: str = Form(None)):
    
    results = []

    try:
        if not query.strip():
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "results": [], "stats": status(), "msg": "",
                    "folders": [], "recent_searches": get_recent_searches(),
                    "recent_results": get_recent_results()   # ✅ added
                }
            )

        # Save search query
        save_search(query.strip())

        results = search_files(
            query=query,
            file_type=file_type if file_type else None,
            folder=folder if folder else None
        )

        # ✅ Save results to DB
        save_recent_results(query.strip(), results)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "results": results, "stats": status(), "msg": "",
                "folders": get_folders(), "recent_searches": get_recent_searches(),
                "recent_results": get_recent_results()   # ✅ added
            }
        )

    except Exception as e:
        print("❌ ERROR:", e)
        return {"error": str(e)}

@app.get("/search-ui")
def search_ui_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stats": status(), "msg": "", "folders": get_folders(),
                "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
    )

@app.post("/clear-searches")
def clear_searches():
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recent_searches")
        conn.commit()
        conn.close()
        return {"status": "cleared"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/open")
def open_file(path: str):
    full_path = os.path.normpath(path)
    if not os.path.exists(full_path):
        return {"error": f"File not found: {full_path}"}
    return FileResponse(full_path)

@app.get("/open-native")
def open_native(path: str):
    try:
        print(f"📥 Raw path received: '{path}'")
        full_path = os.path.normpath(path)
        print(f"🔍 Trying to open: {full_path}")

        if os.path.exists(full_path):
            subprocess.Popen(f'start "" "{full_path}"', shell=True)
            return {"status": "opened"}

        return {"error": f"File not found: {full_path}"}

    except Exception as e:
        return {"error": str(e)}

@app.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    allowed_ext = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".csv"}
    temp_dir = os.path.join(tempfile.gettempdir(), "ai_search_uploads")
    os.makedirs(temp_dir, exist_ok=True)

    uploaded = []
    skipped = []

    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_ext:
            continue

        # ✅ Check DB before saving to temp
        try:
            conn = sqlite3.connect(DB_LOCATION)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM files WHERE name = ? AND extension = ?",
                (filename, ext)
            )
            existing = cursor.fetchone()
            conn.close()

            if existing:
                print(f"⚠️ Already indexed: {filename}")
                skipped.append(filename)
                continue  # ✅ Skip this file entirely

        except Exception as e:
            print(f"❌ DB check error: {e}")

        # ✅ Only reaches here if file is NOT already indexed
        temp_path = os.path.join(temp_dir, filename)

        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            if temp_path not in queued_files:
                queued_files.add(temp_path)
                file_queue.put(("create", temp_path))
                uploaded.append(filename)

        except Exception as e:
            print(f"❌ Upload error for {filename}: {e}")

    # ✅ Return outside the loop
    if uploaded:
        msg = quote(f"success: Successfully added: {', '.join(uploaded)}")
    elif skipped:
        msg = quote(f"warning: Already indexed: {', '.join(skipped)}")
    else:
        msg = quote("warning: No new files added")

    return RedirectResponse(url=f"/?msg={msg}", status_code=303)

@app.post("/reset")
def reset_db_route():
    try:
        # ✅ Stop all watchers first
        stop_all_watchers()

        # ✅ Clear DB
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files")
        cursor.execute("DELETE FROM vector_mapping")
        cursor.execute("DELETE FROM watched_folders")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='files'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='vector_mapping'")
        conn.commit()
        conn.close()
        print("✅ Database cleared")

        # ✅ Reset FAISS
        index.reset()
        save_index(index)
        print("✅ FAISS reset")

        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        print(f"❌ Reset Error: {e}")
        return {"error": str(e)}

@app.post("/add-folder")
def add_folder(path: str = Form(...)):
    try:
        if not os.path.exists(path):
            return RedirectResponse(
                url=f"/?msg={quote('error: Invalid folder path')}",
                status_code=303
            )

        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO watched_folders (path) VALUES (?)",
            (path,)
        )
        conn.commit()
        conn.close()

        if path in watched_paths:
            return RedirectResponse(
                url=f"/?msg={quote('warning: Folder already being watched')}",
                status_code=303
            )

        # ✅ Scan existing files
        threading.Thread(target=scan_folder, args=(path,), daemon=True).start()

        # ✅ Start watcher
        threading.Thread(target=start_watching, args=(path,), daemon=True).start()

        return RedirectResponse(
            url=f"/?msg={quote('success: Folder added successfully')}",
            status_code=303
        )

    except Exception as e:
        return RedirectResponse(
            url=f"/?msg={quote(f'error: {str(e)}')}",
            status_code=303
        )

@app.post("/remove-folder")
def remove_folder(path: str = Form(...)):
    try:
        from backend.automation.file_watcher import stop_watching

        stopped = stop_watching(path)

        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watched_folders WHERE path = ?", (path,))
        conn.commit()
        conn.close()

        if stopped:
            return RedirectResponse(
                url=f"/?msg={quote('success: Folder removed')}",
                status_code=303
            )
        else:
            return RedirectResponse(
                url=f"/?msg={quote('warning: Watcher not active but removed from DB')}",
                status_code=303
            )

    except Exception as e:
        return RedirectResponse(
            url=f"/?msg={quote(f'error: {str(e)}')}",
            status_code=303
        )

@app.get("/notifications")
def get_notifications():
    messages = list(notification_queue)
    notification_queue.clear()
    return {"notifications": messages}

@app.get("/progress")
def get_progress():
    return progress

@app.post("/clear-report")
def clear_report():
    # ✅ Reset after user closes report
    progress["report_ready"] = False
    progress["success_files"] = []
    progress["failed_files"] = []
    progress["total"] = 0
    progress["processed"] = 0
    progress["current_file"] = ""
    return {"status": "cleared"}

@app.post("/clear-recent-results")
def clear_recent_results():
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recent_results")
        conn.commit()
        conn.close()
        return {"status": "cleared"}
    except Exception as e:
        return {"error": str(e)}

# MOBILE SHARE — wireless file transfer from phone to laptop
SHARED_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "shared")
os.makedirs(SHARED_FOLDER, exist_ok=True)

# Tracks files received from phone, waiting for user to confirm indexing
_mobile_pending = {"active": False, "files": [], "folder": SHARED_FOLDER}

def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.get("/mobile/qr-info")
def mobile_qr_info():
    """Returns LAN IP and phone URL — used by the QR modal."""
    ip = _get_local_ip()
    return {
        "ip": ip,
        "url": f"http://{ip}:8000/mobile",
        "folder": SHARED_FOLDER
    }


@app.get("/mobile", response_class=None)
def mobile_page():
    """The page your phone opens in its browser to send files."""
    from fastapi.responses import HTMLResponse
    ip = _get_local_ip()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0"/>
<title>Send to PC — DocS AI</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f0f2f5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 20px 60px;
}}
header {{ width: 100%; max-width: 480px; text-align: center; margin-bottom: 32px; }}
.logo {{ font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }}
.sub {{ font-size: 13px; color: #64748b; }}
.card {{
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 24px;
    width: 100%;
    max-width: 480px;
    margin-bottom: 16px;
}}
.drop-zone {{
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    position: relative;
    transition: all 0.15s;
    background: #fafafa;
    margin-bottom: 12px;
}}
.drop-zone:active {{ border-color: #2563eb; background: #eff6ff; }}
.drop-icon {{ font-size: 40px; margin-bottom: 10px; display: block; }}
.drop-label {{ font-weight: 600; font-size: 15px; color: #0f172a; margin-bottom: 4px; }}
.drop-hint {{ font-size: 12px; color: #94a3b8; }}
#file-input {{
    position: absolute; inset: 0; opacity: 0;
    cursor: pointer; width: 100%; height: 100%;
}}
.file-list {{ display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }}
.file-item {{
    display: flex; align-items: center; gap: 10px;
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 10px 14px;
    font-size: 13px; position: relative; overflow: hidden;
}}
.file-prog {{
    position: absolute; left: 0; top: 0; bottom: 0;
    background: #eff6ff; width: 0%; transition: width 0.3s;
    z-index: 0;
}}
.file-icon {{ font-size: 18px; z-index: 1; }}
.file-name {{ flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; z-index: 1; color: #374151; }}
.file-size {{ font-size: 11px; color: #94a3b8; z-index: 1; }}
.file-stat {{ font-size: 14px; z-index: 1; }}
.btn {{
    display: block; width: 100%; max-width: 480px;
    padding: 14px; border: none; border-radius: 12px;
    font-weight: 700; font-size: 15px; cursor: pointer;
    transition: background 0.15s;
}}
.btn-primary {{ background: #2563eb; color: #fff; }}
.btn-primary:hover {{ background: #1d4ed8; }}
.btn-primary:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.status-card {{
    display: none; background: #fff;
    border: 1px solid #e2e8f0; border-radius: 16px;
    padding: 32px 24px; width: 100%; max-width: 480px;
    text-align: center; margin-bottom: 16px;
}}
.status-icon {{ font-size: 48px; margin-bottom: 12px; }}
.status-title {{ font-size: 20px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }}
.status-msg {{ font-size: 13px; color: #64748b; }}
.allowed {{ font-size: 11px; color: #94a3b8; text-align: center; margin-top: 8px; }}
.spinner {{
    display: inline-block; width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: #fff; border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle; margin-right: 6px;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<header>
    <div class="logo">⚡ DocS AI</div>
    <div class="sub">Send files to your PC wirelessly</div>
</header>

<div class="card" id="pick-card">
    <div class="drop-zone" id="drop-zone">
        <input type="file" id="file-input" multiple
            accept=".pdf,.txt,.jpg,.jpeg,.png,.csv,.docx"/>
        <span class="drop-icon">📁</span>
        <div class="drop-label">Tap to choose files</div>
        <div class="drop-hint">PDF · TXT · JPG · PNG · CSV</div>
    </div>
    <div class="file-list" id="file-list"></div>
    <p class="allowed">Supported: .pdf .txt .jpg .png .csv .docx</p>
</div>

<button class="btn btn-primary" id="send-btn" disabled onclick="uploadFiles()">
    Send to PC
</button>

<div class="status-card" id="status-card">
    <div class="status-icon" id="s-icon">✅</div>
    <div class="status-title" id="s-title">Done!</div>
    <div class="status-msg" id="s-msg">A prompt will appear on your PC to index the files.</div>
</div>

<script>
const input = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const sendBtn = document.getElementById('send-btn');
const ICONS = {{pdf:'📄',txt:'📝',jpg:'🖼️',jpeg:'🖼️',png:'🖼️',csv:'📊',docx:'📘'}};
let files = [];

function icon(name) {{ return ICONS[name.split('.').pop().toLowerCase()] || '📎'; }}
function fmtSize(b) {{
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
    return (b/1048576).toFixed(1) + ' MB';
}}

input.addEventListener('change', () => {{
    files = Array.from(input.files);
    fileList.innerHTML = '';
    files.forEach((f, i) => {{
        fileList.innerHTML += `
        <div class="file-item" id="fi-${{i}}">
            <div class="file-prog" id="fp-${{i}}"></div>
            <span class="file-icon">${{icon(f.name)}}</span>
            <span class="file-name">${{f.name}}</span>
            <span class="file-size">${{fmtSize(f.size)}}</span>
            <span class="file-stat" id="fs-${{i}}">⏳</span>
        </div>`;
    }});
    sendBtn.disabled = files.length === 0;
}});

async function uploadFiles() {{
    if (!files.length) return;
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span>Sending...';
    let ok = 0, fail = 0;
    for (let i = 0; i < files.length; i++) {{
        const prog = document.getElementById(`fp-${{i}}`);
        const stat = document.getElementById(`fs-${{i}}`);
        stat.textContent = '📤';
        try {{
            const fd = new FormData();
            fd.append('file', files[i]);
            await new Promise((res, rej) => {{
                const xhr = new XMLHttpRequest();
                xhr.upload.onprogress = e => {{
                    if (e.lengthComputable) prog.style.width = (e.loaded/e.total*100) + '%';
                }};
                xhr.onload = () => {{ stat.textContent = xhr.status===200 ? '✅' : '❌'; xhr.status===200 ? ok++ : fail++; res(); }};
                xhr.onerror = () => {{ stat.textContent = '❌'; fail++; res(); }};
                xhr.open('POST', '/mobile/upload');
                xhr.send(fd);
            }});
        }} catch(e) {{ document.getElementById(`fs-${{i}}`).textContent = '❌'; fail++; }}
    }}
    await fetch('/mobile/transfer-complete', {{method:'POST'}});
    document.getElementById('pick-card').style.display = 'none';
    sendBtn.style.display = 'none';
    const sc = document.getElementById('status-card');
    sc.style.display = 'block';
    if (fail === 0) {{
        document.getElementById('s-icon').textContent = '✅';
        document.getElementById('s-title').textContent = `${{ok}} file${{ok>1?'s':''}} sent!`;
        document.getElementById('s-msg').textContent = 'A prompt will appear on your PC to index them.';
    }} else {{
        document.getElementById('s-icon').textContent = '⚠️';
        document.getElementById('s-title').textContent = `${{ok}} sent, ${{fail}} failed`;
        document.getElementById('s-msg').textContent = 'Some files could not be transferred.';
    }}
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/mobile/upload")
async def mobile_upload(file: UploadFile = File(...)):
    """Receives a single file from the phone and saves to Desktop/shared/."""
    try:
        dest = os.path.join(SHARED_FOLDER, file.filename)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        _mobile_pending["files"].append(file.filename)
        print(f"📱 Received from phone: {file.filename}")
        return {"status": "ok", "file": file.filename}
    except Exception as e:
        print(f"❌ Mobile upload error: {e}")
        return {"status": "error", "detail": str(e)}


@app.post("/mobile/transfer-complete")
async def mobile_transfer_complete():
    """Phone calls this when all files are done uploading."""
    _mobile_pending["active"] = True
    _mobile_pending["folder"] = SHARED_FOLDER
    print(f"📱 Transfer complete — {len(_mobile_pending['files'])} file(s) ready to index")
    return {"status": "prompt_pending"}


@app.get("/mobile/pending")
def mobile_pending():
    """Polled by the desktop UI every 4s to check for incoming files."""
    return _mobile_pending


@app.post("/mobile/dismiss-prompt")
def mobile_dismiss_prompt():
    """Called when user clicks 'Yes, Index Now' or 'Not Now'."""
    _mobile_pending["active"] = False
    _mobile_pending["files"] = []
    return {"status": "dismissed"}

@app.get("/pick-folder")
def pick_folder_dialog():
    try:
        result = subprocess.run([
            "powershell", "-Command",
            """
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
            $dialog.Description = 'Select folder to index'
            $dialog.ShowNewFolderButton = $false
            if ($dialog.ShowDialog() -eq 'OK') {
                Write-Output $dialog.SelectedPath
            }
            """
        ], capture_output=True, text=True, timeout=60)

        path = result.stdout.strip()

        if path:
            return {"path": path}
        return {"path": None}

    except Exception as e:
        return {"path": None, "error": str(e)}