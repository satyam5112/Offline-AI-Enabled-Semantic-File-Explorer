import os
from backend.task_queue.file_queue import file_queue, queued_files

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".jpg", ".png", ".csv", ".txt")

def is_valid_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def is_ignored_file(path):
    ignored_keywords = [
        ".db",
        ".db-journal",
        ".db-wal",
        ".db-shm",
        "__pycache__"
    ]
    return any(x in path for x in ignored_keywords)


def scan_folder(folder_path):
    print(f"\n🔍 Scanning folder: {folder_path}\n")

    total_files = 0
    queued = 0

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.normpath(os.path.join(root, file))

            total_files += 1

            # ❌ Ignore unwanted files
            if is_ignored_file(file_path):
                continue

            # ❌ Skip unsupported files
            if not is_valid_file(file_path):
                continue

            # ❌ Avoid duplicate queue
            if file_path in queued_files:
                continue

            queued_files.add(file_path)
            file_queue.put(("create", file_path))
            queued += 1

            print(f"📌 Queued: {file_path}")

    print("\n✅ Scan Completed")
    print(f"📊 Total scanned: {total_files}")
    print(f"📥 Added to queue: {queued}\n")