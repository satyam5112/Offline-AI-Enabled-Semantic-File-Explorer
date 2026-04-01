import faiss
import numpy as np

dimension = 384  # for MiniLM model

index = faiss.IndexFlatL2(dimension)


def add_to_index(vectors):
    vectors = np.array(vectors).astype('float32')
    index.add(vectors)


def search(query_vector, k=5):
    query_vector = np.array([query_vector]).astype('float32')
    distances, indices = index.search(query_vector, k)
    return distances, indices