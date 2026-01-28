# backend/notifications.py
from datetime import datetime, timezone
from typing import List, Dict

# In-memory notification store (replace with DB in production)
NOTIFICATIONS: List[Dict] = []

def send_notification(user_id: str, message: str, notif_type: str = "info"):
    NOTIFICATIONS.append({
        "user_id": user_id,
        "message": message,
        "type": notif_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "read": False
    })

def get_user_notifications(user_id: str) -> List[Dict]:
    return [n for n in NOTIFICATIONS if n["user_id"] == user_id]

def mark_all_read(user_id: str):
    for n in NOTIFICATIONS:
        if n["user_id"] == user_id:
            n["read"] = True

# Placeholder for email notification integration
def send_email_notification(user_email: str, message: str):
    # Integrate with email service (e.g., SMTP, SendGrid)
    pass
