import os

# ---- Database Configuration ----
DB_LOCATION = os.path.abspath("fileTracker_Status_checker.db")

# ---- Indexing Configuration ----
TABLE_NAME = "files"   # or "files" depending on your schema

# ---- Filesystem Configuration ----
BASE_FOLDER_ADDRESS = os.path.abspath(
    os.path.join("backend", "files_collection")
)