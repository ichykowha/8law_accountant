# app/preflight.py
import os
import streamlit as st

REQUIRED_AT_BOOT = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
]

OPTIONAL_FEATURE_SECRETS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]

def _missing(keys):
    missing = []
    for k in keys:
        v = os.getenv(k) or st.secrets.get(k, None)
        if not v:
            missing.append(k)
    return missing

def run():
    missing_boot = _missing(REQUIRED_AT_BOOT)
    if missing_boot:
        st.error(
            "Missing required secrets: " + ", ".join(missing_boot) + "\n\n"
            "Add them in Streamlit Cloud → App Settings → Secrets.\n\n"
            "Until these are set, authentication and database access will not work."
        )
        st.stop()

    # Non-blocking notice for feature secrets
    missing_optional = _missing(OPTIONAL_FEATURE_SECRETS)
    if missing_optional:
        st.warning(
            "Optional features disabled until secrets are set: "
            + ", ".join(missing_optional)
            + "\n\nEmbeddings / Pinecone will not work until these are provided."
        )
