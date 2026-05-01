"""
backend/vault/vault.py
======================
Hidden Vault - file encryption, password management, session handling.

Dependencies:
    pip install cryptography

Default password: 1234
"""

import os
import json
import uuid
import time
import shutil
import hashlib
import sqlite3
import tempfile
import threading

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

# Paths 
# Anchor everything to THIS file's directory so paths are always consistent
_VAULT_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/vault/
BASE_DIR          = os.path.dirname(os.path.dirname(_VAULT_MODULE_DIR))  # project root
VAULT_DIR         = os.path.join(_VAULT_MODULE_DIR, "vault_store")
VAULT_CONFIG      = os.path.join(_VAULT_MODULE_DIR, "vault_config.json")

os.makedirs(VAULT_DIR, exist_ok=True)

# DB location (reuse app DB) 
try:
    from backend.configuration import DB_LOCATION
except Exception:
    DB_LOCATION = os.path.join(BASE_DIR, "backend", "fileTracker_Status_checker.db")

# Default password
DEFAULT_PASSWORD = "1234"

# In-memory session 
# token - expiry timestamp (None = never expires until app restart / nav away)
_session: dict = {"token": None}


#  PASSWORD MANAGEMENT
def _hash_password(password: str) -> str:
    """SHA-256 hash of password (hex string)."""
    return hashlib.sha256(password.encode()).hexdigest()


def _load_config() -> dict:
    try:
        if os.path.exists(VAULT_CONFIG):
            with open(VAULT_CONFIG, "r") as f:
                data = json.load(f)
                # Validate it has the expected key
                if "password_hash" in data:
                    return data
    except Exception as e:
        print(f"vault_config.json read error: {e} - resetting to default")

    # First run or corrupted  create default config
    config = {"password_hash": _hash_password(DEFAULT_PASSWORD)}
    _save_config(config)
    return config


def _save_config(config: dict):
    with open(VAULT_CONFIG, "w") as f:
        json.dump(config, f)


def verify_password(password: str) -> bool:
    config = _load_config()
    return config["password_hash"] == _hash_password(password)

def change_password(old_password: str, new_password: str) -> dict:
    if not verify_password(old_password):
        return {"success": False, "error": "Current password is incorrect"}

    config = _load_config()
    config["password_hash"] = _hash_password(new_password)

    # print("BEFORE SAVE:", config)   #  add this

    _save_config(config)

    # print("AFTER SAVE:", _load_config())  # add this

    return {"success": True}

def is_default_password() -> bool:
    config = _load_config()
    return config["password_hash"] == _hash_password(DEFAULT_PASSWORD)

#  SESSION MANAGEMENT
def create_session() -> str:
    token = str(uuid.uuid4())
    _session["token"] = token
    return token


def validate_session(token: str) -> bool:
    return _session.get("token") is not None and _session["token"] == token


def destroy_session():
    _session["token"] = None



#  ENCRYPTION HELPERS
# # Fixed salt acceptable for local app (not a web server)
_SALT = b"docsvault_salt_v1"

def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=100_000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _get_fernet(password: str) -> Fernet:
    return Fernet(_derive_key(password))


def encrypt_file(src_path: str, dest_path: str, password: str):
    """Encrypt src_path - dest_path using password-derived key."""
    f = _get_fernet(password)
    with open(src_path, "rb") as fp:
        data = fp.read()
    encrypted = f.encrypt(data)
    with open(dest_path, "wb") as fp:
        fp.write(encrypted)


def decrypt_file(src_path: str, dest_path: str, password: str):
    """Decrypt src_path - dest_path using password-derived key."""
    f = _get_fernet(password)
    with open(src_path, "rb") as fp:
        data = fp.read()
    decrypted = f.decrypt(data)
    with open(dest_path, "wb") as fp:
        fp.write(decrypted)

#  DATABASE HELPERS
def ensure_vault_table():
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            original_path TEXT,
            encrypted_name TEXT NOT NULL UNIQUE,
            extension TEXT,
            size INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_vault_files() -> list:
    ensure_vault_table()
    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, original_name, original_path, encrypted_name, extension, size, added_at
        FROM vault_files ORDER BY added_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "original_path": r[2],
            "encrypted_name": r[3],
            "extension": r[4],
            "size": r[5],
            "added_at": r[6]
        }
        for r in rows
    ]

#  VAULT OPERATIONS
def add_to_vault(file_path: str, password: str) -> dict:
    """
    Encrypt a file and move it into the vault.
    Removes it from the normal search index.
    """
    ensure_vault_table()

    if not os.path.exists(file_path):
        return {"success": False, "error": "File not found"}

    original_name = os.path.basename(file_path)
    extension = os.path.splitext(original_name)[1].lower()
    size = os.path.getsize(file_path)
    encrypted_name = str(uuid.uuid4()) + ".enc"
    encrypted_path = os.path.join(VAULT_DIR, encrypted_name)

    try:
        # 1. Encrypt file into vault_store
        encrypt_file(file_path, encrypted_path, password)

        # 2. Record in DB
        conn = sqlite3.connect(DB_LOCATION)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vault_files (original_name, original_path, encrypted_name, extension, size)
            VALUES (?, ?, ?, ?, ?)
        """, (original_name, file_path, encrypted_name, extension, size))

        # 3. Remove from normal files index so it won't appear in search
        cursor.execute("DELETE FROM files WHERE path = ?", (os.path.normpath(file_path),))
        conn.commit()
        conn.close()

        # 4. Delete original file from disk
        norm_path = os.path.normpath(file_path)
        if os.path.exists(norm_path):
            os.remove(norm_path)
            # print(f"Deleted original: {norm_path}")
        else:
            # Try with forward slashes converted (Windows path mismatch)
            alt_path = file_path.replace("/", "\\")
            if os.path.exists(alt_path):
                os.remove(alt_path)
                # print(f"Deleted original (alt path): {alt_path}")
            else:
                print(f"Could not delete original - file not found at: {norm_path}")
                print(f"The file was encrypted into vault but original may still exist on disk.")
                print(f"Please manually delete: {norm_path}")

        # 5. Also delete ALL other indexed copies of same filename
        #    (handles case where same file is in multiple watched folders)
        conn2 = sqlite3.connect(DB_LOCATION)
        cursor2 = conn2.cursor()
        cursor2.execute(
            "SELECT path FROM files WHERE name = ? AND extension = ?",
            (original_name, extension)
        )
        duplicate_paths = [row[0] for row in cursor2.fetchall()]
        cursor2.execute(
            "DELETE FROM files WHERE name = ? AND extension = ?",
            (original_name, extension)
        )
        conn2.commit()
        conn2.close()

        for dupe_path in duplicate_paths:
            norm = os.path.normpath(dupe_path)
            if os.path.exists(norm) and norm != os.path.normpath(file_path):
                try:
                    os.remove(norm)
                    # print(f"Deleted duplicate: {norm}")
                except Exception as del_err:
                    print(f"Could not delete duplicate {norm}: {del_err}")

        return {"success": True, "message": f"{original_name} encrypted and moved to vault"}

    except Exception as e:
        # Cleanup on failure
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)
        print(f"add_to_vault error: {e}")
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(e)}


def remove_from_vault(vault_id: int, password: str, restore_path: str = None) -> dict:
    """
    Decrypt a file and restore it to its original location (or restore_path).
    Re-adds it to the normal search index.
    """
    ensure_vault_table()

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vault_files WHERE id = ?", (vault_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "error": "File not found in vault"}

    _, original_name, original_path, encrypted_name, extension, size, added_at = row
    encrypted_path = os.path.join(VAULT_DIR, encrypted_name)

    # Determine restore destination
    dest = restore_path or original_path or os.path.join(
        os.path.expanduser("~"), "Desktop", original_name
    )

    try:
        decrypt_file(encrypted_path, dest, password)

        # Remove from vault DB
        cursor.execute("DELETE FROM vault_files WHERE id = ?", (vault_id,))
        conn.commit()
        conn.close()

        # Delete encrypted file
        os.remove(encrypted_path)

        return {"success": True, "message": f"{original_name} restored to {dest}", "path": dest}

    except Exception as e:
        conn.close()
        return {"success": False, "error": f"Decryption failed - wrong password or corrupted file: {e}"}


def open_vault_file(vault_id: int, password: str) -> dict:
    """
    Decrypt to a temp file, return the temp path.
    Caller should open it with subprocess and schedule deletion.
    """
    ensure_vault_table()

    conn = sqlite3.connect(DB_LOCATION)
    cursor = conn.cursor()
    cursor.execute("SELECT original_name, encrypted_name FROM vault_files WHERE id = ?", (vault_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "File not found in vault"}

    original_name, encrypted_name = row
    encrypted_path = os.path.join(VAULT_DIR, encrypted_name)

    # Decrypt to temp file with correct extension
    ext = os.path.splitext(original_name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext,
                                      prefix="vault_tmp_", dir=tempfile.gettempdir())
    tmp.close()

    try:
        decrypt_file(encrypted_path, tmp.name, password)

        # Schedule deletion after 60 seconds
        def _delete_later(path):
            time.sleep(60)
            try:
                os.remove(path)
            except Exception:
                pass

        threading.Thread(target=_delete_later, args=(tmp.name,), daemon=True).start()

        return {"success": True, "temp_path": tmp.name, "name": original_name}

    except Exception as e:
        os.remove(tmp.name)
        return {"success": False, "error": f"Decryption failed: {e}"}


def get_vault_stats() -> dict:
    files = get_vault_files()
    total_size = sum(f["size"] or 0 for f in files)
    return {
        "total_files": len(files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "is_default_password": is_default_password()
    }