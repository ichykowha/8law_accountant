from passlib.context import CryptContext

# Central password hashing/verification context.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Converts a plaintext password into a secure bcrypt hash."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Returns True if the stored hash should be upgraded (e.g., cost factor changed,
    algorithm settings updated). Useful for transparent re-hashing on successful login.
    """
    return pwd_context.needs_update(hashed_password)
