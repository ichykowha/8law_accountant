import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 1. Try to Import Streamlit (to access Cloud Secrets)
try:
    import streamlit as st
except ImportError:
    st = None

# 2. Find the Connection String 🕵️‍♂️
# Priority A: Check for a local .env file (good for local computers)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
    
DATABASE_URL = os.getenv("DATABASE_URL")

# Priority B: Check Streamlit Secrets (The Hunter-Seeker Logic)
if not DATABASE_URL and st is not None:
    try:
        # Check 1: Is it at the very top?
        if "DATABASE_URL" in st.secrets:
            DATABASE_URL = st.secrets["DATABASE_URL"]
        
        # Check 2: Is it inside [general]?
        elif "general" in st.secrets and "DATABASE_URL" in st.secrets["general"]:
            DATABASE_URL = st.secrets["general"]["DATABASE_URL"]
            
        # Check 3: Is it inside [supabase]? (This is where you put it!)
        elif "supabase" in st.secrets and "DATABASE_URL" in st.secrets["supabase"]:
            DATABASE_URL = st.secrets["supabase"]["DATABASE_URL"]
            
    except Exception:
        pass # Secrets not available

# 3. Validate
if not DATABASE_URL:
    # DEBUG: Print what keys we actually found to help troubleshooting
    if st is not None:
        print(f"DEBUG: Available Secret Sections: {list(st.secrets.keys())}")
    
    raise ValueError("DATABASE_URL is missing! Please check Streamlit Secrets.")

# 4. Fix Format for SQLAlchemy
# SQLAlchemy needs 'postgresql://', but Supabase often gives 'postgres://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 5. Connect to the Database 🔌
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Helper function to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()