# app/components/turnstile_component/turnstile_component.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

_turnstile = components.declare_component(
    "turnstile_component",
    path=str(_FRONTEND_DIR),
)

def render_turnstile(
    site_key: str,
    *,
    key: str,
    theme: str = "auto",
    size: str = "normal",
    appearance: str = "always",
) -> Optional[str]:
    """
    Render Cloudflare Turnstile and return the token string (or None).
    - theme: auto | light | dark
    - size: normal | compact
    - appearance: always | interaction-only
    """
    token = _turnstile(
        site_key=site_key,
        theme=theme,
        size=size,
        appearance=appearance,
        key=key,
        default="",
    )
    token = (token or "").strip()
    return token or None
