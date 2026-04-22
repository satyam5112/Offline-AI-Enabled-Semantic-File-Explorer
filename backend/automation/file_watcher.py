import time
import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import your modules
from backend.indexer.indexer import process_file
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer
from backend.task_queue.file_queue import file_queue, queued_files
from backend.task_queue.worker import worker

# Start worker thread
threading.Thread(target=worker, daemon=True).start()

recent_files = {}
watched_paths = set()
active_watchers = {}

DEBOUNCE_TIME = 2  # seconds
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".jpg", ".png", ".csv", ".txt")


# ✅ Ignore system / unwanted files
def is_ignored_file(path):
    ignored_keywords = [
        ".db",
        ".db-journal",
        ".db-wal",
        ".db-shm",
        "__pycache__"
    ]
    return any(x in path for x in ignored_keywords)


# ✅ Allow only supported files
def is_valid_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


class FileHandler(FileSystemEventHandler):

    # ------------------ CREATE ------------------
    def on_created(self, event):
        if event.is_directory:
            return

        file_path = os.path.normpath(event.src_path)

        # ✅ Ignore unwanted files
        if is_ignored_file(file_path):
            return

        # ✅ Allow only supported files
        if not is_valid_file(file_path):
            return

        # ✅ Prevent duplicates
        if file_path in queued_files:
            return

        queued_files.add(file_path)

        print(f"📁 Queued (create): {file_path}")
        file_queue.put(("create", file_path))

    # ------------------ MODIFY ------------------
    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = os.path.normpath(event.src_path)

        # ✅ Ignore unwanted files
        if is_ignored_file(file_path):
            return

        # ✅ Allow only supported files
        if not is_valid_file(file_path):
            return

        # ✅ Prevent duplicates
        if file_path in queued_files:
            return

        queued_files.add(file_path)

        print(f"✏️ Queued (modify): {file_path}")
        file_queue.put(("modify", file_path))

    # ------------------ DELETE ------------------
    def on_deleted(self, event):
        if event.is_directory:
            return

        file_path = os.path.normpath(event.src_path)

        # ✅ Ignore unwanted files
        if is_ignored_file(file_path):
            return

        print(f"🗑️ Queued (delete): {file_path}")
        file_queue.put(("delete", file_path))

    # ------------------ COMMON PIPELINE ------------------
    def process_pipeline(self, file_path, is_update=False):
        try:
            # ---- STEP 1: Indexing ----
            file_id = process_file(file_path, update=is_update)
            print("✅ Indexed")

            # ---- STEP 2: Extraction ----
            content = extract_file(file_path)
            print("✅ Content Extracted")

            # ---- STEP 3: Vectorization ----
            run_vectorizer(file_id, content)
            print("✅ Vectorized & Stored")

        except Exception as e:
            print(f"❌ Error processing file: {e}")


def start_watching(folder_path):
    global watched_paths, active_watchers

    if folder_path in watched_paths:
        print(f"⚠️ Already watching: {folder_path}")
        return

    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=True)

    watched_paths.add(folder_path)
    active_watchers[folder_path] = observer  # ✅ store reference

    print(f"👀 Watching folder: {folder_path}")

    observer.start()

def stop_watching(folder_path):
    global watched_paths, active_watchers

    observer = active_watchers.get(folder_path)

    if not observer:
        print(f"⚠️ Not watching: {folder_path}")
        return

    observer.stop()
    observer.join()

    watched_paths.discard(folder_path)
    del active_watchers[folder_path]

    print(f"🛑 Stopped watching: {folder_path}")

# if __name__ == "__main__":
#     start_watching(r"C:\Users\singh\OneDrive\Desktop")