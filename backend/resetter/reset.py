import sqlite3
import shutil
import os
from backend.configuration import DB_LOCATION
from backend.vectorizer.faiss_index import index, save_index

def reset_db():
    try:
        # ---- Step 1: Clear Database Tables ----
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM files")
        cursor.execute("DELETE FROM vector_mapping")

        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='files'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='vector_mapping'")

        conn.commit()
        conn.close()

        # print("Database cleared")

        # ---- Step 2: Reset FAISS Index ----
        index.reset()
        save_index(index)

        # print("FAISS index reset")

        return {"message": "Database reset successful"}

    except Exception as e:
        print(f"Reset error: {e}")
        return {"error": str(e)}