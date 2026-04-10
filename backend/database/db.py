from gc import get_referents
import sqlite3
from backend.configuration import (
    DB_LOCATION,
    FILES_TABLE,
    FILE_CONTENTS_TABLE
)

# -------------------------------
# DB Connection
# -------------------------------
def get_connection():
    return sqlite3.connect(DB_LOCATION)


# -------------------------------
# Create Tables (Run Once)
# -------------------------------
def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Files Table (already used in indexer)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {FILES_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        extension TEXT,
        size INTEGER,
        modified_time INTEGER,
        created_time INTEGER,
        folder TEXT
    );
    """)

    # File Content Table (for extractor)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {FILE_CONTENTS_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        content TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (file_id) REFERENCES {FILES_TABLE}(id)
    )
    """)

    # -------------------------------
    # Vector Mapping Table (FAISS ↔ Files)
    # -------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vector_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vector_id INTEGER,
        file_id INTEGER,
        chunk_text TEXT,
        chunk_index INTEGER,
        FOREIGN KEY (file_id) REFERENCES Files(id)
    )
    """)

    conn.commit()
    conn.close()


# -------------------------------
# Insert Extracted Content
# -------------------------------
def insert_file_content(file_id, content):
    conn = get_connection()
    cursor = conn.cursor()

    # Check if content already exists
    cursor.execute(f"""
        SELECT id FROM {FILE_CONTENTS_TABLE} WHERE file_id = ?
    """, (file_id,))
    
    result = cursor.fetchone()

    if result:
        # Update existing content
        cursor.execute(f"""
            UPDATE {FILE_CONTENTS_TABLE}
            SET content = ?, last_updated = CURRENT_TIMESTAMP
            WHERE file_id = ?
        """, (content, file_id))
    else:
        # Insert new content
        cursor.execute(f"""
            INSERT INTO {FILE_CONTENTS_TABLE} (file_id, content)
            VALUES (?, ?)
        """, (file_id, content))

    conn.commit()
    conn.close()


# -------------------------------
# Get All Files (for extractor loop)
# -------------------------------
def get_all_files():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT id, path FROM {FILES_TABLE}")
    rows = cursor.fetchall()

    conn.close()

    # Convert to list of dicts
    files = [{"id": row[0], "file_path": row[1]} for row in rows]
    
    # for file in files:
    #     print(file)
    return files

# Function to get the content from file_contents table (for vectorizer)

def get_all_file_contents():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT file_id, content FROM {FILE_CONTENTS_TABLE}")
    rows = cursor.fetchall()

    conn.close()

    return [{"file_id": row[0], "content": row[1]} for row in rows]

# -------------------------------
# Insert Vector Mapping
# -------------------------------
def insert_vector_mapping(vector_id, file_id, chunk_text, chunk_index):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO vector_mapping (vector_id, file_id, chunk_text, chunk_index)
        VALUES (?, ?, ?, ?)
    """, (vector_id, file_id, chunk_text, chunk_index))

    conn.commit()
    conn.close()

def get_vectors_by_file_id(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT vector_id FROM vector_mapping WHERE file_id = ?",
        (file_id,)
    )
    rows = cursor.fetchall()

    conn.close()
    return [{"vector_id": row[0]} for row in rows]

def delete_vector_mappings_by_file_id(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM vector_mapping WHERE file_id = ?",
        (file_id,)
    )
    conn.commit()
    conn.close()