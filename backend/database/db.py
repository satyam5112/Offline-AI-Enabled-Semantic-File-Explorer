from gc import get_referents
import sqlite3
from backend.configuration import (
    DB_LOCATION,
    FILES_TABLE,
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
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vector_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vector_id INTEGER,
        file_id INTEGER,
        chunk_text TEXT,
        chunk_index INTEGER,
        FOREIGN KEY (file_id) REFERENCES files(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recent_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL UNIQUE,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recent_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        file_name TEXT,
        file_path TEXT,
        score REAL,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

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