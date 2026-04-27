import faiss
import sqlite3
import numpy as np
import re
from sentence_transformers import SentenceTransformer
from torch import threshold
from backend.configuration import DB_LOCATION
import os

# ---- Load embedding model ----
model = SentenceTransformer("all-MiniLM-L6-v2")

# ---- Load FAISS index ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "vectorizer", "faiss_index.bin")

index = faiss.read_index(INDEX_PATH)
#  to check wheteher FAISS index is loading correctly or not
# print("🚀 FAISS index loaded")
# print("📊 Total vectors in index:", index.ntotal)
# print("📁 Index path:", INDEX_PATH)

# -------------------------------
# 🔥 Clean query
# -------------------------------
def clean_query(query):
    stopwords = {
        "my", "is", "so", "the", "a", "an", "of", "for",
        "to", "in", "on", "at", "by", "with",
        "this", "that", "these", "those",
        "and", "or", "but",
        "please", "find", "give", "show",
        "me", "i", "you"
    }
    words = [w.strip() for w in query.lower().split()]
    return [w for w in words if w not in stopwords and len(w) > 2]


# -------------------------------
# 🔥 Keyword scoring
# -------------------------------
def keyword_score(text, words):
    score = 0
    text = text.lower()
    for w in words:
        score += text.count(w)
    return score

# Highlight Keywords Feature

def highlight_text(text, keywords):
    for word in keywords:
        if word:
            text = text.replace(word, f"<mark>{word}</mark>")
    return str(text)

# -------------------------------
# 🔍 MAIN SEARCH FUNCTION
# -------------------------------
def search_files(query, top_k=30, file_type=None, folder=None):

    conn = sqlite3.connect(DB_LOCATION, timeout=10)
    cursor = conn.cursor()

    try:
        print(f"\n🔍 Query: {query}")

        # ---- Step 1: Clean query ----
        clean_words = clean_query(query)

        # ---- Step 2: Query embedding ----
        query_vector = model.encode([query])
        query_vector = np.array(query_vector).astype("float32")

        # ---- Step 3: FAISS search ----
        distances, indices = index.search(query_vector, top_k * 3)

        semantic_results = []

        for distance, idx in zip(distances[0], indices[0]):

            if distance > 1.5 or idx == -1:
                continue

            cursor.execute("""
                SELECT f.name, f.path, f.extension, f.folder, vm.chunk_text
                FROM vector_mapping vm
                JOIN files f ON vm.file_id = f.id
                WHERE vm.id = ?
            """, (int(idx),))

            row = cursor.fetchone()
            if not row:
                continue

            file_name, file_path, extension, file_folder, chunk_text = row

            # ---- Filtering ----
            if file_type and extension != file_type:
                continue

            if folder and folder not in file_folder:
                continue

            # ---- Scoring ----
            semantic_score = float(1 / (1 + distance))
            keyword_match = float(keyword_score(chunk_text, clean_words))

            final_score = float((0.8 * semantic_score) + (0.2 * keyword_match))

            highlighted_chunk = highlight_text(chunk_text.lower(), clean_words)

            semantic_results.append({
                "file_name": file_name,
                "file_path": file_path,
                "folder": file_folder,
                "chunk": highlighted_chunk,
                "score": float(final_score),
                "source": "semantic"
            })

        # =========================================================
        # 🔥 NEW: KEYWORD SEARCH (independent of FAISS)
        # =========================================================

        keyword_results = []

        if clean_words:
            conditions = " OR ".join(["vm.chunk_text LIKE ?" for _ in clean_words])
            values = [f"%{word}%" for word in clean_words]

            cursor.execute(f"""
                SELECT f.name, f.path, f.extension, f.folder, vm.chunk_text
                FROM vector_mapping vm
                JOIN files f ON vm.file_id = f.id
                WHERE {conditions}
            """, values)

            rows = cursor.fetchall()

            for row in rows:
                file_name, file_path, extension, file_folder, chunk_text = row

                if file_type and extension != file_type:
                    continue

                if folder and folder not in file_folder:
                    continue

                score = float(keyword_score(chunk_text, clean_words))

                if score == 0:
                    continue

                # normalize keyword score
                score = min(score / 10, 1.0)

                keyword_results.append({
                    "file_name": file_name,
                    "file_path": file_path,
                    "folder": file_folder,
                    "chunk": highlight_text(chunk_text[:200].lower(), clean_words),
                    "score": score,
                    "source": "keyword"
                })
                
        # =========================================================
        # 🔥 FILE NAME KEYWORD SEARCH (NEW)
        # =========================================================

        file_name_results = []

        if clean_words:
            conditions = " OR ".join(["f.name LIKE ?" for _ in clean_words])
            values = [f"%{word}%" for word in clean_words]

            cursor.execute(f"""
                SELECT name, path, extension, folder
                FROM files f
                WHERE {conditions}
            """, values)

            rows = cursor.fetchall()

            for row in rows:
                file_name, file_path, extension, file_folder = row

                if file_type and extension != file_type:
                    continue

                if folder and folder not in file_folder:
                    continue

                # 🔥 Strong boost for filename match
                score = 1.2

                file_name_results.append({
                    "file_name": file_name,
                    "file_path": file_path,
                    "folder": file_folder,
                    "chunk": f"📄 File name match: {file_name}",
                    "score": score,
                    "source": "filename"
                })
        # =========================================================
        # 🔥 MERGE BOTH RESULTS
        # =========================================================

        combined = semantic_results + keyword_results + file_name_results

        seen = set()
        final_results = []

        for r in combined:
            path = r["file_path"]

            if path not in seen:
                seen.add(path)
                final_results.append(r)

        # ---- Final sorting ----
        final_results = sorted(final_results, key=lambda x: x["score"], reverse=True)

        return final_results[:5]

    except Exception as e:
        print(f"❌ Search Error: {e}")
        return []

    finally:
        conn.close()