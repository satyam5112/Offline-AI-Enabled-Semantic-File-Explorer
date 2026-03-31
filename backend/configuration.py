import os

# ---- Database Configuration ----
DB_LOCATION = os.path.abspath("fileTracker_Status_checker.db")

# ---- Indexing Configuration ----
FILES_TABLE = "files"   # or "files" depending on your schema
FILE_CONTENTS_TABLE = "FileContents"   # or "file contents of each file" depending on your schema

# ---- Filesystem Configuration ----
BASE_FOLDER_ADDRESS = os.path.abspath(
    os.path.join("backend", "files_collection")
)