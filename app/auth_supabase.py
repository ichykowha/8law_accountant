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

    # Read from a hidden text area via Streamlit state proxy:
    # We cannot directly read DOM state; instead we ask user to click "I am human"
    # and then re-run will allow the widget to populate the textarea.
    # We provide a manual input fallback (still frictionless).
    token = st.session_state.get(f"{key}_token")
    # Offer a tiny text_input that can capture pasted tokens (fallback), but hidden-ish.
    token_ui = st.text_input("Turnstile token (auto-filled)", key=f"{key}_token", label_visibility="collapsed")
    return token_ui or token


# =============================================================================
# Password policy UX helpers (client-side)
# =============================================================================

@dataclass
class PasswordPolicy:
    min_len: int = MIN_PASSWORD_LEN_DEFAULT
    require_upper: bool = False
    require_lower: bool = False
    require_digit: bool = False
    require_symbol: bool = False


def _estimate_strength(pw: str, policy: PasswordPolicy) -> tuple[int, list[str]]:
    """
    Returns (score 0-100, unmet_rules list).
    This is UX-only; Supabase server-side rules still apply.
    """
    unmet = []

    if len(pw) < policy.min_len:
        unmet.append(f"At least {policy.min_len} characters")

    has_lower = bool(re.search(r"[a-z]", pw))
    has_upper = bool(re.search(r"[A-Z]", pw))
    has_digit = bool(re.search(r"\d", pw))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", pw))

    if policy.require_lower and not has_lower:
        unmet.append("At least one lowercase letter")
    if policy.require_upper and not has_upper:
        unmet.append("At least one uppercase letter")
    if policy.require_digit and not has_digit:
        unmet.append("At least one number")
    if policy.require_symbol and not has_symbol:
        unmet.append("At least one symbol")

    # Heuristic strength score
    score = 0
    score += min(len(pw) * 5, 40)  # length contributes up to 40
    score += 15 if has_lower else 0
    score += 15 if has_upper else 0
    score += 15 if has_digit else 0
    score += 15 if has_symbol else 0

    # penalize very short
    if len(pw) < 8:
        score = min(score, 45)
    if len(pw) < policy.min_len:
        score = min(score, 35)

    score = max(0, min(score, 100))
    return score, unmet


def _strength_label(score: int) -> str:
    if score < 35:
        return "Weak"
    if score < 60:
        return "Fair"
    if score < 80:
        return "Good"
    return "Strong"


# =============================================================================
# Session management
# =============================================================================

def _set_user_session(user: dict, access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> None:
    st.session_state["auth_user"] = user
    if access_token:
        st.session_state["auth_access_token"] = access_token
    if refresh_token:
        st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_last_set_ts"] = time.time()


def current_user() -> Optional[dict]:
    return st.session_state.get("auth_user")


def supabase_logout() -> None:
    """
    Safe logout: clears local session. Attempts Supabase signout if possible.
    """
    try:
        sb = _supabase()
        # If we have a token, set it and sign out.
        access = st.session_state.get("auth_access_token")
        if access:
            sb.auth.set_session(access, st.session_state.get("auth_refresh_token") or "")
        sb.auth.sign_out()
    except Exception:
        pass

    for k in [
        "auth_user",
        "auth_access_token",
        "auth_refresh_token",
        "auth_last_set_ts",
    ]:
        if k in st.session_state:
            del st.session_state[k]


# =============================================================================
# Auth UI / Flows
# =============================================================================

def require_login() -> Optional[dict]:
    """
    Blocks app until user is authenticated.
    Returns user dict on success.
    """
    # Already authenticated in session
    u = current_user()
    if u:
        return u

    st.title("8law Secure Access")

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    # Optional Turnstile
    site_key = _get_secret(TURNSTILE_SITE_KEY_KEY)

    with tab_login:
        st.subheader("Sign In")
        email = st.text_input("Email", key="auth_login_email")
        password = st.text_input("Password", type="password", key="auth_login_password")

        token = None
        if site_key:
            st.caption("Human verification:")
            token = turnstile_token(site_key, key="turnstile_login")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                if not email or not password:
                    st.error("Email and password are required.")
                else:
                    try:
                        sb = _supabase()
                        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
                        # supabase-py returns an object with .user and .session
                        user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                        session = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                        if not user:
                            st.error("Sign-in failed. Check credentials and email confirmation status.")
                        else:
                            access_token = getattr(session, "access_token", None) if session else None
                            refresh_token = getattr(session, "refresh_token", None) if session else None
                            _set_user_session(user if isinstance(user, dict) else user.__dict__, access_token, refresh_token)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Sign-in error: {type(e).__name__}: {e}")

        with col_b:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                if not email:
                    st.error("Enter your email above first.")
                else:
                    try:
                        sb = _supabase()
                        # Newer supabase clients: resend() exists; if not, fall back message
                        try:
                            sb.auth.resend({"type": "signup", "email": email})
                            st.success("Confirmation email resent. Check your inbox and spam folder.")
                        except Exception:
                            st.warning(
                                "Resend API not available in this client version. "
                                "In Supabase Dashboard, you can also invite/re-send from Auth → Users."
                            )
                    except Exception as e:
                        st.error(f"Resend failed: {type(e).__name__}: {e}")

        st.markdown("---")
        st.caption(
            "If you get OTP expired errors, increase Email OTP Expiration in Supabase Auth settings, "
            "and ensure your Streamlit domain is in Supabase Redirect URLs."
        )

    with tab_signup:
        st.subheader("Create Account")
        email2 = st.text_input("Email", key="auth_signup_email")
        pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
        pw2 = st.text_input("Confirm password", type="password", key="auth_signup_pw2")

        # Password UX policy (client-side messaging only)
        policy = PasswordPolicy(min_len=MIN_PASSWORD_LEN_DEFAULT)
        score, unmet = _estimate_strength(pw1 or "", policy)

        st.caption("Password requirements:")
        st.write(f"- Minimum length: {policy.min_len} characters")
        if unmet:
            st.warning("Missing: " + ", ".join(unmet))
        st.progress(score / 100.0, text=f"Strength: {_strength_label(score)} ({score}/100)")

        token2 = None
        if site_key:
            st.caption("Human verification:")
            token2 = turnstile_token(site_key, key="turnstile_signup")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            if not email2 or not pw1 or not pw2:
                st.error("Email, password, and confirmation are required.")
            elif pw1 != pw2:
                st.error("Passwords do not match.")
            elif len(pw1) < policy.min_len:
                st.error(f"Password must be at least {policy.min_len} characters.")
            else:
                try:
                    sb = _supabase()

                    # NOTE: Supabase will enforce its own policies (leaked password checks, min length, etc.)
                    resp = sb.auth.sign_up({"email": email2, "password": pw1})

                    user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                    if user:
                        st.success(
                            "Account created. Check your email for a confirmation link before signing in."
                        )
                    else:
                        st.warning(
                            "Signup submitted. If you do not receive an email, verify email provider settings "
                            "in Supabase Auth → Email."
                        )
                except Exception as e:
                    st.error(f"Signup error: {type(e).__name__}: {e}")

    st.stop()
    return None
