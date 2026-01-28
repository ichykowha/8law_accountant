# backend/blockchain_hashing.py
import hashlib

def hash_document(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def hash_audit_batch(audit_entries: list) -> str:
    joined = ''.join(sorted(str(e) for e in audit_entries))
    return hashlib.sha256(joined.encode()).hexdigest()
