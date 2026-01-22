# app/auth.py
"""
Deprecated auth shim.

Previous versions used a single shared password + hashlib for demo access.
8law now uses Supabase Auth (email/password + optional Turnstile), which is required
for Row Level Security (RLS) and safe multi-tenant operation.

If older code calls check_password(), we treat that as "require login".
"""

from typing import Optional, Dict
import streamlit as st

from app.auth_supabase import require_login


def check_password() -> bool:
    """
    Backwards-compatible name.
    Returns True when a Supabase user session exists.
    If not authenticated, renders the Supabase auth UI and returns False.
    """
    user = require_login()
    if user:
        # Store a familiar flag for any legacy code paths that read it
        st.session_state["password_correct"] = True
        return True

    st.session_state["password_correct"] = False
    return False


def current_user() -> Optional[Dict[str, str]]:
    """
    Convenience helper for callers that want user identity.
    """
    user = require_login()
    return user
