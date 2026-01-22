# app/preflight.py
import os
import streamlit as st

REQUIRED_AT_BOOT = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
]

OPTIONAL_AT_BOOT = [
    "AUTH_REDIRECT_URL",
]

OPTIONAL_FEATURE_SECRETS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]


def _get_secret(key: str):
    return os.getenv(key) or st.secrets.get(key, None)


def _missing(keys):
    return [k for k in keys if not _get_secret(k)]


def run():
    missing_boot = _missing(REQUIRED_AT_BOOT)
    if missing_boot:
        st.error(
            "Missing required secrets: " + ", ".join(missing_boot) + "\n\n"
            "Add them in Streamlit Cloud → App Settings → Secrets.\n\n"
            "Until these are set, authentication and database access will not work."
        )
        st.stop()

    missing_optional_boot = _missing(OPTIONAL_AT_BOOT)
    if missing_optional_boot:
        st.info(
            "Optional secret not set: AUTH_REDIRECT_URL.\n\n"
            "Not required for basic email/password auth, but recommended for deployment clarity.\n"
            "Set it to your Streamlit app URL (see instructions below)."
        )

    missing_optional = _missing(OPTIONAL_FEATURE_SECRETS)
    if missing_optional:
        st.warning(
            "Optional features disabled until secrets are set: "
            + ", ".join(missing_optional)
            + "\n\nEmbeddings / Pinecone will not work until these are provided."
        )
