# DocS — Semantic File Search

> Search across your files using natural language, not just keywords.

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## What is DocS?

DocS is a local semantic file search application that runs entirely on your machine. It indexes your files using AI embeddings and lets you search them using natural language — not just exact keyword matches.

Instead of remembering exact filenames, you can search for *"invoice from last month"* or *"project meeting notes"* and DocS finds the most relevant files instantly.

---

## Features

- **Semantic Search** — AI-powered search using sentence embeddings (MiniLM-L6-v2)
- **Multi-format Support** — Indexes PDF, TXT, CSV, JPG, PNG files
- **Hidden Vault** — AES-128 encrypted personal file storage, hidden from search
- **Folder Watcher** — Automatically indexes new files added to watched folders
- **Mobile File Sharing** — Send files from your phone to your PC over WiFi
- **Recent Searches** — Quickly re-run previous searches
- **Recent Results** — See last search results on the home page
- **System Tray** — Runs silently in the background, always ready
- **Auto Startup** — Registers itself to start with Windows automatically
- **Web Interface** — Clean, modern UI accessible from any browser

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Search | FAISS |
| Database | SQLite |
| File Watching | Watchdog |
| PDF Extraction | PyMuPDF |
| OCR | Tesseract + pytesseract |
| Encryption | AES-128 (cryptography) |
| System Tray | pystray + Pillow |
| Frontend | HTML + CSS + Jinja2 |

---

## Project Structure

```
MAJOR PROJECT/
│   app.py                  # Entry point — starts server + tray
│   logo.ico                # App icon
│   logo.svg                # App logo
│   requirements.txt
│
└───backend/
    │   configuration.py    # DB path config
    │
    ├───api/
    │   │   main.py         # FastAPI routes
    │   ├───static/         # CSS, logo
    │   └───templates/      # HTML pages
    │
    ├───automation/         # File watcher
    ├───extractor/          # PDF, TXT, CSV, image extractors
    ├───indexer/            # File indexer
    ├───search/             # Semantic search logic
    ├───task_queue/         # Background worker + progress
    ├───vault/              # Encrypted vault
    └───vectorizer/         # FAISS index + embedder
```

---

## Installation

### Option 1 — Run from source

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/docs-ai.git
cd docs-ai
```

**2. Create a virtual environment**
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Install Tesseract OCR** (required for image search)

Download from: https://github.com/UB-Mannheim/tesseract/wiki

**5. Run the app**
```bash
python app.py
```

The app starts the backend server and opens the UI in your default browser automatically.

---

### Option 2 — Install from installer (Windows)

1. Download `DocS_Setup.exe` from the releases page
2. Run the installer and follow the wizard
3. DocS will be installed with desktop shortcut and auto-startup enabled
4. Launch from desktop shortcut or Start Menu

---

## Usage

### Search
- Open the app — it launches in your browser at `http://127.0.0.1:8000`
- Type a natural language query in the search bar
- Filter by file type or folder if needed
- Click **Open File** to open any result directly

### Add Files
- **Upload files** — drag and drop or click to upload from the search page
- **Watch a folder** — add a folder path to auto-index all files inside it
- **Mobile upload** — scan the QR code from your phone to send files over WiFi

### Vault
- Navigate to the **Vault** page
- Default password is `1234` — change it immediately after first use
- Add files to encrypt them with AES-128
- Original files are permanently deleted after encryption
- Vault files are hidden from all search results

---

## Building the Installer

**Step 1 — Build the executable**
```bash
python -m PyInstaller app.py --name DocS --icon=logo.ico --add-data "backend:backend" --add-data "logo.ico:." --hidden-import=pystray --hidden-import=PIL --hidden-import=PIL.Image --noconsole
```

**Step 2 — Install NSIS**

Download from: https://nsis.sourceforge.io

**Step 3 — Build the installer**
```bash
makensis installer.nsi
```

This produces `DocS_Setup.exe` — a full wizard installer with uninstall support.

---

## Notes

- DocS runs entirely **locally** — no data is sent to any server
- The vault uses **AES-128 encryption** — files cannot be recovered without the password
- Supported file types: `.pdf`, `.txt`, `.csv`, `.jpg`, `.jpeg`, `.png`
- Mobile file sharing works over **local WiFi only**
- Auto-startup is registered under `HKEY_CURRENT_USER` — no admin rights needed

---

## License

MIT License — free to use, modify and distribute.

---

*Built with Python, FastAPI, and sentence-transformers.*