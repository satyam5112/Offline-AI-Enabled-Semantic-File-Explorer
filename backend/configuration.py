import os

# ---- Database Configuration ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_LOCATION = os.path.join(BASE_DIR, "fileTracker_Status_checker.db")

# ---- Indexing Configuration ----
FILES_TABLE = "files"