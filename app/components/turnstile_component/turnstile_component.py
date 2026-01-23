# app/components/turnstile_component/turnstile_component.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components


# -----------------------------------------------------------------------------
# Component declaration
# -----------------------------------------------------------------------------
# Production (Streamlit Cloud): serve built assets from frontend/dist (must be committed).
# Local dev (optional): set TURNSTILE_COMPONENT_DEV_URL=http://localhost:5173
# -----------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_FRONTEND_DIST = _HERE / "frontend" / "dist"

_DEV_URL = os.getenv("TURNSTILE_COMPONENT_DEV_URL", "").strip()
_IS_DEV = bool(_DEV_URL)

if _IS_DEV:
    _component = components.declare_component("turnstile_component", url=_DEV_URL)
else:
    if not _FRONTEND_DIST.exists():
        raise RuntimeError(
            f"Turnstile component frontend not built. Missing: {_FRONTEND_DIST}. "
            "Run `npm install` and `npm run build` in "
            "app/components/turnstile_component/frontend and commit frontend/dist."
        )
    _component = components.declare_component("turnstile_component", path=str(_FRONTEND_DIST))


def turnstile(
    site_key: str,
    *,
    theme: str = "auto",
    size: str = "normal",
    key: str = "turnstile",
) -> Optional[str]:
    """
    Render Cloudflare Turnstile and return the token when solved.

    Deterministic behavior:
      - returns None until a token is produced
      - returns token string once solved
      - returns None again if expired/error clears token

    Critical: 'key' must be stable across reruns to prevent iframe recreation / flashing.
    """
    site_key = (site_key or "").strip()
    if not site_key:
        return None

    value = _component(
        siteKey=site_key,  # matches TSX args.siteKey
        theme=theme,
        size=size,
        key=key,
        default="",
    )

    if not value:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
