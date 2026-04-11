import os
import sqlite3
from backend.vectorizer.faiss_index import index, save_index
from backend.configuration import (
    DB_LOCATION,
    BASE_FOLDER_ADDRESS
)

def delete_file_records(file_path):
    conn = sqlite3.connect(DB_LOCATION, timeout=10)
    cursor = conn.cursor()

    relative_path = os.path.relpath(file_path, BASE_FOLDER_ADDRESS)
    

    try:
        print(f"🧹 Deleting records for: {relative_path}")

        # 🔍 Step 1: Get file_id
        cursor.execute(
            "SELECT id FROM files WHERE path = ?",
            (relative_path,)
        )
        result = cursor.fetchone()

        if not result:
            print("⚠️ File not found in DB")
            return

        file_id = result[0]

        cursor.execute(
            "SELECT id FROM vector_mapping WHERE file_id = ?",
            (file_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            print(f"⚠️ No vectors found for file_id {file_id}")
            return

        ids_to_delete = [row[0] for row in rows]


        # 🗑️ Step 2: Delete from files table
        cursor.execute(
            "DELETE FROM files WHERE id = ?",
            (file_id,)
        )

        # Step 3: Remove from FAISS ----

        import numpy as np
        ids_np = np.array(ids_to_delete, dtype="int64")

        index.remove_ids(ids_np)
        # 🗑️ Step 4: Delete from vector_mapping
        cursor.execute(
            "DELETE FROM vector_mapping WHERE file_id = ?",
            (file_id,)
        )

        conn.commit()
        save_index(index)

        print(f"✅ Deleted file_id {file_id} from DB")

    except Exception as e:
        print(f"❌ Deletion Error: {e}")

    finally:
        conn.close()