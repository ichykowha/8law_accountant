# backend/encryption.py
"""
End-to-end encryption utilities for 8law (scaffold).
"""
from cryptography.fernet import Fernet

# Generate a key (store securely in production)
def generate_key():
    return Fernet.generate_key()

# Encrypt data
def encrypt_data(key, data: bytes) -> bytes:
    f = Fernet(key)
    return f.encrypt(data)

# Decrypt data
def decrypt_data(key, token: bytes) -> bytes:
    f = Fernet(key)
    return f.decrypt(token)
