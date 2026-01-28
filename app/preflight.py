# app/preflight.py
from __future__ import annotations

import os
from typing import Optional, Iterable, List

import streamlit as st

REQUIRED_AT_BOOT = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
]

# If you enabled Supabase Captcha protection with hCaptcha, you should set this in Streamlit secrets.
OPTIONAL_AT_BOOT = [
    "HCAPTCHA_SITE_KEY",
]

OPTIONAL_FEATURE_SECRETS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]


def _secrets_get(key: str) -> Optional[str]:
    """
    Streamlit-safe secret getter:
    - env first
    - then st.secrets if available
    - NEVER throws if secrets.toml is missing
    """
    v = os.getenv(key)
    if v:
        return v

    try:
        return st.secrets.get(key, None)  # type: ignore[attr-defined]
    except Exception:
        return None


def _missing(keys: Iterable[str]) -> List[str]:
    return [k for k in keys if not _secrets_get(k)]


def run() -> None:
    missing_boot = _missing(REQUIRED_AT_BOOT)
    if missing_boot:
        st.error(
            "Missing required secrets: "
            + ", ".join(missing_boot)
            + "\n\n"
            "Set them via one of the following:\n"
            "- Streamlit Cloud → App Settings → Secrets\n"
            "- Local dev: create .streamlit/secrets.toml in the repo root\n"
            "- Or set environment variables before launching Streamlit\n\n"
            "Until these are set, authentication and database access will not work."
        )
        st.stop()

    # Non-blocking notices
    missing_hcaptcha = _missing(OPTIONAL_AT_BOOT)
    if missing_hcaptcha:
        st.info(
            "hCaptcha is not configured. If Supabase CAPTCHA protection is enabled, "
            "set HCAPTCHA_SITE_KEY to render the verification widget in the UI."
        )

    missing_optional = _missing(OPTIONAL_FEATURE_SECRETS)
    if missing_optional:
        st.warning(
            "Optional features disabled until secrets are set: "
            + ", ".join(missing_optional)
            + "\n\nEmbeddings / Pinecone will not work until these are provided."
        )
