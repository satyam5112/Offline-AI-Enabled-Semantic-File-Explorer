import subprocess
import webbrowser
import time
import socket
import sys
import threading
import os

from pystray import Icon, MenuItem, Menu
from PIL import Image

PORT = 8000

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

# --------------------------
# Add to startup
# --------------------------
def add_to_startup():
    try:
        import winreg
        exe_path = sys.executable if not getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "DocS", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        print("✅ Added to startup")
    except Exception as e:
        print(f"⚠️ Could not add to startup: {e}")

add_to_startup()

# --------------------------
# Fix path for PyInstaller
# --------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --------------------------
# Check if backend running
# --------------------------
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

# --------------------------
# Start backend
# --------------------------
def start_backend():
    print("Starting backend...")
    import uvicorn
    from backend.api.main import app
    print("Backend imported successfully")

    uvicorn.run(app, host="127.0.0.1", port=8000)

# --------------------------
# Open UI
# --------------------------
def open_ui():
    webbrowser.open("http://127.0.0.1:8000")

# --------------------------
# Exit app
# --------------------------
def exit_app(icon, item):
    icon.stop()
    sys.exit()

# --------------------------
# Tray icon
# --------------------------
def run_tray():
    try:
        icon_path = resource_path("logo.ico")
        image = Image.open(icon_path).convert("RGBA").resize((64, 64))
    except Exception as e:
        print(f"⚠️ Could not load icon: {e}")
        image = Image.new('RGB', (64, 64), color='blue')

# --------------------------
# MAIN
# --------------------------

# Prevent multiple instances
import socket
import threading

# Start backend in thread
threading.Thread(target=start_backend, daemon=True).start()

# Wait until backend is ready
for _ in range(15):
    if is_port_in_use(PORT):
        break
    time.sleep(1)

# Open browser
if is_port_in_use(PORT):
    open_ui()
else:
    print("Backend failed to start")

# Run tray
run_tray()