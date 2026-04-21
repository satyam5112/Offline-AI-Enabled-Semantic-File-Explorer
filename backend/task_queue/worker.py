import os
import time
from backend.indexer.indexer import process_file
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer
from backend.deleter.deleter import delete_file_records
from backend.task_queue.file_queue import file_queue, queued_files
from backend.task_queue.notifications import notify_user

def worker():
    print("🚀 Worker started...\n")

    while True:
        try:
            task_type, file_path = file_queue.get()

            print(f"\n⚙️ Processing: {task_type} → {file_path}")

            if task_type in ("create", "modify"):
                file_id = process_file(file_path)

                content = extract_file(file_path)

                if not content or len(content.strip()) < 10:
                    print(f"❌ Extraction failed for: {file_path}")
                    print(f"🗑️ Rolling back index for file_id: {file_id}")

                    # ✅ Notify user
                    failed_filename = os.path.basename(file_path)
                    notify_user(f"❌ Data extraction failed for '{failed_filename}'. Indexing deleted. Please try again.")
                    
                    # ✅ Delete index record
                    delete_file_records(file_path)
                    
                    file_queue.task_done()
                    continue

                run_vectorizer(file_id, content)

            elif task_type == "delete":
                delete_file_records(file_path)

        except Exception as e:
            print(f"❌ Worker Error: {e}")
            time.sleep(1)
        finally:
            queued_files.discard(file_path) 
            file_queue.task_done()
            time.sleep(0.3)