# backend/audit_trail.py
from typing import List, Dict
from datetime import datetime, timezone

# In-memory audit log (replace with DB in production)
AUDIT_LOG: List[Dict] = []

def log_action(user_id: str, action: str, details: dict = None):
    AUDIT_LOG.append({
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def get_audit_log(user_id: str = None) -> List[Dict]:
    if user_id:
        return [a for a in AUDIT_LOG if a["user_id"] == user_id]
    return AUDIT_LOG
