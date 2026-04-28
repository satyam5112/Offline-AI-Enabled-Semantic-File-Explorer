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

# --------------------------
# Fix path for PyInstaller
# --------------------------
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

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
    if not is_port_in_use(PORT):
        subprocess.Popen(
            [
                "uvicorn",
                "backend.api.main:app",
                "--host", "127.0.0.1",
                "--port", str(PORT)
            ],
            creationflags=0x08000000
        )

        # wait for server
        for _ in range(10):
            if is_port_in_use(PORT):
                break
            time.sleep(1)

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
    image = Image.open(resource_path("logo.ico"))

    menu = Menu(
        MenuItem("Open DocS", lambda icon, item: open_ui()),
        MenuItem("Exit", exit_app)
    )

    icon = Icon("DocS", image, "DocS", menu)
    icon.run()

# --------------------------
# MAIN
# --------------------------

# Start backend in background
threading.Thread(target=start_backend, daemon=True).start()

# Open browser once
time.sleep(2)
open_ui()

# Run tray (keeps app alive)
run_tray()