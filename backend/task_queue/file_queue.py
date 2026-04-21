import importlib.util

# ✅ Load built-in queue module directly bypassing folder conflict
spec = importlib.util.spec_from_file_location(
    "queue_builtin",
    importlib.util.find_spec("queue").origin
)
_queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_queue)

file_queue = _queue.Queue()
queued_files = set()