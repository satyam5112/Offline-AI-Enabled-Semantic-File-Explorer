import os
import sqlite3

from backend.configuration import (
    DB_LOCATION,
    FILES_TABLE,
    BASE_FOLDER_ADDRESS
)
from backend.tempCodeRunnerFile import TABLE_NAME

# print("🚀 Script started")

# -------------------------------
# 1. DB CONNECTION
# -------------------------------
# print("📦 Connecting to DB:", DB_LOCATION)

conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()

# print("✅ Connected to DB")


# -------------------------------
# 2. CREATE TABLE
# -------------------------------
# print("🛠️ Creating table if not exists...")

create_table_query = f'''
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
'''

cursor.execute(create_table_query)

# print("✅ Table ready:", FILES_TABLE)


# -------------------------------
# 3. SCAN FUNCTION
# -------------------------------
def scan_directory(root):

    # print(f"\n📂 Starting scan in: {root}")

    if not os.path.exists(root):
        print("❌ ERROR: Base folder does NOT exist!")
        return

    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # print(f"\n➡️ Entering directory: {dirpath}")

        if not filenames:
            print("⚠️ No files in this directory")

        for file in filenames:
            # print(f"   🔍 Found file: {file}")

            full_path = os.path.abspath(os.path.join(dirpath, file))
            # print("   📍 Full path:", full_path)

            try:
                stat = os.stat(full_path)
            except FileNotFoundError:
                print("   ❌ File disappeared:", full_path)
                continue

            # RELATIVE PATH
            try:
                relative_path = os.path.relpath(full_path, BASE_FOLDER_ADDRESS)
                relative_path = os.path.normpath(relative_path).replace("\\", "/")
                # print("   📌 Relative path:", relative_path)
            except Exception as e:
                print("   ❌ Error in path conversion:", e)
                continue

            # METADATA
            name = file
            extension = os.path.splitext(file)[1]
            size = stat.st_size
            modified_time = int(stat.st_mtime)
            created_time = int(stat.st_birthtime)

            folder = os.path.normpath(os.path.dirname(relative_path)).replace("\\", "/")
            # print("   📊 Metadata:", name, extension, size, folder)

            # INSERT QUERY
            insert_query = f'''
            INSERT INTO {FILES_TABLE} 
            (path, name, extension, size, modified_time, created_time, folder)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                size = excluded.size,
                modified_time = excluded.modified_time;
            '''

            try:
                cursor.execute(insert_query, (
                    relative_path,
                    name,
                    extension,
                    size,
                    modified_time,
                    created_time,
                    folder
                ))

                # print("   ✅ Inserted/Updated in DB")

                file_count += 1

            except Exception as e:
                print("   ❌ DB Insert Error:", e)

    # print(f"\n📈 Total files processed: {file_count}")


# -------------------------------
# 4. RUN SCAN
# -------------------------------
# scan_directory(BASE_FOLDER_ADDRESS)


# -------------------------------
# 5. COMMIT
# -------------------------------
# print("\n💾 Committing changes to DB...")
conn.commit()
print("✅ Commit done")

# 7. CLOSE DB
# -------------------------------
conn.close()
# print("\n🔒 DB connection closed")

# 8. DB CONNECTION
# -------------------------------
# print("📦 Connecting to DB:", DB_LOCATION)

conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()

# print("✅ Connected to DB")

# -------------------------------
# 9. VERIFY DATA
# -------------------------------
# print("\n🔍 Fetching data from DB...")

try:
    cursor.execute(f"SELECT COUNT(*) FROM {FILES_TABLE}")
    count = cursor.fetchone()[0]
    # print(f"📊 Total rows in DB: {count}")
except Exception as e:
    print("❌ Error fetching count:", e)


# print("\n--- Sample Data ---")

# try:
#     cursor.execute(f"SELECT * FROM {FILES_TABLE} LIMIT 10")
#     rows = cursor.fetchall()

#     if not rows:
#         print("⚠️ No data found in DB!")
#     else:
#         for row in rows:
#             # print(row)

# except Exception as e:
#     print("❌ Error fetching rows:", e)


# -------------------------------
# 10. CLOSE DB
# -------------------------------
conn.close()
# print("\n🔒 DB connection closed")

def process_file(file_path):
    import sqlite3
    import os
    from datetime import datetime

    conn = sqlite3.connect("fileTracker_Status_checker.db")
    cursor = conn.cursor()

    # ---- METADATA EXTRACTION ----
    file_name = os.path.basename(file_path)
    relative_path = os.path.relpath(file_path)
    extension = os.path.splitext(file_path)[1].lower()
    size = os.path.getsize(file_path)
    modified_time = int(os.path.getmtime(file_path))
    created_time = int(os.path.getctime(file_path))
    folder = os.path.normpath(os.path.dirname(relative_path)).replace("\\", "/")

    try:
        # ---- INSERT INTO DB ----
        cursor.execute(f"""
            INSERT INTO files (path, name, extension, size, modified_time, created_time, folder)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (relative_path, file_name, extension, size, modified_time, created_time, folder))

        conn.commit()

        # ---- GET FILE ID ----
        file_id = cursor.lastrowid

        print(f"✅ Indexed: {file_name} (ID: {file_id})")
        return file_id

    except sqlite3.IntegrityError:
        # ---- HANDLE DUPLICATE ----
        print(f"⚠️ Already exists: {file_name}")

        cursor.execute("SELECT id FROM files WHERE path = ?", (relative_path,))
        file_id = cursor.fetchone()[0]
        return file_id

    finally:
        conn.close()


def delete_file_record(file_path):
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()

    try:
        # ---- STEP 1: Get file_id ----
        cursor.execute(f"SELECT id FROM {FILES_TABLE} WHERE path = ?", (file_path,))
        result = cursor.fetchone()

        if not result:
            print("⚠️ File not found in DB")
            return None

        file_id = result[0]

        # ---- STEP 2: Delete record ----
        cursor.execute(f"DELETE FROM {FILES_TABLE} WHERE id = ?", (file_id,))
        conn.commit()

        print(f"🗑️ Deleted from DB (ID: {file_id})")

        return file_id

    except Exception as e:
        print(f"❌ DB Delete Error: {e}")
        return None

    finally:
        conn.close()

# if __name__ == "__main__":
#     print("🚀 Script started")

#     # Start bulk indexing
#     scan_directory(BASE_FOLDER_ADDRESS)

#     conn.commit()
#     conn.close()
