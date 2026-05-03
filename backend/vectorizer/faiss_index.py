import faiss
import os
import sys

# ---- Dynamic path ----
if getattr(sys, 'frozen', False):
    # Running as .exe — store in AppData
    _APP_DATA = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'DocS AI')
else:
    # Running from source — store next to this file
    _APP_DATA = os.path.dirname(os.path.abspath(__file__))

os.makedirs(_APP_DATA, exist_ok=True)


FAISS_INDEX_FILE = os.path.join(_APP_DATA, "faiss_index.bin")
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