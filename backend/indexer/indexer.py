# This module handles the core indexing logic:
# - Extracts metadata
# - Inserts/updates file records in the database
# - Returns file_id for downstream processing (vectorization, etc.)

import os
import sqlite3

from backend.configuration import (
    DB_LOCATION,
    FILES_TABLE,
)

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