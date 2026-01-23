from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components


# -----------------------------------------------------------------------------
# Component declaration
# -----------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_FRONTEND_DIST = _THIS_DIR / "frontend" / "dist"

# For local frontend dev you can set:
#   TURNSTILE_COMPONENT_DEV_URL="http://localhost:5173"
_DEV_URL = os.getenv("TURNSTILE_COMPONENT_DEV_URL")

if _DEV_URL:
    _component = components.declare_component("turnstile_component", url=_DEV_URL)
else:
    _component = components.declare_component("turnstile_component", path=str(_FRONTEND_DIST))


def turnstile(
    site_key: str,
    *,
    key: str,
    theme: str = "auto",  # "auto" | "light" | "dark"
    size: str = "normal",  # "normal" | "compact"
) -> Optional[str]:
    """
    Render Cloudflare Turnstile and return a captcha token when solved.

    Returns:
      - token string when completed
      - None while unsolved
    """
    if not site_key:
        return None

    token = _component(
        siteKey=site_key,
        theme=theme,
        size=size,
        default=None,
        key=key,
    )

    if isinstance(token, str) and token.strip():
        return token.strip()

    return None
