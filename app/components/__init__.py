# app/components/__init__.py
"""
Component package marker.

IMPORTANT:
Do NOT import Streamlit components here at import-time.
Streamlit Cloud imports modules during bootstrap; importing component modules here
can create circular imports and failures if assets are not yet resolved.
"""

__all__: list[str] = []
