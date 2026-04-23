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
        context={"stats": status(), "msg": msg, "folders": folders}
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
                context={"results": [], "count": 0, "stats": status(), "msg": ""}
            )

        results = search_files(
            query=query,
            file_type=file_type if file_type else None,
            folder=folder if folder else None
        )

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"results": results, "stats": status(), "msg": ""}
        )

    except Exception as e:
        print("❌ ERROR:", e)
        return {"error": str(e)}

@app.get("/search-ui")
def search_ui_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stats": status(), "msg": ""}
    )

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
    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_ext:
            print(f"❌ Skipped unsupported file: {filename}")
            continue

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

    # ✅ Fixed - return OUTSIDE the loop
    if uploaded:
        msg = quote(f"success: Successfully added: {', '.join(uploaded)}")
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