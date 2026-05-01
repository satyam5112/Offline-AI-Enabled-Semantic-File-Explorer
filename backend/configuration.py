# import os

# # ---- Database Configuration ----
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DB_LOCATION = os.path.join(BASE_DIR, "fileTracker_Status_checker.db")

# # ---- Indexing Configuration ----
# FILES_TABLE = "files"

import os
import sys

# ---- Database Configuration ----
# Use AppData so DB persists correctly on any machine
if getattr(sys, 'frozen', False):
    # Running as .exe — store DB in AppData
    APP_DATA = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DocS AI')
else:
    # Running from source
    APP_DATA = os.path.dirname(os.path.abspath(__file__))

os.makedirs(APP_DATA, exist_ok=True)

BASE_DIR = APP_DATA
DB_LOCATION = os.path.join(APP_DATA, "fileTracker_Status_checker.db")

# ---- Indexing Configuration ----
FILES_TABLE = "files"