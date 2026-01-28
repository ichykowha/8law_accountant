# backend/audit_logger.py
from backend.database.connection import get_db
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from backend.blockchain_hashing import hash_audit_batch
from backend.ethereum_integration import anchor_hash_to_ethereum

# Simple audit log table (for demo, could be a real model)
AUDIT_LOG = []

def log_action(user_id, action, details: Optional[dict] = None):
    entry = {
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    AUDIT_LOG.append(entry)
    # Anchor every 10 entries (demo, adjust as needed)
    if len(AUDIT_LOG) % 10 == 0:
        batch_hash = hash_audit_batch(AUDIT_LOG[-10:])
        anchor_hash_to_ethereum(batch_hash)

# Example: log_action(1, "classify", {"txn_id": 123, "category": "Groceries"})

def get_audit_log(user_id=None):
    if user_id:
        return [a for a in AUDIT_LOG if a["user_id"] == user_id]
    return AUDIT_LOG
