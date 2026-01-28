from cryptography.fernet import Fernet
import base64
import hashlib

# User-provided password
password = "H311o$mum$897$"

# Derive a key from the password
key = hashlib.sha256(password.encode()).digest()
key_b64 = base64.urlsafe_b64encode(key)
fernet = Fernet(key_b64)

# Recovery codes to encrypt
codes = '''
07a5b-3e195
a049c-b5c3d
5892a-bd9ab
a6e5b-2b248
df594-0dec3
ebbcf-c7aad
cab16-94a2f
25104-0238e
7eabd-0d294
2a3c9-93230
5eac4-75f56
5d2f2-dee1d
baa54-21f3f
3d3bc-13665
dd4d8-9d935
42095-adb7b
'''.strip()

# Encrypt the codes
encrypted = fernet.encrypt(codes.encode())

# Save to file
with open("github_2fa_codes.encrypted", "wb") as f:
    f.write(encrypted)

print("Encrypted recovery codes saved to github_2fa_codes.encrypted.")
