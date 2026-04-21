from fileinput import filename
from importlib.resources import path
import os
from os import path
import tempfile
import threading
import subprocess
import shutil
import sqlite3
import tempfile


from backend.automation.file_watcher import watched_paths
from backend.scanner.folder_scanner import scan_folder
from backend.automation.file_watcher import start_watching
from backend.task_queue.file_queue import file_queue, queued_files
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Form, UploadFile, File
from fastapi import UploadFile, File
from typing import List
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from backend.search.search import search_files
from backend.configuration import DB_LOCATION
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from backend.automation.file_watcher import start_watching
from backend.resetter.reset import reset_db
from backend.vectorizer.faiss_index import index, save_index
from backend.task_queue.notifications import notification_queue
from backend.resetter.reset import reset_db
from urllib.parse import quote,unquote


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Start file watcher when FastAPI starts
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    print("✅ File watcher started alongside FastAPI")
    yield
    print("🛑 FastAPI shutting down")

app = FastAPI(lifespan=lifespan)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory="backend/api/templates")
app.mount("/static", StaticFiles(directory="backend/api/static"), name="static")


# ---- Request Model ----
class SearchRequest(BaseModel):
    query: str
    file_type: str | None = None
    folder: str | None = None

def run_watcher():
    start_watching(r"C:\Users\singh\OneDrive\Desktop")

@app.get("/status")
def status():

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM files")
    total_files = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM vector_mapping")
    total_vectors = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.txt'")
    txt_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.pdf'")
    pdf_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension IN ('.jpg','.jpeg','.png')")
    img_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM files WHERE extension='.csv'")
    csv_count = cursor.fetchone()[0]
    conn.close()
    return {"total_files": total_files, "total_vectors": total_vectors,
            "txt_count": txt_count, "pdf_count": pdf_count,
            "img_count": img_count, "csv_count": csv_count}

@app.get("/")
def home(request: Request, msg: str = ""):
    msg = unquote(msg)  # ✅ decode the URL encoded message
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"stats": status(), "msg": msg}
    )

@app.get("/files")
def my_files(request: Request):
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, extension, folder, path FROM files ORDER BY name")
    rows = cursor.fetchall()
    conn.close()

    # Group by folder type
    files = {"Text Files": [], "PDF Files": [], "Image Files": [], "CSV Files": []}
    
    for name, extension, folder, path in rows:
        if folder in files:
            files[folder].append({"name": name, "extension": extension, "path": path})

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
                request=request,          # ✅ pass as keyword arg
                name="index.html",
                context={"results": [], "count": 0}
            )

        results = search_files(
            query=query,
            file_type=file_type if file_type else None,
            folder=folder if folder else None
        )

        return templates.TemplateResponse(
            request=request,              # ✅ pass as keyword arg
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

    # Normalize path (safety)
    full_path = os.path.normpath(path)

    print("📂 OPEN REQUEST:", full_path)  # debug

    # Check if file exists
    if not os.path.exists(full_path):
        return {"error": f"File not found: {full_path}"}

    return FileResponse(full_path)

@app.post("/upload")
def upload_files(files: list[UploadFile] = File(...)):

    allowed_ext = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".csv"}

    # temp directory (OS managed, no duplication in project)
    temp_dir = os.path.join(tempfile.gettempdir(), "ai_search_uploads")
    os.makedirs(temp_dir, exist_ok=True)

    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_ext:
            print(f"❌ Skipped unsupported file: {filename}")
            continue

        temp_path = os.path.join(temp_dir, filename)

        try:
            # Save temporarily
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # print(f"📥 Uploaded (temp): {temp_path}")

            if temp_path not in queued_files:
                queued_files.add(temp_path)
                file_queue.put(("create", temp_path))

        except Exception as e:
            print(f"❌ Upload error for {filename}: {e}")

        return RedirectResponse(url="/", status_code=303)

@app.post("/reset")
def reset_db_route():
    try:
        result = reset_db()
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"❌ Reset Error: {e}")
        return {"error": str(e)}

@app.get("/notifications")
def get_notifications():
    messages = list(notification_queue)
    notification_queue.clear()  
    return {"notifications": messages}

@app.get("/open-native")
def open_native(path: str):
    try:
        import subprocess

        print(f"📥 Raw path received: '{path}'")

        # ✅ Fix missing backslash between folder and filename
        folders = ["Text Files", "PDF Files", "Image Files", "CSV Files"]
        for folder in folders:
            if path.startswith(folder) and not path.startswith(folder + "\\"):
                path = folder + "\\" + path[len(folder):]
                break

        if not os.path.isabs(path):
            full_path = path
        else:
            full_path = path

        print(f"🔍 Trying to open: {full_path}")

        if os.path.exists(full_path):
            subprocess.Popen(f'start "" "{full_path}"', shell=True)
            return {"status": "opened"}

        return {"error": f"File not found: {full_path}"}

    except Exception as e:
        return {"error": str(e)}
    
@app.post("/add-folder")
def add_folder(path: str = Form(...)):
    try:
        if path in watched_paths:
            return RedirectResponse(url="/?msg=warning:Folder already being watched",status_code=303)
        if not os.path.exists(path):
            return {"error": "Invalid folder path"}

        # ✅ Run scan in background
        threading.Thread(target=scan_folder, args=(path,), daemon=True).start()

        # ✅ Run watcher in background
        threading.Thread(target=start_watching, args=(path,), daemon=True).start()

        return RedirectResponse(url="/?msg=success:Folder added successfully", status_code=303)

    except Exception as e:
        return {"error": str(e)}
