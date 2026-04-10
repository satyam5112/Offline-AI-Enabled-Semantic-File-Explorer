import sqlite3
from backend.configuration import DB_LOCATION
import numpy as np
from backend.vectorizer.chunker import chunk_text
from backend.vectorizer.embedder import get_embeddings
from backend.vectorizer.faiss_index import index, save_index



def run_vectorizer(file_id, content):

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    try:
        chunks = chunk_text(content)
        print("Chunks Created")
        embeddings = get_embeddings(chunks)
        print("Embeddings Generated")
        
        if len(embeddings) == 0:
            print(f"[WARNING] Skipping file_id {file_id} due to empty content")
            return

        vector_ids = []

        for i, chunk in enumerate(chunks):
            # ✅ Insert into DB FIRST (auto-increment ID)
            cursor.execute(
                """
                INSERT INTO vector_mapping (file_id, chunk_index, chunk_text)
                VALUES (?, ?, ?)
                """,
                (file_id, i, chunk)
            )

            vector_id = cursor.lastrowid  # ✅ SAFE ID from SQLite
            vector_ids.append(vector_id)

        conn.commit()

        # ---- Add to FAISS ----
        vectors_np = np.array(embeddings).astype("float32")
        ids_np = np.array(vector_ids).astype("int64")

        index.add_with_ids(vectors_np, ids_np)

        # ---- Save index ----
        save_index(index)

        print(f"✅ Vectorized file_id {file_id}")

    except Exception as e:
        print(f"❌ Vectorization Error: {e}")

    finally:
        conn.close()

def delete_vectors(file_id):
        
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    try:
        # ---- Get vector_ids for this file ----
        cursor.execute(
            "SELECT vector_id FROM vector_mapping WHERE file_id = ?",
            (file_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            print("⚠️ No vectors found for this file")
            return

        vector_ids = [row[0] for row in rows]

        # ---- Remove from FAISS ----
        index.remove_ids(np.array(vector_ids, dtype="int64"))

        # ---- Delete from DB ----
        cursor.execute(
            "DELETE FROM vector_mapping WHERE file_id = ?",
            (file_id,)
        )
        conn.commit()

        # ---- Save updated FAISS index ----
        save_index(index)

        print(f"🧹 Deleted vectors for file_id {file_id}")

    except Exception as e:
        print(f"❌ Vector Deletion Error: {e}")

    finally:
        conn.close()