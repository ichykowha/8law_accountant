# backend/admin.py
from typing import List, Dict
from datetime import datetime, timezone

# Placeholder user store
USERS = [
    {"id": "1", "email": "admin@8law.com", "role": "admin"},
    {"id": "2", "email": "user@8law.com", "role": "client"}
]

# Placeholder log store
LOGS = [
    {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "System started."}
]

# Placeholder health check
def get_system_health() -> Dict:
        return {"status": "OK", "uptime": "99.99%", "last_check": datetime.now(timezone.utc).isoformat()}

def list_users() -> List[Dict]:
    return USERS

def get_logs() -> List[Dict]:
    return LOGS
