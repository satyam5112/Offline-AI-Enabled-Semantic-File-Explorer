import os
import threading
import subprocess
import shutil
import sqlite3
import tempfile
import socket

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
from fastapi.responses import HTMLResponse
from pathlib import Path
from backend.database.db import initialize_database

# ---- Shared folder (moved up so run_watcher can use it) ----
def _get_shared_folder():
    userprofile = os.environ.get("USERPROFILE", "")
    onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
    if os.path.exists(onedrive_desktop):
        return os.path.join(onedrive_desktop, "shared")
    return os.path.join(userprofile, "Desktop", "shared")

SHARED_FOLDER = _get_shared_folder()
os.makedirs(SHARED_FOLDER, exist_ok=True)

# ---- Watcher starter ----
def run_watcher():
    if os.path.exists(SHARED_FOLDER):
        threading.Thread(
            target=start_watching,
            args=(SHARED_FOLDER,),
            daemon=True
        ).start()
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
    except Exception as e:
        print(f"Error restoring watchers: {e}")

# ---- Lifespan ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    print("File watcher started alongside FastAPI")
    yield
    print("FastAPI shutting down")

app = FastAPI(lifespan=lifespan)

recent_upload_count = 0

# ---- Static + Templates ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Vault router (safe import won't crash server if cryptography missing)
try:
    from backend.vault.vault_routes import router as vault_router
    app.include_router(vault_router)
    print("Vault router registered")
except Exception as _vault_err:
    import traceback
    print(f"Vault router failed to load: {_vault_err}")
    traceback.print_exc()

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ---- Request Model ----
class SearchRequest(BaseModel):
    query: str
    file_type: str | None = None
    folder: str | None = None

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
    """Save search query to DB max 10 recent searches"""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()

        # Insert or update timestamp if query exists
        cursor.execute("""
            INSERT INTO recent_searches (query, searched_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(query) DO UPDATE SET searched_at = CURRENT_TIMESTAMP
        """, (query,))

        # Keep only last 10
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
        print(f"Error saving search: {e}")

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
    """Save top 5 search results to recent_results table."""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recent_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                file_name TEXT,
                file_path TEXT,
                score REAL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Clear previous results
        cursor.execute("DELETE FROM recent_results")
        # Insert top 5
        for r in results[:5]:
            cursor.execute("""
                INSERT INTO recent_results (query, file_name, file_path, score)
                VALUES (?, ?, ?, ?)
            """, (query, r["file_name"], r.get("file_path",""), r.get("score", 0)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving recent results: {e}")


def get_recent_results():
    """Get results from the most recent search."""
    try:
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query, file_name, file_path, score
            FROM recent_results
            ORDER BY searched_at DESC LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()
        return [{"query": r[0], "file_name": r[1], "file_path": r[2], "score": r[3]} for r in rows]
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
        print("Error loading folders:", e)
        folders = []

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stats": status(), "msg": msg, "folders": folders, "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
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
    try:
        if not query.strip():
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={"results": [], "stats": status(), "msg": "", "folders": [], "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
            )

        # Save search query to DB
        save_search(query.strip())

        results = search_files(
            query=query,
            file_type=file_type if file_type else None,
            folder=folder if folder else None
        )

        # Save recent results
        save_recent_results(query.strip(), results)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"results": results, "stats": status(), "msg": "", "folders": get_folders(), "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
        )

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}

@app.get("/search-ui")
def search_ui_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stats": status(), "msg": "", "folders": get_folders(), "recent_searches": get_recent_searches(), "recent_results": get_recent_results()}
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
        # print(f"Raw path received: '{path}'")
        full_path = os.path.normpath(path)
        # print(f"Trying to open: {full_path}")

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

        #Check DB before saving to temp
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
                # print(f"Already indexed: {filename}")
                skipped.append(filename)
                continue  # Skip this file entirely

        except Exception as e:
            print(f"DB check error: {e}")

        #Only reaches here if file is NOT already indexed
        temp_path = os.path.join(temp_dir, filename)

        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            if temp_path not in queued_files:
                queued_files.add(temp_path)
                file_queue.put(("create", temp_path))
                uploaded.append(filename)

        except Exception as e:
            print(f"Upload error for {filename}: {e}")

    # Return outside the loop
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
        # Stop all watchers first
        stop_all_watchers()

        # Clear DB
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files")
        cursor.execute("DELETE FROM vector_mapping")
        cursor.execute("DELETE FROM watched_folders")

        cursor.execute("DELETE FROM sqlite_sequence WHERE name='files'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='watched_folders'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='vector_mapping'")
        conn.commit()
        conn.close()
        # print("Database cleared")

        # Reset FAISS
        index.reset()
        save_index(index)
        # print("FAISS reset")

        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        print(f"Reset Error: {e}")
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

        # Scan existing files
        threading.Thread(target=scan_folder, args=(path,), daemon=True).start()

        # Start watcher
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
    # Reset after user closes report
    progress["report_ready"] = False
    progress["success_files"] = []
    progress["failed_files"] = []
    progress["total"] = 0
    progress["processed"] = 0
    progress["current_file"] = ""
    return {"status": "cleared"}


# ================================================================
# MOBILE SHARE wireless file transfer from phone to laptop
# ================================================================
# Use USERPROFILE (real Desktop) not expanduser (may give OneDrive Desktop)
def _get_shared_folder():
    userprofile = os.environ.get("USERPROFILE", "")
    
    onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
    if os.path.exists(onedrive_desktop):
        return os.path.join(onedrive_desktop, "shared")

    return os.path.join(userprofile, "Desktop", "shared")

SHARED_FOLDER = _get_shared_folder()
os.makedirs(SHARED_FOLDER, exist_ok=True)

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
    """Returns LAN IP and phone URL used by the QR modal."""
    ip = _get_local_ip()
    return {
        "ip": ip,
        "url": f"http://{ip}:8000/mobile",
        "folder": SHARED_FOLDER
    }


@app.get("/mobile", response_class=HTMLResponse)
def mobile_page():
    html_path = BASE_PATH / "templates" / "mobile.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.post("/mobile/upload")
async def mobile_upload(file: UploadFile = File(...)):
    global recent_upload_count

    try:
        # print("Shared folder:", SHARED_FOLDER)

        file_path = os.path.join(SHARED_FOLDER, file.filename)

        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # print("Saved:", file_path)

        # Increment counter for toast
        recent_upload_count += 1

        return {"status": "success"}

    except Exception as e:
        print("Upload error:", e)
        return {"status": "error", "message": str(e)}

@app.get("/mobile/recent")
def get_recent():
    global recent_upload_count
    count = recent_upload_count
    recent_upload_count = 0  # reset after reading
    return {"count": count}

@app.post("/vault/add-upload")
async def vault_add_upload(file: UploadFile = File(...), password: str = Form(...)):
    """
    Upload a file directly into the vault.
    Encrypts in-place never saved to a normal location.
    original_path is NULL because this file came from phone/browser upload,
    not from an existing location on this PC.
    """
    from backend.vault.vault import verify_password, encrypt_file, ensure_vault_table, VAULT_DIR
    from backend.configuration import DB_LOCATION
    import uuid

    if not verify_password(password):
        return {"success": False, "error": "Incorrect password"}

    original_name = file.filename
    ext = os.path.splitext(original_name)[1].lower()
    encrypted_name = str(uuid.uuid4()) + ".enc"
    encrypted_path = os.path.join(VAULT_DIR, encrypted_name)

    # Save upload to temp
    tmp_path = os.path.join(tempfile.gettempdir(), f"vault_up_{uuid.uuid4()}{ext}")
    try:
        with open(tmp_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        size = os.path.getsize(tmp_path)

        # Encrypt directly to vault
        encrypt_file(tmp_path, encrypted_path, password)

        # Record in DB original_path is NULL (uploaded from browser, no PC path)
        ensure_vault_table()
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vault_files (original_name, original_path, encrypted_name, extension, size)
            VALUES (?, NULL, ?, ?, ?)
        """, (original_name, encrypted_name, ext, size))
        conn.commit()
        conn.close()

        # print(f"Vault upload: {original_name} {encrypted_name}")
        return {"success": True, "message": f"{original_name} encrypted and added to vault"}

    except Exception as e:
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)
        print(f"vault_add_upload error: {e}")
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.get("/pick-files")
def pick_files_dialog():
    """
    Opens a native Windows file picker.
    Returns actual disk paths no file copying needed.
    """
    try:
        result = subprocess.run([
            "powershell", "-Command",
            """
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.OpenFileDialog
            $dialog.Title = 'Select files to index'
            $dialog.Filter = 'Supported Files|*.txt;*.pdf;*.jpg;*.jpeg;*.png;*.csv|All Files|*.*'
            $dialog.Multiselect = $true
            $dialog.InitialDirectory = [Environment]::GetFolderPath('Desktop')
            if ($dialog.ShowDialog() -eq 'OK') {
                $dialog.FileNames -join '|'
            }
            """
        ], capture_output=True, text=True, timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)

        raw = result.stdout.strip()
        if raw:
            paths = [p.strip() for p in raw.split('|') if p.strip()]
            return {"paths": paths}
        return {"paths": []}

    except Exception as e:
        return {"paths": [], "error": str(e)}

@app.post("/index-files-by-path")
def index_files_by_path(request: Request, paths: str = Form(...)):
    """
    Index files by their actual disk paths no copying.
    paths is a pipe-separated list of absolute file paths.
    """
    allowed_ext = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".csv"}
    file_paths = [p.strip() for p in paths.split('|') if p.strip()]

    uploaded = []
    skipped = []

    for file_path in file_paths:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_ext:
            continue

        # Check if already indexed
        try:
            conn = sqlite3.connect(DB_LOCATION)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM files WHERE path = ?",
                (os.path.normpath(file_path),)
            )
            existing = cursor.fetchone()
            conn.close()

            if existing:
                # print(f"Already indexed: {filename}")
                skipped.append(filename)
                continue

        except Exception as e:
            print(f"DB check error: {e}")

        # Queue the actual disk path no copying
        norm_path = os.path.normpath(file_path)
        if norm_path not in queued_files:
            queued_files.add(norm_path)
            file_queue.put(("create", norm_path))
            uploaded.append(filename)
            # print(f"Queued for indexing: {norm_path}")

    if uploaded:
        msg = quote(f"success: Successfully added: {', '.join(uploaded)}")
    elif skipped:
        msg = quote(f"warning: Already indexed: {', '.join(skipped)}")
    else:
        msg = quote("warning: No new files added")

    return RedirectResponse(url=f"/?msg={msg}", status_code=303)

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
        ], capture_output=True, text=True, timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)

        path = result.stdout.strip()

        if path:
            return {"path": path}
        return {"path": None}

    except Exception as e:
        return {"path": None, "error": str(e)}