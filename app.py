import sys
import os
import time
import threading
import subprocess
import socket
import webbrowser

from PyQt6.QtGui import QIcon, QPixmap, QAction

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel,
    QStatusBar, QSplashScreen, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from torch import layout

# ---- Base paths ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
API_DIR = os.path.join(BACKEND_DIR, "api")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, BACKEND_DIR)

from backend.task_queue.file_queue import file_queue, queued_files


# ---- Get LAN IP ----
def get_local_ip():
    """Returns the LAN IP of this machine (e.g. 192.168.x.x)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---- Signal class for thread-safe UI updates ----
class WorkerSignals(QObject):
    status_update = pyqtSignal(str)


# ---- Start FastAPI in background ----
# def start_fastapi():
#     """
#     Binds to 0.0.0.0 so the server is reachable on the LAN
#     (needed for mobile share). The PyQt browser still connects
#     via 127.0.0.1 — both work simultaneously.
#     """
#     subprocess.Popen(
#         [
#             sys.executable, "-m", "uvicorn",
#             "backend.api.main:app",
#             "--host", "0.0.0.0",   # ← changed from 127.0.0.1
#             "--port", "8000"
#         ],
#         cwd=BASE_DIR,
#         # stdout=subprocess.DEVNULL,
#         # stderr=subprocess.DEVNULL
#     )


# ---- Wait for FastAPI to be ready ----
def wait_for_server(timeout=60):
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
        self._lan_ip = get_local_ip()

        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(BASE_DIR, "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

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
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        # Logo image
        logo_label = QLabel()
        logo_path = os.path.join(BASE_DIR, "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                28, 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)

        # App name
        name_label = QLabel("DocS AI")
        name_label.setStyleSheet("color:#fff; font-size:16px; font-weight:700;")

        title_layout.addWidget(logo_label)
        title_layout.addWidget(name_label)

        toolbar_layout.addWidget(title_widget)
        toolbar_layout.addStretch()

        # ---- LAN IP label (shown after server starts) ----
        self.lan_label = QLabel()
        self.lan_label.setStyleSheet("""
            color: #64748b;
            font-size: 11px;
            padding: 2px 8px;
            border: 1px solid #1e293b;
            border-radius: 6px;
            font-family: monospace;
        """)
        self.lan_label.setVisible(False)  # shown once server is ready
        toolbar_layout.addWidget(self.lan_label)

        layout.addWidget(toolbar)

        # ---- Placeholder UI instead of browser ----
        placeholder = QLabel("🚀 DocS AI is starting...\nOpening in browser")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("""
            color:#ffffff;
            font-size:16px;
            padding:20px;
        """)

        layout.addWidget(placeholder)

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

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())

        menu = QMenu()

        show_action = QAction("Open DocS AI", self)
        quit_action = QAction("Exit", self)

        show_action.triggered.connect(self.show_window)
        quit_action.triggered.connect(self.close)

        menu.addAction(show_action)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()


    def start_server(self):
        # 🚀 Start FastAPI and STORE process
        self.server_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "backend.api.main:app",
                "--host", "0.0.0.0",   
                "--port", "8000",
                "--log-level", "warning"
            ],
            cwd=BASE_DIR,
            # stdout=subprocess.DEVNULL,
            # stderr=subprocess.DEVNULL
        )

        print("⏳ Waiting for server...")

        ready = wait_for_server(timeout=60)

        if ready:
            print("✅ Server is ready!")
            self.server_ready.emit()
        else:
            print("❌ Server failed to start")
            QTimer.singleShot(0, lambda: self.status_bar.showMessage(
                "❌ Server failed to start — try restarting the app"
        ))
            
    def on_server_ready(self):
        # Open in system browser
        webbrowser.open("http://127.0.0.1:8000")

        # Show mobile sharing link
        if self._lan_ip != "127.0.0.1":
            self.lan_label.setText(f"📱 Phone: http://{self._lan_ip}:8000/mobile")
            self.lan_label.setVisible(True)

        self.status_bar.showMessage(
            f"✅ Running — Desktop: http://127.0.0.1:8000   |   "
            f"Phone: http://{self._lan_ip}:8000/mobile"
        )

    def show_window(self):
        self.show()
        self.raise_()          # bring window to front
        self.activateWindow()
        
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "DocS AI",
            "App is running in background",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

# ---- Splash Screen ----
def show_splash():
    splash_widget = QSplashScreen()
    splash_widget.setFixedSize(500, 300)
    splash_widget.setStyleSheet("QSplashScreen { background: #0f172a; border-radius: 16px; }")

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

    from PyQt6.QtGui import QIcon
    icon_path = os.path.join(BASE_DIR, "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    splash = show_splash()
    app.processEvents()

    time.sleep(1)

    window = MainWindow()
    window.hide()

    sys.exit(app.exec())