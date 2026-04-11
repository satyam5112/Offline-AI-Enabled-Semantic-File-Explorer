import time
from backend.queue.file_queue import file_queue, queued_files
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer
from backend.indexer.indexer import process_file
from backend.deleter.deleter import delete_file_records


def worker():
    print("🚀 Worker started...\n")

    while True:
        try:
            task_type, file_path = file_queue.get()

            print(f"\n⚙️ Processing: {task_type} → {file_path}")

            if task_type in ("create", "modify"):
                file_id = process_file(file_path)

                content = extract_file(file_path)

                if content:
                    run_vectorizer(file_id, content)

            elif task_type == "delete":
                delete_file_records(file_path)

            # ✅ Remove from dedup set AFTER processing
            if file_path in queued_files:
                queued_files.remove(file_path)

            file_queue.task_done()

            time.sleep(0.3)

        except Exception as e:
            print(f"❌ Worker Error: {e}")
            time.sleep(1)