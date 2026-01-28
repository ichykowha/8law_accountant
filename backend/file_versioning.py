# backend/file_versioning.py
from typing import List, Dict
from datetime import datetime, timezone

# In-memory file version store (replace with DB in production)
FILE_VERSIONS: List[Dict] = []

def add_file_version(user_id: str, file_name: str, file_hash: str):
    FILE_VERSIONS.append({
        "user_id": user_id,
        "file_name": file_name,
        "file_hash": file_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": get_next_version(file_name)
    })

def get_file_versions(file_name: str) -> List[Dict]:
    return [v for v in FILE_VERSIONS if v["file_name"] == file_name]

def get_next_version(file_name: str) -> int:
    versions = [v for v in FILE_VERSIONS if v["file_name"] == file_name]
    return len(versions) + 1
