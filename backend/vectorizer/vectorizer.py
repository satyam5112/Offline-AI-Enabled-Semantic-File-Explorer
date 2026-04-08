from backend.database.db import get_all_file_contents, insert_vector_mapping
from backend.vectorizer.chunker import chunk_text
from backend.vectorizer.embedder import get_embeddings
from backend.vectorizer.faiss_index import add_to_index
from backend.vectorizer.faiss_index import index
import faiss

# Mapping storage (IMPORTANT)
vector_store = []

def run_vectorizer(file_id, content):
    # records = get_all_file_contents()

    # for record in records:
        # file_id = record["file_id"]
        # content = record["content"]

        chunks = chunk_text(content)
        # print("Chunking completed. Number of chunks:", len(chunks))

        embeddings = get_embeddings(chunks)

        # 🔥 ADD THIS CHECK
        if len(embeddings) == 0:
            print(f"[WARNING] Skipping file_id {file_id} due to empty content")
            return
        
        # print("Embedding completed. Number of embeddings:", len(embeddings))

        # 🔥 Step 3: Get current FAISS index position BEFORE adding
        current_vector_id = index.ntotal

        # Step 4: Add vectors to FAISS

        add_to_index(embeddings)
        # print(f"[INFO] Total vectors in FAISS index: {index.ntotal}")

        # Store mapping
        for i, chunk in enumerate(chunks):
            # print(f"[DEBUG] Inserting mapping for vector_id: {current_vector_id + i}")
            
            insert_vector_mapping(
                vector_id=current_vector_id + i,
                file_id=file_id,
                chunk_text=chunk,
                chunk_index=i
            )
        
        faiss.write_index(index, "backend/vectorizer/faiss_index.bin")

        # print("[INFO] Vectorization + Mapping completed successfully")


if __name__ == "__main__":
    run_vectorizer()