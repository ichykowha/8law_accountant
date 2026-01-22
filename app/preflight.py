from __future__ import annotations

import os
from typing import Optional, List

import streamlit as st

REQUIRED_AT_BOOT = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    # This must match your deployed Streamlit URL (or local dev URL when running locally).
    "AUTH_REDIRECT_URL",
]

# If Supabase Captcha protection is enabled, you should set this.
OPTIONAL_AT_BOOT = [
    "CLOUDFLARE_TURNSTILE_SITE_KEY",
]

OPTIONAL_FEATURE_SECRETS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]


def _get_secret(key: str) -> Optional[str]:
    v = os.getenv(key)
    if v:
        return v
    try:
        return st.secrets.get(key, None)
    except Exception:
        return None


def _missing(keys: List[str]) -> List[str]:
    return [k for k in keys if not _get_secret(k)]


def run() -> None:
    missing_boot = _missing(REQUIRED_AT_BOOT)
    if missing_boot:
        st.error(
            "Missing required secrets: " + ", ".join(missing_boot) + "\n\n"
            "Add them in Streamlit Cloud → App Settings → Secrets.\n\n"
            "Until these are set, authentication and database access will not work."
        )
        st.stop()

    auth_redirect = _get_secret("AUTH_REDIRECT_URL") or ""
    if not (auth_redirect.startswith("https://") or auth_redirect.startswith("http://localhost")):
        st.error(
            "AUTH_REDIRECT_URL must be a full URL, e.g.\n"
            "- https://<your-streamlit-app>.streamlit.app\n"
            "- http://localhost:8501\n\n"
            f"Current value: {auth_redirect!r}"
        )
        st.stop()

    # Non-blocking notices
    if _missing(OPTIONAL_AT_BOOT):
        st.info(
            "Turnstile is not configured in Streamlit secrets. If Supabase Captcha protection is enabled, "
            "set CLOUDFLARE_TURNSTILE_SITE_KEY to render the verification widget in the UI."
        )

    missing_optional = _missing(OPTIONAL_FEATURE_SECRETS)
    if missing_optional:
        st.warning(
            "Optional features disabled until secrets are set: "
            + ", ".join(missing_optional)
            + "\n\nEmbeddings / Pinecone will not work until these are provided."
        )
