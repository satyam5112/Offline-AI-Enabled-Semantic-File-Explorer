import faiss
import os

FAISS_INDEX_FILE = "backend/vectorizer/faiss_index.bin"
DIMENSION = 384

def create_index():
    base_index = faiss.IndexFlatL2(DIMENSION)
    return faiss.IndexIDMap(base_index)


def load_index():
    if os.path.exists(FAISS_INDEX_FILE):
        idx = faiss.read_index(FAISS_INDEX_FILE)

        # SAFETY CHECK
        if not isinstance(idx, faiss.IndexIDMap):
            # print("Old FAISS index detected. Recreating...")
            return create_index()

        return idx

    return create_index()


def save_index(index):
    faiss.write_index(index, FAISS_INDEX_FILE)\

index = load_index()