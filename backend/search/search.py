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
# 🔥 Highlight matched words
# -------------------------------
def highlight_text(text, query):
    words = query.lower().split()
    for word in words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub(lambda m: f"[{m.group(0)}]", text)
    return text


# -------------------------------
# 🔥 Keyword scoring
# -------------------------------
def keyword_score(text, words):
    score = 0
    text = text.lower()
    for w in words:
        score += text.count(w)
    return score


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

        # ---- Step 3: FAISS search (extra for filtering) ----
        distances, indices = index.search(query_vector, top_k * 3)
        # print("Indices:", indices)
        # print("Distances:", distances)
        results = []

        for distance, idx in zip(distances[0], indices[0]):

            if distance > 1.5:
                continue

            if idx == -1:
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

            # ---- Step 4: Filtering ----
            if file_type and extension != file_type:
                continue

            if folder and folder not in file_folder:
                continue

            # ---- Step 5: Scoring ----
            semantic_score = 1 / (1 + distance)
            keyword_match = keyword_score(chunk_text, clean_words)

            final_score = (0.8 * semantic_score) + (0.2 * keyword_match)

            threshold = 0.3
            if final_score < threshold:
                continue

            # ---- Step 6: Highlight ----
            highlighted_chunk = highlight_text(chunk_text, query)

            results.append({
                "file_name": file_name,
                "file_path": file_path,
                "folder": file_folder,
                "chunk": highlighted_chunk,
                "score": final_score
            })

        # ---- Step 7: Sort by score ----
        results = sorted(results, key=lambda x: x["score"], reverse=True)

        # ---- Step 8: Remove duplicate files ----
        seen = set()
        final_results = []

        for r in results:
            if r["file_path"] not in seen:
                seen.add(r["file_path"])
                final_results.append(r)

        return final_results[:5]
    
    except Exception as e:
        print(f"❌ Search Error: {e}")
        return []

    finally:
        conn.close()