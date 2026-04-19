from collections import deque

# ✅ Store failed notifications
notification_queue = deque()

def notify_user(message: str):
    print(f"🔔 Notification: {message}")
    notification_queue.append(message)