# app/components/turnstile_component.py
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

try:
    # Streamlit Components v2 (no separate frontend build required)
    from streamlit.components.v2 import component as v2_component
except Exception as e:  # pragma: no cover
    v2_component = None
    _V2_IMPORT_ERROR = e
else:
    _V2_IMPORT_ERROR = None


_HTML = """
<div style="min-height: 70px;">
  <div id="cf_turnstile_root"></div>
  <div id="cf_turnstile_status" style="font-size: 12px; opacity: 0.75; margin-top: 6px;"></div>
</div>
"""

# Streamlit v2 component JS contract:
# - export default function(component) { ... }
# - component.setStateValue("token", token) persists token in component state
# - component.data carries Python->frontend payload
# Docs show setStateValue usage and the v2 component mounting model. :contentReference[oaicite:1]{index=1}
_JS = r"""
export default function(component) {
  const { parentElement, setStateValue, data } = component;

  const siteKey = (data && data.site_key) ? data.site_key : null;
  const resetNonce = (data && (data.reset_nonce !== undefined)) ? data.reset_nonce : 0;
  const haveToken = (data && data.token) ? true : false;

  const root = parentElement.querySelector("#cf_turnstile_root");
  const status = parentElement.querySelector("#cf_turnstile_status");

  const setStatus = (msg) => {
    if (status) status.textContent = msg || "";
  };

  if (!siteKey) {
    setStatus("Turnstile site key missing.");
    return;
  }

  // Keep a stable widget mountpoint ID inside this component instance.
  const widgetDivId = "cf_turnstile_widget";
  if (root && !root.querySelector(`#${widgetDivId}`)) {
    root.innerHTML = `<div id="${widgetDivId}"></div>`;
  }

  // Track render state on the parent element to avoid double renders across reruns.
  const stateKey = "__cf_turnstile_state__";
  if (!parentElement[stateKey]) parentElement[stateKey] = {};
  const local = parentElement[stateKey];

  const ensureScript = () => {
    return new Promise((resolve, reject) => {
      if (window.turnstile) return resolve(true);

      // If script tag already exists, wait.
      const existing = document.querySelector('script[data-cf-turnstile="1"]');
      if (existing) {
        const wait = () => window.turnstile ? resolve(true) : setTimeout(wait, 150);
        return wait();
      }

      const s = document.createElement("script");
      s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      s.async = true;
      s.defer = true;
      s.dataset.cfTurnstile = "1";
      s.onload = () => resolve(true);
      s.onerror = () => reject(new Error("Failed to load Turnstile API script."));
      document.head.appendChild(s);
    });
  };

  const doRender = async () => {
    try {
      await ensureScript();

      // If we already have a token in Python state, we still render the widget so the UI is consistent.
      // But we do not spam resets unless user requests.
      setStatus(haveToken ? "Verified." : "Complete the verification to proceed.");

      // Re-render protection: if already rendered AND resetNonce unchanged, do nothing.
      if (local.rendered && local.lastResetNonce === resetNonce) {
        return;
      }

      // If we rendered before and resetNonce changed, reset existing widget.
      if (local.rendered && local.widgetId !== undefined && local.lastResetNonce !== resetNonce) {
        try {
          window.turnstile.reset(local.widgetId);
        } catch (e) {
          // If reset fails, we will fall back to a fresh render.
          local.rendered = false;
        }
      }

      if (!local.rendered) {
        const widgetEl = parentElement.querySelector(`#${widgetDivId}`);
        if (!widgetEl) {
          setStatus("Turnstile mount element missing.");
          return;
        }

        const wid = window.turnstile.render(widgetEl, {
          sitekey: siteKey,
          callback: function(token) {
            setStateValue("token", token);
            setStatus("Verified.");
          },
          "expired-callback": function() {
            setStateValue("token", null);
            setStatus("Verification expired. Please verify again.");
          },
          "error-callback": function() {
            setStateValue("token", null);
            setStatus("Verification error. Please retry.");
          }
        });

        local.widgetId = wid;
        local.rendered = true;
      }

      local.lastResetNonce = resetNonce;
    } catch (err) {
      setStateValue("token", null);
      setStatus("Unable to load verification widget (network/script blocked).");
    }
  };

  doRender();
}
"""

# Mount command (v2 bidirectional component)
_turnstile = None
if v2_component is not None:
    _turnstile = v2_component(
        "turnstile_component",
        html=_HTML,
        js=_JS,
    )


def reset_turnstile(component_key: str) -> None:
    """
    Forces a Turnstile reset on next rerun for the given component key.
    Deterministic: increments a nonce that frontend watches.
    """
    st.session_state.setdefault(f"{component_key}__reset_nonce", 0)
    st.session_state[f"{component_key}__reset_nonce"] += 1

    # Clear persisted token state (component state is stored under the component key)
    if component_key in st.session_state and isinstance(st.session_state[component_key], dict):
        st.session_state[component_key]["token"] = None


def turnstile_token(*, site_key: str, component_key: str, height: int = 90) -> Optional[str]:
    """
    Renders Turnstile and returns the token (or None if not completed yet).

    Uses Components v2 state passing (setStateValue) so it works on Streamlit Cloud
    without bundling frontend assets. :contentReference[oaicite:2]{index=2}
    """
    if _turnstile is None:
        raise RuntimeError(
            "Streamlit Components v2 is not available in this environment. "
            f"Import error: {_V2_IMPORT_ERROR!r}"
        )

    # Read current persisted token (component state is stored under component_key)
    component_state: Dict[str, Any] = st.session_state.get(component_key, {}) or {}
    token = component_state.get("token")

    reset_nonce = st.session_state.get(f"{component_key}__reset_nonce", 0)

    data = {
        "site_key": site_key,
        "token": token,
        "reset_nonce": reset_nonce,
    }

    result = _turnstile(
        data=data,
        default={"token": token},
        key=component_key,
        on_token_change=lambda: None,  # required when using default state
        height=height,
    )

    # result is dictionary-like; token is in state key "token"
    if result is None:
        return None
    return result.get("token")
