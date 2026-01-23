# app/components/turnstile_component/turnstile_component.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

# Expected layout:
# app/components/turnstile_component/
#   turnstile_component.py   <-- this file
#   frontend/
#     dist/
#       index.html
#       assets/...
_THIS_DIR = Path(__file__).resolve().parent
_FRONTEND_DIST = _THIS_DIR / "frontend" / "dist"

if not _FRONTEND_DIST.exists():
    # Fail loudly with deterministic diagnostics (this is what you need in Streamlit Cloud)
    raise RuntimeError(
        "Turnstile component frontend build output is missing.\n\n"
        f"Expected directory:\n  {_FRONTEND_DIST}\n\n"
        "Fix:\n"
        "  1) On your dev machine, run:\n"
        "       cd app/components/turnstile_component/frontend\n"
        "       npm install\n"
        "       npm run build\n"
        "  2) Commit and push the generated folder:\n"
        "       app/components/turnstile_component/frontend/dist\n"
        "  3) Ensure your .gitignore does NOT exclude dist/\n"
    )

_component = components.declare_component(
    "turnstile_component",
    path=str(_FRONTEND_DIST),
)

def turnstile(
    site_key: str,
    *,
    theme: str = "auto",
    size: str = "normal",
    key: str = "turnstile_component",
) -> Optional[str]:
    """
    Render Cloudflare Turnstile and return a token when solved, else None.
    """
    if not site_key:
        return None

    token = _component(
        siteKey=site_key,
        theme=theme,
        size=size,
        default="",
        key=key,
    )

    if isinstance(token, str) and token.strip():
        return token.strip()
    return None
