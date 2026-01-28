# Example usage: create a user
from backend.database.connection import get_db
from backend.database.models import User, UserRole
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

def create_user(email: str, password: str, role: UserRole = UserRole.client):
    db: Session = next(get_db())
    hashed_pw = bcrypt.hash(password)
    user = User(email=email, hashed_password=hashed_pw, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"Created user: {user.email} ({user.role})")

# Example: create_user("admin@8law.com", "securepassword", UserRole.admin)
