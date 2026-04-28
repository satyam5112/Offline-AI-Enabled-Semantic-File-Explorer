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
        # ---- Start Transaction ----
        conn.execute("BEGIN")

        if file_id is None:
            # print("❌ Invalid file_id. Skipping vectorization.")
            return

        chunks = chunk_text(content)
        # print("Chunks Created")

        embeddings = get_embeddings(chunks)
        # print("Embeddings Generated")

        if len(embeddings) == 0:
            print(f"[WARNING] Skipping file_id {file_id} due to empty content")
            conn.rollback()
            return

        if len(chunks) != len(embeddings):
            raise ValueError("Mismatch between chunks and embeddings")

        # ---- Remove old vectors (important) ----
        cursor.execute("DELETE FROM vector_mapping WHERE file_id = ?", (file_id,))

        vector_ids = []

        # ---- Insert into DB ----
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            cursor.execute(
                """
                INSERT INTO vector_mapping (file_id, chunk_text, chunk_index)
                VALUES (?, ?, ?)
                """,
                (file_id, chunk, i)
            )

            vector_id = cursor.lastrowid
            vector_ids.append(vector_id)

        # ---- Add to FAISS ----
        vectors_np = np.array(embeddings).astype("float32")
        ids_np = np.array(vector_ids).astype("int64")

        index.add_with_ids(vectors_np, ids_np)

        # ---- Save index ----
        save_index(index)

        # ---- Commit only if EVERYTHING succeeds ----
        conn.commit()

        # print(f"✅ Vectorized file_id {file_id}")

    except Exception as e:
        # ❌ If anything fails → rollback DB
        conn.rollback()
        print(f"❌ Vectorization Error: {e}")

    finally:
        conn.close()
