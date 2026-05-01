import os
from backend.task_queue.file_queue import file_queue, queued_files
from backend.task_queue.progress import progress

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".jpg", ".png", ".csv", ".txt")

def is_valid_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS

def is_ignored_file(path):
    ignored_keywords = [
        ".db", ".db-journal", ".db-wal",
        ".db-shm", "__pycache__"
    ]
    return any(x in path for x in ignored_keywords)

def scan_folder(folder_path):
    # print(f"\nScanning folder: {folder_path}\n")

    # ---- Step 1: Collect all valid files first ----
    valid_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.normpath(os.path.join(root, file))

            if not os.path.isfile(file_path):
                continue

            if is_ignored_file(file_path):
                continue
            if not is_valid_file(file_path):
                continue
            if file_path in queued_files:
                continue

            valid_files.append(file_path)

    # ---- Step 2: Update progress total ----
    progress["total"] = len(valid_files)
    progress["processed"] = 0
    progress["active"] = True
    progress["current_file"] = ""

    # print(f"Total valid files found: {len(valid_files)}")

    # ---- Step 3: Queue all files ----
    for file_path in valid_files:
        queued_files.add(file_path)
        file_queue.put(("create", file_path))
        # print(f"Queued: {file_path}")

    # print("\n Scan Completed")
    # print(f"Added to queue: {len(valid_files)}\n")