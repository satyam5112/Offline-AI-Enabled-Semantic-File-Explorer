import sys
import os
import time
import threading
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QStatusBar, QSplashScreen
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QIcon, QColor

# ---- Base paths ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
API_DIR = os.path.join(BACKEND_DIR, "api")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, BACKEND_DIR)

from backend.queue.file_queue import file_queue, queued_files
from backend.configuration import BASE_FOLDER_ADDRESS

# ---- Signal class for thread-safe UI updates ----
class WorkerSignals(QObject):
    status_update = pyqtSignal(str)

# ---- Start FastAPI in background ----
def start_fastapi():
    subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.api.main:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# ---- Wait for FastAPI to be ready ----
def wait_for_server(timeout=30):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:8000")
            return True
        except:
            time.sleep(0.5)
    return False

# ---- Main Window ----
class MainWindow(QMainWindow):
    server_ready = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocS AI — Semantic File Search")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)

        # ---- Central widget ----
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Top toolbar ----
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet("background:#0f172a; border-bottom: 1px solid #1e293b;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 0, 16, 0)
        toolbar_layout.setSpacing(10)

        # App title
        title_label = QLabel("⚡ DocS AI")
        title_label.setStyleSheet("color:#fff; font-size:16px; font-weight:700;")
        toolbar_layout.addWidget(title_label)

        toolbar_layout.addStretch()

        # ---- Add Files button ----
        self.add_btn = QPushButton("📁  Add Files")
        self.add_btn.setFixedHeight(32)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:pressed { background: #1e40af; }
        """)
        self.add_btn.clicked.connect(self.pick_files)
        toolbar_layout.addWidget(self.add_btn)

        # ---- Add Folder button ----
        self.folder_btn = QPushButton("📂  Add Folder")
        self.folder_btn.setFixedHeight(32)
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setStyleSheet("""
            QPushButton {
                background: #0f172a;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1e293b; color: #fff; }
            QPushButton:pressed { background: #1e293b; }
        """)
        self.folder_btn.clicked.connect(self.pick_folder)
        toolbar_layout.addWidget(self.folder_btn)

        # ---- Refresh button ----
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #0f172a;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover { background: #1e293b; color: #fff; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_page)
        toolbar_layout.addWidget(self.refresh_btn)

        layout.addWidget(toolbar)

        # ---- Browser ----
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("about:blank"))
        layout.addWidget(self.browser)

        # ---- Status bar ----
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #0f172a;
                color: #64748b;
                font-size: 12px;
                padding: 2px 12px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("⏳ Starting server...")

        # ---- Connect server ready signal ----
        self.server_ready.connect(self.on_server_ready)

        # ---- Start FastAPI in background thread ----
        threading.Thread(target=self.start_server, daemon=True).start()

    def start_server(self):
        start_fastapi()
        ready = wait_for_server()
        if ready:
            self.server_ready.emit()

    def on_server_ready(self):
        self.browser.setUrl(QUrl("http://127.0.0.1:8000"))
        self.status_bar.showMessage("✅ Server running — http://127.0.0.1:8000")

    def refresh_page(self):
        self.browser.reload()

    # ---- Pick individual files ----
    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Index",
            os.path.expanduser("~"),
            "Supported Files (*.txt *.pdf *.jpg *.jpeg *.png *.csv)"
        )

        if not files:
            return

        self.status_bar.showMessage(f"⏳ Indexing {len(files)} file(s)...")
        threading.Thread(
            target=self.index_files,
            args=(files,),
            daemon=True
        ).start()

    # ---- Pick entire folder ----
    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Index",
            os.path.expanduser("~")
        )

        if not folder:
            return

        # Collect all supported files from folder
        allowed_ext = {".txt", ".pdf", ".jpg", ".jpeg", ".png", ".csv"}
        files = []
        for root, dirs, filenames in os.walk(folder):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in allowed_ext:
                    files.append(os.path.join(root, filename))

        if not files:
            self.status_bar.showMessage("⚠️ No supported files found in folder")
            return

        self.status_bar.showMessage(f"⏳ Indexing {len(files)} file(s) from folder...")
        threading.Thread(
            target=self.index_files,
            args=(files,),
            daemon=True
        ).start()

    # ---- Index files via queue ----
    def index_files(self, file_paths):
        added = 0
        skipped = 0

        for path in file_paths:
            if path in queued_files:
                skipped += 1
                continue

            queued_files.add(path)
            file_queue.put(("create", path))
            added += 1

        # ---- Update status and refresh page ----
        msg = f"✅ Queued {added} file(s) for indexing"
        if skipped:
            msg += f" ({skipped} skipped — already queued)"

        # Use timer to update UI from main thread
        QTimer.singleShot(500, lambda: self.status_bar.showMessage(msg))

        # Refresh after indexing completes (give worker time)
        QTimer.singleShot(3000, self.refresh_page)

# ---- Splash Screen ----
def show_splash():
    splash_widget = QSplashScreen()
    splash_widget.setFixedSize(500, 300)
    splash_widget.setStyleSheet("""
        QSplashScreen {
            background: #0f172a;
            border-radius: 16px;
        }
    """)

    layout = QVBoxLayout(splash_widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title = QLabel("⚡ DocS AI")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet("color:#fff; font-size:32px; font-weight:800;")

    subtitle = QLabel("Semantic File Search")
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setStyleSheet("color:#64748b; font-size:14px;")

    loading = QLabel("Starting server...")
    loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    loading.setStyleSheet("color:#3b82f6; font-size:12px; margin-top:20px;")

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addWidget(loading)

    return splash_widget

# ---- Entry point ----
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("DocS AI")
    app.setStyle("Fusion")

    # Show splash
    splash = show_splash()
    splash.show()
    app.processEvents()

    # Short delay for splash
    time.sleep(1)

    # Show main window
    window = MainWindow()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())