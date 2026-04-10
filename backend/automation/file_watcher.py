import time
import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import your modules
from backend.indexer.indexer import process_file, delete_file_record  
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer, delete_vectors
from backend.queue.file_queue import file_queue, queued_files
from backend.queue.worker import worker

# Start worker thread
threading.Thread(target=worker, daemon=True).start()

recent_files = {}

DEBOUNCE_TIME = 2  # seconds
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".jpg", ".png", ".csv")


class FileHandler(FileSystemEventHandler):

    # ------------------ CREATE ------------------
    def on_created(event):
        if event.is_directory:
            return

        file_path = event.src_path

        if file_path in queued_files:
            return

        queued_files.add(file_path)

        print(f"📁 Queued (create): {file_path}")
        file_queue.put(("create", file_path))

    # ------------------ MODIFY ------------------
    def on_modified(event):
        if event.is_directory:
            return
        
        file_path = event.src_path

        if file_path in queued_files:
            return

        queued_files.add(file_path)

        print(f"✏️ Queued (modify): {file_path}")
        file_queue.put(("modify", event.src_path))

    # ------------------ DELETE ------------------

    def on_deleted(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        # 🔥 Always process delete (even if not in set)
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
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=True)

    print(f"👀 Watching folder: {folder_path}")
    observer.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    BASE_FOLDER_ADDRESS = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "files_collection")
    )
    start_watching(BASE_FOLDER_ADDRESS)