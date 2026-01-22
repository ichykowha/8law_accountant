# app/preflight.py
import os
import streamlit as st


REQUIRED_SECRETS = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]


def run():
    missing = [k for k in REQUIRED_SECRETS if not os.getenv(k)]
    if missing:
        st.error(
            "Missing required secrets: " + ", ".join(missing)
            + "\n\nGo to Streamlit Cloud App Settings → Secrets and add them."
        )
        st.stop()
