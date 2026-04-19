import os
import threading
import subprocess
import shutil

from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from backend.search.search import search_files
from backend.configuration import BASE_FOLDER_ADDRESS
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from backend.automation.file_watcher import start_watching
from backend.configuration import BASE_FOLDER_ADDRESS



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Start file watcher when FastAPI starts
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    print("✅ File watcher started alongside FastAPI")
    yield
    print("🛑 FastAPI shutting down")

app = FastAPI(lifespan=lifespan)


templates = Jinja2Templates(directory="backend/api/templates")
app.mount("/static", StaticFiles(directory="backend/api/static"), name="static")


# ---- Request Model ----
class SearchRequest(BaseModel):
    query: str
    file_type: str | None = None
    folder: str | None = None

def run_watcher():
    start_watching(BASE_FOLDER_ADDRESS)

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
            context={"results": results, "count": len(results)}
        )

    except Exception as e:
        print("❌ ERROR:", e)
        return {"error": str(e)}


@app.get("/open")
def open_file(path: str):
    full_path = os.path.join(BASE_FOLDER_ADDRESS, path)

    if not os.path.exists(full_path):
        return {"error": "File not found"}

    return FileResponse(full_path)

@app.post("/reset")
def reset_db():
    import sqlite3
    from backend.configuration import DB_LOCATION
    from backend.vectorizer.faiss_index import index, save_index

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM files")
    cursor.execute("DELETE FROM vector_mapping")

    conn.commit()
    conn.close()

    index.reset()
    save_index(index)

    return {"message": "Database reset successful"}

@app.post("/upload")
def upload_files(files: list[UploadFile] = File(...)):

    allowed_ext = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".csv"}
    
    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in allowed_ext:
            continue

        folder_map = {
            ".txt": "Text files",
            ".pdf": "PDF Files",
            ".jpg": "Image Files",
            ".jpeg": "Image Files",
            ".png": "Image Files",
            ".csv": "CSV Files"
        }

        folder = folder_map.get(ext, "Others")
        folder_path = os.path.join(BASE_FOLDER_ADDRESS, folder)

        os.makedirs(folder_path, exist_ok=True)

        save_path = os.path.join(folder_path, filename)

        if os.path.exists(save_path):
            print(f"⚠️ File already exists: {filename}")
            continue

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    return {"status": "uploaded", "files": [f.filename for f in files]}
    # return RedirectResponse(url="/", status_code=303)

@app.get("/status")
def status():
    import sqlite3
    from backend.configuration import DB_LOCATION
    from backend.vectorizer.faiss_index import index

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM files")
    file_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vector_mapping")
    vector_count = cursor.fetchone()[0]

    conn.close()

    return {
        "files": file_count,
        "vectors": vector_count,
        "faiss_vectors": index.ntotal
    }


# ---- Root Endpoint (test) ----
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"results": [], "count": 0}
    )

@app.get("/search-ui")
def search_ui_get(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"results": [], "count": 0}
    )