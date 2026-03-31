import os
import sqlite3

from backend.configuration import (
    DB_LOCATION,
    TABLE_NAME,
    BASE_FOLDER_ADDRESS
)

# print(DB_LOCATION,TABLE_NAME, BASE_FOLDER_ADDRESS,sep="\n")

conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()

def scan_directory(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for file in filenames:
            # full_path = os.path.join(dirpath, file)
            full_path = os.path.abspath(os.path.join(dirpath, file))
            try:
                stat = os.stat(full_path)
            except FileNotFoundError:
                continue
            name = file
            extension = os.path.splitext(file)[1]
            size = stat.st_size
            modified_time = int(stat.st_mtime)
            created_time = int(stat.st_ctime)

            params = (full_path, name, extension, size, modified_time, created_time)
            print(params)

            query_to_store_metadata = '''
            INSERT INTO files (path, name, extension, size, modified_time, created_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                size = excluded.size,
                modified_time = excluded.modified_time;
            '''

            cursor.execute(
                query_to_store_metadata,
                params
            )


SCRIPT_for_table_creation = '''CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    path TEXT NOT NULL UNIQUE,     -- absolute path
    name TEXT NOT NULL,            -- file name
    extension TEXT,                -- .pdf, .txt, .py
    size INTEGER,                  -- bytes
    modified_time INTEGER,         -- last modified (epoch)
    created_time INTEGER,          -- optional
    file_hash TEXT                 -- optional (for change detection)
);
'''
cursor.executescript(SCRIPT_for_table_creation)


scan_directory(BASE_FOLDER_ADDRESS)

# Commit all changes to DB
conn.commit()

# Fetch and display DB contents
print("\n--- Indexed Files in DB ---")
cursor.execute("SELECT id, path, name, extension, size, modified_time, created_time FROM files")
rows = cursor.fetchall()

for row in rows:
    print(row)

# Close DB connection
conn.close()