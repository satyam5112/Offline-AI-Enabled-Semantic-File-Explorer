import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import your modules
from backend.indexer.indexer import process_file, delete_file_record  
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer, delete_vectors

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".jpg", ".png", ".csv")


class FileHandler(FileSystemEventHandler):

    # ------------------ CREATE ------------------
    def on_created(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
            return

        print(f"\n📁 New file detected: {file_path}")

        self.process_pipeline(file_path)

    # ------------------ MODIFY ------------------
    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
            return

        print(f"\n✏️ File modified: {file_path}")

        # 🔴 Important: Avoid duplicate rapid triggers
        time.sleep(1)

        self.process_pipeline(file_path, is_update=True)

    # ------------------ DELETE ------------------
    def on_deleted(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
            return

        print(f"\n🗑️ File deleted: {file_path}")

        try:
            # ---- STEP 1: Get file_id (from DB using path) ----
            file_id = delete_file_record(file_path)

            # ---- STEP 2: Remove vectors ----
            delete_vectors(file_id)

            print("✅ File removed from system")

        except Exception as e:
            print(f"❌ Error deleting file data: {e}")

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