# app/auth_supabase.py
import os
import re
import time
from typing import Optional, Dict, Any

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client


# -----------------------------
# Config / Secrets
# -----------------------------

def _secret(key: str, default=None):
    return os.getenv(key) or st.secrets.get(key, default)

SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_ANON_KEY = _secret("SUPABASE_ANON_KEY")

# Optional: show Turnstile widget in UI if provided
TURNSTILE_SITE_KEY = _secret("CLOUDFLARE_TURNSTILE_SITE_KEY", None)

# If you want to hard-disable captcha UI (even if site key exists), set to "0"
TURNSTILE_UI_ENABLED = str(_secret("TURNSTILE_UI_ENABLED", "1")).strip() != "0"


# -----------------------------
# Supabase client
# -----------------------------

@st.cache_resource(show_spinner=False)
def _sb():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# -----------------------------
# Password policy helpers
# -----------------------------

def password_requirements_text(min_len: int = 8) -> str:
    return (
        f"Password requirements:\n"
        f"- At least {min_len} characters\n"
        f"- At least 1 uppercase letter\n"
        f"- At least 1 lowercase letter\n"
        f"- At least 1 number\n"
        f"- At least 1 symbol (!@#$%^&* etc.)"
    )

def password_strength(password: str) -> int:
    """Returns 0..100 strength score (simple heuristic)."""
    if not password:
        return 0

    score = 0
    length = len(password)

    # Length
    if length >= 8:
        score += 20
    if length >= 12:
        score += 15
    if length >= 16:
        score += 10

    # Variety
    if re.search(r"[A-Z]", password):
        score += 15
    if re.search(r"[a-z]", password):
        score += 15
    if re.search(r"\d", password):
        score += 15
    if re.search(r"[^\w\s]", password):
        score += 15

    # Penalize very common patterns
    if re.search(r"(password|1234|qwer|admin|letmein)", password.lower()):
        score -= 25

    return max(0, min(100, score))

def is_password_strong(password: str, min_len: int = 8) -> bool:
    if len(password) < min_len:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^\w\s]", password):
        return False
    return True


# -----------------------------
# Turnstile rendering (no custom component build)
# -----------------------------

def turnstile_widget(site_key: str, widget_id: str) -> None_
