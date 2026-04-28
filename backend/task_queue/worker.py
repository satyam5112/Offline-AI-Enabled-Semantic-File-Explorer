import os
import time
import threading
from backend.indexer.indexer import process_file
from backend.extractor.extractor import extract_file
from backend.vectorizer.vectorizer import run_vectorizer
from backend.deleter.deleter import delete_file_records
from backend.task_queue.file_queue import file_queue, queued_files
from backend.task_queue.progress import progress

def get_timeout(file_path):
    """Dynamic timeout based on file size"""
    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)  # size in MB

        if size_mb < 1:
            return 30       # < 1MB   → 30 seconds
        elif size_mb < 5:
            return 60       # 1-5MB   → 1 minute
        elif size_mb < 20:
            return 180      # 5-20MB  → 3 minutes
        elif size_mb < 50:
            return 300      # 20-50MB → 5 minutes
        else:
            return 600      # > 50MB  → 10 minutes

    except Exception:
        return 60           # default 1 minute if size unknown

def process_with_timeout(func, args, timeout):
    """Run a function with a timeout — returns (result, success)"""
    result = [None]
    error = [None]
    finished = threading.Event()

    def target():
        try:
            result[0] = func(*args)
        except Exception as e:
            error[0] = e
        finally:
            finished.set()

    t = threading.Thread(target=target, daemon=True)
    t.start()
    finished.wait(timeout=timeout)

    if not finished.is_set():
        return None, False  # timed out
    if error[0]:
        return None, False  # errored
    return result[0], True  # success

def worker():
    print("🚀 Worker started...\n")

    while True:
        task_type, file_path = None, None
        try:
            task_type, file_path = file_queue.get(timeout=60)

            progress["active"] = True
            progress["current_file"] = os.path.basename(file_path)

            # ✅ Get dynamic timeout based on file size
            timeout = get_timeout(file_path)
            size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
            # print(f"\n⚙️ Processing: {task_type} → {file_path}")
            print(f"📦 Size: {size_mb:.2f}MB | ⏱️ Timeout: {timeout}s")

            if task_type in ("create", "modify"):
                try:
                    # ✅ Index
                    file_id, ok = process_with_timeout(
                        process_file, (file_path,), timeout
                    )
                    if not ok:
                        raise Exception("Indexing timed out or failed")

                    # ✅ Extract — give more time for large files
                    content, ok = process_with_timeout(
                        extract_file, (file_path,), timeout * 2
                    )
                    if not ok or not content or len(content.strip()) < 10:
                        raise Exception("Extraction timed out or returned empty")

                    # ✅ Vectorize
                    _, ok = process_with_timeout(
                        run_vectorizer, (file_id, content), timeout
                    )
                    if not ok:
                        raise Exception("Vectorization timed out")

                    # ✅ Success
                    progress["processed"] += 1
                    progress["success_files"].append(os.path.basename(file_path))
                    # print(f"✅ Done: {os.path.basename(file_path)}")

                except Exception as e:
                    print(f"❌ Failed: {file_path} → {e}")
                    progress["failed_files"].append(
                        f"{os.path.basename(file_path)} ({size_mb:.1f}MB)"
                    )
                    try:
                        delete_file_records(file_path)
                    except:
                        pass

            elif task_type == "delete":
                delete_file_records(file_path)

        except Exception as e:
            if file_queue.unfinished_tasks == 0 or "Empty" in type(e).__name__:
                if progress["active"] and progress["total"] > 0:
                    progress["active"] = False
                    progress["report_ready"] = True
                    print("✅ All files processed — report ready")
            else:
                print(f"❌ Worker Error: {e}")
            time.sleep(1)

        finally:
            if file_path:
                queued_files.discard(file_path)

            try:
                file_queue.task_done()
            except ValueError:
                pass

            if file_queue.unfinished_tasks == 0 and progress["active"]:
                progress["active"] = False
                progress["report_ready"] = True
                print("✅ Queue empty — report ready")

            time.sleep(0.3) 