import os
import sqlite3

from backend.configuration import (
    DB_LOCATION,
    TABLE_NAME,
    BASE_FOLDER_ADDRESS
)

print("🚀 Script started")

# -------------------------------
# 1. DB CONNECTION
# -------------------------------
print("📦 Connecting to DB:", DB_LOCATION)

conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()

print("✅ Connected to DB")


# -------------------------------
# 2. CREATE TABLE
# -------------------------------
print("🛠️ Creating table if not exists...")

create_table_query = f'''
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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

print("✅ Table ready:", TABLE_NAME)


# -------------------------------
# 3. SCAN FUNCTION
# -------------------------------
def scan_directory(root):

    print(f"\n📂 Starting scan in: {root}")

    if not os.path.exists(root):
        print("❌ ERROR: Base folder does NOT exist!")
        return

    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        print(f"\n➡️ Entering directory: {dirpath}")

        if not filenames:
            print("⚠️ No files in this directory")

        for file in filenames:
            print(f"   🔍 Found file: {file}")

            full_path = os.path.abspath(os.path.join(dirpath, file))
            print("   📍 Full path:", full_path)

            try:
                stat = os.stat(full_path)
            except FileNotFoundError:
                print("   ❌ File disappeared:", full_path)
                continue

            # RELATIVE PATH
            try:
                relative_path = os.path.relpath(full_path, BASE_FOLDER_ADDRESS)
                relative_path = os.path.normpath(relative_path).replace("\\", "/")
                print("   📌 Relative path:", relative_path)
            except Exception as e:
                print("   ❌ Error in path conversion:", e)
                continue

            # METADATA
            name = file
            extension = os.path.splitext(file)[1]
            size = stat.st_size
            modified_time = int(stat.st_mtime)
            created_time = int(stat.st_ctime)

            folder = os.path.dirname(relative_path).replace("\\", "/")

            print("   📊 Metadata:",
                  name, extension, size, folder)

            # INSERT QUERY
            insert_query = f'''
            INSERT INTO {TABLE_NAME} 
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

                print("   ✅ Inserted/Updated in DB")

                file_count += 1

            except Exception as e:
                print("   ❌ DB Insert Error:", e)

    print(f"\n📈 Total files processed: {file_count}")


# -------------------------------
# 4. RUN SCAN
# -------------------------------
scan_directory(BASE_FOLDER_ADDRESS)


# -------------------------------
# 5. COMMIT
# -------------------------------
print("\n💾 Committing changes to DB...")
conn.commit()
print("✅ Commit done")

# 7. CLOSE DB
# -------------------------------
conn.close()
print("\n🔒 DB connection closed")

# 1. DB CONNECTION
# -------------------------------
print("📦 Connecting to DB:", DB_LOCATION)

conn = sqlite3.connect(DB_LOCATION)
cursor = conn.cursor()

print("✅ Connected to DB")

# -------------------------------
# 6. VERIFY DATA
# -------------------------------
print("\n🔍 Fetching data from DB...")

try:
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cursor.fetchone()[0]
    print(f"📊 Total rows in DB: {count}")
except Exception as e:
    print("❌ Error fetching count:", e)


print("\n--- Sample Data ---")

try:
    cursor.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 10")
    rows = cursor.fetchall()

    if not rows:
        print("⚠️ No data found in DB!")
    else:
        for row in rows:
            print(row)

except Exception as e:
    print("❌ Error fetching rows:", e)


# -------------------------------
# 7. CLOSE DB
# -------------------------------
conn.close()
print("\n🔒 DB connection closed")
