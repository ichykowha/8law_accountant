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
# Priority A: Check for a local .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
    
DATABASE_URL = os.getenv("DATABASE_URL")

# Priority B: Check Streamlit Secrets (The "Case-Insensitive" Update)
if not DATABASE_URL and st is not None:
    try:
        # Check 1: Root Level (Uppercase AND Lowercase)
        if "DATABASE_URL" in st.secrets:
            DATABASE_URL = st.secrets["DATABASE_URL"]
        elif "database_url" in st.secrets:
            DATABASE_URL = st.secrets["database_url"]
        
        # Check 2: Inside [general] section
        elif "general" in st.secrets:
            if "DATABASE_URL" in st.secrets["general"]:
                DATABASE_URL = st.secrets["general"]["DATABASE_URL"]
            elif "database_url" in st.secrets["general"]:
                DATABASE_URL = st.secrets["general"]["database_url"]
            
        # Check 3: Inside [supabase] section
        elif "supabase" in st.secrets:
            if "DATABASE_URL" in st.secrets["supabase"]:
                DATABASE_URL = st.secrets["supabase"]["DATABASE_URL"]
            elif "database_url" in st.secrets["supabase"]:
                DATABASE_URL = st.secrets["supabase"]["database_url"]
            
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
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    print("DATABASE ENGINE CREATED SUCCESSFULLY")
except Exception as e:
    print("DATABASE ENGINE CREATION FAILED:", e)
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Helper function to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
