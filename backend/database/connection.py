import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Optional: only present in Streamlit deployments
try:
    import streamlit as st
except Exception:
    st = None

# Optional: local development convenience
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_database_url() -> str:
    # 1) Environment variable (best for FastAPI/Uvicorn and most hosts)
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.strip():
        return db_url.strip()

    # 2) Streamlit secrets (best for Streamlit Cloud)
    if st is not None:
        try:
            secrets = st.secrets

            # Top-level common keys
            for k in ("DATABASE_URL", "database_url"):
                v = secrets.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

            # Nested common sections
            for section in ("general", "supabase"):
                sec = secrets.get(section)
                if isinstance(sec, dict):
                    for k in ("DATABASE_URL", "database_url"):
                        v = sec.get(k)
                        if isinstance(v, str) and v.strip():
                            return v.strip()
        except Exception:
            pass

    raise ValueError(
        "DATABASE_URL is missing. Set it as an environment variable, or define it in Streamlit secrets."
    )


DATABASE_URL = _get_database_url()

# Normalize for SQLAlchemy (Supabase sometimes provides postgres://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
from sqlalchemy import text

with engine.connect() as conn:
    row = conn.execute(text("select current_database(), current_user")).first()
    print("DB CONNECTED TO:", row)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
