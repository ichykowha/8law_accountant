from __future__ import annotations

import os
from typing import Optional

import streamlit.components.v1 as components

# Local component path (ships with repo; works on Streamlit Cloud)
_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))

_turnstile = components.declare_component(
    "turnstile_component",
    path=_COMPONENT_DIR,
)

def render(site_key: str, *, key: str = "turnstile") -> Optional[str]:
    """
    Render Cloudflare Turnstile and return a token string when solved.
    Returns None until solved.

    Deterministic: no network fetches for component assets; ships with repo.
    """
    if not site_key:
        return None
    result = _turnstile(site_key=site_key, key=key, default=None)
    if isinstance(result, str) and result.strip():
        return result.strip()
    return None
