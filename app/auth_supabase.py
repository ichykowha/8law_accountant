# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client


# =============================================================================
# Configuration / Secrets
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

# Optional Turnstile (Cloudflare)
TURNSTILE_SITE_KEY_KEY = "CLOUDFLARE_TURNSTILE_SITE_KEY"
TURNSTILE_SECRET_KEY_KEY = "CLOUDFLARE_TURNSTILE_SECRET_KEY"

# Optional: if set, we can enforce stronger client-side policy messaging
MIN_PASSWORD_LEN_DEFAULT = 8


def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v:
        return v
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _supabase() -> Client:
    url = _get_secret(SUPABASE_URL_KEY)
    anon = _get_secret(SUPABASE_ANON_KEY_KEY)
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY")
    return create_client(url, anon)


# =============================================================================
# Turnstile (Optional)
# =============================================================================

def _turnstile_html(site_key: str, widget_id: str) -> str:
    # Streamlit-safe HTML widget that posts token back through a hidden input.
    # We also expose token via a <textarea> because Streamlit can read it.
    # Note: This is client-side only; if you want full security, verify token on server.
    return f"""
    <div>
      <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>

      <div id="{widget_id}"></div>

      <textarea id="{widget_id}_token" style="display:none;"></textarea>

      <script>
        const renderWidget = () => {{
          if (!window.turnstile) {{
            setTimeout(renderWidget, 200);
            return;
          }}

          // avoid double-render
          const container = document.getElementById("{widget_id}");
          if (!container || container.dataset.rendered === "1") return;
          container.dataset.rendered = "1";

          window.turnstile.render("#{widget_id}", {{
            sitekey: "{site_key}",
            callback: function(token) {{
              const t = document.getElementById("{widget_id}_token");
              if (t) {{
                t.value = token;
                // Trigger an input event so Streamlit notices changes
                t.dispatchEvent(new Event('input', {{ bubbles: true }}));
              }}
            }},
            'expired-callback': function() {{
              const t = document.getElementById("{widget_id}_token");
              if (t) {{
                t.value = "";
                t.dispatchEvent(new Event('input', {{ bubbles: true }}));
              }}
            }}
          }});
        }};

        renderWidget();
      </script>
    </div>
    """


def turnstile_token(site_key: str, key: str = "turnstile") -> Optional[str]:
    """
    Renders Turnstile and returns token from browser.
    Optional: If no token returned yet, returns None.
    """
    widget_id = f"{key}_widget"
    html = _turnstile_html(site_key, widget_id=widget_id)

    # Height: enough for checkbox. Increase if you use non-interactive/invisible.
    components.html(html, height=120)

    # Read
