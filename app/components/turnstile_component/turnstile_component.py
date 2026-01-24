# app/components/turnstile_component/turnstile_component.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components


def _secrets_get(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safe secrets getter.

    Streamlit will raise StreamlitSecretNotFoundError if secrets.toml does not exist.
    We must not crash module import in local 'bare' python execution.
    """
    try:
        return st.secrets.get(name, default)  # type: ignore[attr-defined]
    except Exception:
        return default


_THIS_DIR = Path(__file__).resolve().parent
_FRONTEND_DIST = _THIS_DIR / "frontend" / "dist"

_DEV_URL = os.getenv("TURNSTILE_COMPONENT_DEV_URL") or _secrets_get("TURNSTILE_COMPONENT_DEV_URL", None)

if _DEV_URL:
    _component = components.declare_component("turnstile_component", url=_DEV_URL)
else:
    # In production (Streamlit Cloud), dist must exist in the repo at this exact path.
    _component = components.declare_component("turnstile_component", path=str(_FRONTEND_DIST))


def render_turnstile(
    site_key: str,
    *,
    key: str,
    theme: str = "auto",
    size: str = "normal",
    appearance: str = "always",
) -> str:
    """
    Render Cloudflare Turnstile via Streamlit custom component.

    Returns:
      token string if completed, else "".
    """
    if not site_key:
        return ""

    token = _component(
        siteKey=site_key,
        theme=theme,
        size=size,
        appearance=appearance,
        key=key,
        default="",
    )

    if token is None:
        return ""
    if isinstance(token, str):
        return token
    # Defensive: if component returns unexpected payload
    try:
        return str(token)
    except Exception:
        return ""
