import sqlite3
import shutil
import os
from backend.configuration import DB_LOCATION, BASE_FOLDER_ADDRESS
from backend.vectorizer.faiss_index import index, save_index

def reset_db():
    # ---- Step 1: Clear Database Tables ----
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM files")
    cursor.execute("DELETE FROM vector_mapping")

    cursor.execute("DELETE FROM sqlite_sequence WHERE name='files'")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='vector_mapping'")

    conn.commit()
    conn.close()
    print("✅ Database tables cleared")

    # ---- Step 2: Reset FAISS Index ----
    index.reset()
    save_index(index)
    print("✅ FAISS index reset")

    # ---- Step 3: Delete files only, keep folders ----
    if os.path.exists(BASE_FOLDER_ADDRESS):
        for folder in os.listdir(BASE_FOLDER_ADDRESS):
            folder_path = os.path.join(BASE_FOLDER_ADDRESS, folder)

            if os.path.isdir(folder_path):
                # Delete files inside folder
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)

                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"🗑️ Deleted: {file}")

                print(f"✅ Cleared folder: {folder}")

    print("✅ Physical files deleted, folders preserved")

    return {"message": "Database reset successful"}