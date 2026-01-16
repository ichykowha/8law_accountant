# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Database Connection
# File: backend/database/connection.py
# ------------------------------------------------------------------------------

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 1. Load Secrets (The .env file)
# This keeps your password safe. We never hardcode passwords in code.
load_dotenv()

# 2. Get the URL from the environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing! Check your .env file.")

# 3. Create the Engine
# This is the actual "Cable" connecting to Supabase.
engine = create_engine(DATABASE_URL)

# 4. Create the Session Factory
# This hands out temporary connections to users.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Dependency Injection
# This function is used by the API to get a connection for a single request,
# and then close it immediately after to prevent leaks.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
