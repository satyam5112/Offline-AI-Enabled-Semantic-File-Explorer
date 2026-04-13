import threading
from backend.automation.file_watcher import start_watching
from backend.search.cli_search import run_cli
import os
from backend.configuration import BASE_FOLDER_ADDRESS

if __name__ == "__main__":

    watcher_thread = threading.Thread(
        target=start_watching,
        args=(BASE_FOLDER_ADDRESS,),
        daemon=True
    )
    watcher_thread.start()

    run_cli()