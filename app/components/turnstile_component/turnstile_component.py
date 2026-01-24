# app/components/turnstile_component/turnstile_component.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

# Component build output must exist at:
# app/components/turnstile_component/frontend/dist
_COMPONENT_DIR = Path(__file__).resolve().parent
_FRONTEND_DIST = _COMPONENT_DIR / "frontend" / "dist"

# Optional dev mode:
# set TURNSTILE_COMPONENT_DEV_URL=http://localhost:5173
_DEV_URL = st.secrets.get("TURNSTILE_COMPONENT_DEV_URL", None) if hasattr(st, "secrets") else None

if not _DEV_URL:
    import os
    _DEV_URL = os.getenv("TURNSTILE_COMPONENT_DEV_URL")

if _DEV_URL:
    _component = components.declare_component("turnstile_component", url=_DEV_URL)
else:
    if not _FRONTEND_DIST.exists():
        # Fail fast with a clear message rather than Streamlit's generic redaction.
        raise RuntimeError(
            f"Turnstile component frontend build not found at: {_FRONTEND_DIST}\n\n"
            "Fix:\n"
            "  1) Build the frontend: cd app/components/turnstile_component/frontend && npm install && npm run build\n"
            "  2) Ensure the dist/ directory is committed to git and deployed.\n"
        )
    _component = components.declare_component("turnstile_component", path=str(_FRONTEND_DIST))


def render_turnstile(
    site_key: str,
    *,
    key: str,
    theme: str = "auto",
    size: str = "normal",
    appearance: str = "always",
) -> Optional[str]:
    """
    Render Cloudflare Turnstile and return the token when completed.

    Returns:
      - token string when verified
      - None (or empty) when not yet verified

    Notes:
      - `appearance` is included for future-proofing (Turnstile supports it in some modes),
        but the frontend currently focuses on stable rendering + token callbacks.
    """
    if not site_key:
        return None

    token = _component(
        siteKey=site_key,
        theme=theme,
        size=size,
        appearance=appearance,
        key=key,
        default="",
    )

    if not token:
        return None

    if isinstance(token, str):
        token = token.strip()
        return token or None

    # Defensive: if Streamlit returns something unexpected
    return None
