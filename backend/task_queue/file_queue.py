from queue import Queue

# Queue for file processing
file_queue = Queue()

# To prevent duplicate queue entries
queued_files = set()