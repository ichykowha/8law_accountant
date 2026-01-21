import os
import streamlit as st

REQUIRED = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]

OPTIONAL = [
    "OPENAI_EMBED_MODEL",
]

def _get(name: str):
    # Prefer Streamlit secrets, fall back to env
    try:
        v = st.secrets.get(name, None)
    except Exception:
        v = None
    return v or os.getenv(name)

def run():
    missing = []
    for k in REQUIRED:
        v = _get(k)
        if not v or "YOUR_KEY_HERE" in str(v):
            missing.append(k)

    if missing:
        st.error(
            "Missing required secrets: " + ", ".join(missing) + "\n\n"
            "Go to Streamlit Cloud  App  Settings  Secrets and add them.\n"
            "Until these are set, embeddings / Pinecone will not work."
        )
        # IMPORTANT: stop before any embedding/upsert logic runs
        st.stop()

    # Optional: show model choice if present
    emb = _get("OPENAI_EMBED_MODEL")
    if emb:
        st.caption(f"Embedding model: {emb}")
