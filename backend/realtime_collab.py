# backend/realtime_collab.py
"""
Real-time collaboration utilities for 8law (scaffold).
"""
import threading
import time

COLLAB_STATE = {}

# Simulate a shared state update (in production, use Redis, WebSocket, or similar)
def update_state(doc_id, user_id, data):
    COLLAB_STATE.setdefault(doc_id, {})[user_id] = {"data": data, "timestamp": time.time()}

def get_state(doc_id):
    return COLLAB_STATE.get(doc_id, {})

# In production, replace with a real pub/sub or WebSocket backend
