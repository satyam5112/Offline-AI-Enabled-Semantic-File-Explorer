import subprocess
import webbrowser
import time
import sys

# Windows: hide terminal
CREATE_NO_WINDOW = 0x08000000

# Start backend (FastAPI)
subprocess.Popen(
    [
        sys.executable, "-m", "uvicorn",
        "backend.api.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ],
    creationflags=CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# Wait for server
time.sleep(3)

# Open browser
webbrowser.open("http://127.0.0.1:8000")