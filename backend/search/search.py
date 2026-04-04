import faiss
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from backend.configuration import DB_LOCATION

# ---- Load embedding model ----
model = SentenceTransformer("all-MiniLM-L6-v2")

# ---- Load FAISS index ----
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INDEX_PATH = os.path.join(BASE_DIR, "vectorizer", "faiss_index.bin")

index = faiss.read_index(INDEX_PATH)

index = faiss.read_index(INDEX_PATH)

# ---- Connect DB ----
conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()


def clean_query(query):
    stopwords = {"my", "is", "so", "the", "a", "an", "of", "for",
        "to", "in", "on", "at", "by", "with",
        "this", "that", "these", "those",
        "and", "or", "but",
        "please", "find", "give", "show",
        "me", "i", "you"}
    words = [w.strip() for w in query.lower().split()]
    return [w for w in words if w not in stopwords and len(w) > 2]


def search_files(query, top_k=3):

    # Step 1: Clean the query
    clean_words = clean_query(query)
    
    # Step 2: Convert query → vector
    query_vector = model.encode([query])
    query_vector = np.array(query_vector).astype("float32")

    # Step 3: Search FAISS
    distances, indices = index.search(query_vector, top_k)

    results = []

    # Step 3: Map FAISS IDs → file paths
    results = []

    for idx in indices[0]:
        if idx == -1:
            continue

        cursor.execute("""
            SELECT f.name, f.path
            FROM vector_mapping vm
            JOIN files f ON vm.file_id = f.id
            WHERE vm.vector_id = ?
        """, (int(idx),))

        row = cursor.fetchone()

        if row:
            file_name = row[0].lower()

            score = 0
            for word in clean_words:
                if word in file_name:
                    score += 1

            results.append({
                "file_name": row[0],
                "file_path": row[1],
                "score": score
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    final_results = []
    seen = set()

    for r in results:
        if r["file_path"] not in seen:
            seen.add(r["file_path"])
            final_results.append(r)

    return final_results


# ---- CLI testing ----
if __name__ == "__main__":
    while True:
        query = input("\nEnter search query: ")
        if query.lower() == "exit":
            break

        results = search_files(query)

        print("\nResults:")
        for r in results:
            print(f"{r['file_name']} → {r['file_path']}")