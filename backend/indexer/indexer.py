import os
import re
import sqlite3

from backend.configuration import (
    DB_LOCATION,
    FILES_TABLE,
)
# from backend.tempCodeRunnerFile import TABLE_NAME   

# 1. DB CONNECTION

# conn = sqlite3.connect(DB_LOCATION)
# cursor = conn.cursor()

# 2. CREATE TABLE

# print("🛠️ Creating table if not exists...")

# create_table_query = f'''
# CREATE TABLE IF NOT EXISTS {FILES_TABLE} (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     path TEXT NOT NULL UNIQUE,
#     name TEXT NOT NULL,
#     extension TEXT,
#     size INTEGER,
#     modified_time INTEGER,
#     created_time INTEGER,
#     folder TEXT
# );
# '''

# cursor.execute(create_table_query)

# 3. SCAN FUNCTION

def scan_directory(root):

    if not os.path.exists(root):
        print("❌ ERROR: Base folder does NOT exist!")
        return

    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # print(f"\n➡️ Entering directory: {dirpath}")

        if not filenames:
            print("⚠️ No files in this directory")

        for file in filenames:

            full_path = os.path.abspath(os.path.join(dirpath, file))

            try:
                stat = os.stat(full_path)
            except FileNotFoundError:
                print("   ❌ File disappeared:", full_path)
                continue

            # RELATIVE PATH
            try:
                relative_path = file_path
                
            except Exception as e:
                print("   ❌ Error in path conversion:", e)
                continue

            # METADATA
            name = file
            extension = os.path.splitext(file)[1]
            size = stat.st_size
            modified_time = int(stat.st_mtime)
            created_time = int(stat.st_birthtime)

            folder = os.path.normpath(os.path.dirname(relative_path)).replace("\\", "/")

            # INSERT QUERY
            insert_query = f'''
            INSERT INTO {FILES_TABLE} 
            (path, name, extension, size, modified_time, created_time, folder)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                size = excluded.size,
                modified_time = excluded.modified_time;
            '''

            try:
                cursor.execute(insert_query, (
                    relative_path,
                    name,
                    extension,
                    size,
                    modified_time,
                    created_time,
                    folder
                ))

                file_count += 1

            except Exception as e:
                print("   ❌ DB Insert Error:", e)


def process_file(file_path, update=False):

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    # ---- METADATA EXTRACTION ----
    file_name = os.path.basename(file_path)
    path = os.path.normpath(file_path)
    extension = os.path.splitext(file_path)[1].lower()
    size = os.path.getsize(file_path)
    modified_time = int(os.path.getmtime(file_path))
    created_time = int(os.path.getctime(file_path))
    folder = os.path.normpath(os.path.dirname(path)).replace("\\", "/")

    try:
        # ---- STEP 1: CHECK BY EXACT PATH ----
        cursor.execute("SELECT id FROM files WHERE path = ?", (path,))
        result = cursor.fetchone()

        # ---- STEP 2: CHECK BY NAME + EXTENSION (catches temp vs original) ----
        if not result:
            cursor.execute(
                "SELECT id FROM files WHERE name = ? AND extension = ?",
                (file_name, extension)
            )
            result = cursor.fetchone()
            if result:
                print(f"⚠️ Already indexed (different path): {file_name}")

        # ------------------ UPDATE CASE ------------------
        if result:
            file_id = result[0]

            if update:
                cursor.execute("""
                    UPDATE files
                    SET name = ?, extension = ?, size = ?,
                        modified_time = ?, created_time = ?, folder = ?
                    WHERE id = ?
                """, (file_name, extension, size, modified_time,
                      created_time, folder, file_id))
                conn.commit()
                print(f"♻️ Updated: {file_name} (ID: {file_id})")
            else:
                print(f"⚠️ Already exists: {file_name} (ID: {file_id})")

            return file_id

        # ------------------ INSERT CASE ------------------
        cursor.execute(f"""
            INSERT INTO {FILES_TABLE}
            (path, name, extension, size, modified_time, created_time, folder)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (path, file_name, extension, size, modified_time,
              created_time, folder))

        conn.commit()

        file_id = cursor.lastrowid
        if not file_id:
            raise ValueError("File insert failed, stopping pipeline")
        print(f"✅ Indexed: {file_name} (ID: {file_id})")

        return file_id

    except Exception as e:
        print(f"❌ Indexing Error: {e}")
        return None

    finally:
        conn.close()


# if __name__ == "__main__":
#     print("🚀 Script started")

#     # Start bulk indexing
#     scan_directory(BASE_FOLDER_ADDRESS)

#     conn.commit()
#     conn.close()