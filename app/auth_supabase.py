# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import streamlit as st
from supabase import Client, create_client

from app.components.turnstile_component import render_turnstile

__all__ = [
    "require_login",
    "supabase_logout",
    "current_user",
    "supabase_for_user",
]

# =============================================================================
# Configuration / Secrets
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

# Turnstile (client-side site key)
TURNSTILE_SITE_KEY_KEY = "CLOUDFLARE_TURNSTILE_SITE_KEY"

MIN_PASSWORD_LEN_DEFAULT = 8


def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safe secret fetch:
    - env var wins
    - then st.secrets if present
    - never throws if secrets.toml is missing locally
    """
    v = os.getenv(name)
    if v:
        return v
    try:
        # st.secrets.get triggers parsing; wrap to avoid StreamlitSecretNotFoundError locally
        return st.secrets.get(name, default)  # type: ignore[attr-defined]
    except Exception:
        return default


def _supabase() -> Client:
    url = _get_secret(SUPABASE_URL_KEY)
    anon = _get_secret(SUPABASE_ANON_KEY_KEY)
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY")
    return create_client(url, anon)


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


def _estimate_strength(pw: str, policy: PasswordPolicy) -> Tuple[int, list[str]]:
    unmet: list[str] = []

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

    score = 0
    score += min(len(pw) * 5, 40)
    score += 15 if has_lower else 0
    score += 15 if has_upper else 0
    score += 15 if has_digit else 0
    score += 15 if has_symbol else 0

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


def supabase_for_user() -> Client:
    """
    Return a Supabase client authenticated as the currently logged-in user (if tokens exist).
    This is used by DB-scoped modules so PostgREST calls respect RLS with the user's JWT.
    """
    sb = _supabase()

    access = st.session_state.get("auth_access_token")
    refresh = st.session_state.get("auth_refresh_token")
    if access and refresh:
        try:
            sb.auth.set_session(access, refresh)
        except Exception:
            # If tokens are invalid/expired, caller will hit auth failures via RLS.
            pass

    return sb


def supabase_logout() -> None:
    try:
        sb = _supabase()
        access = st.session_state.get("auth_access_token")
        refresh = st.session_state.get("auth_refresh_token")
        if access and refresh:
            try:
                sb.auth.set_session(access, refresh)
            except Exception:
                pass
        try:
            sb.auth.sign_out()
        except Exception:
            pass
    except Exception:
        pass

    for k in ["auth_user", "auth_access_token", "auth_refresh_token", "auth_last_set_ts"]:
        st.session_state.pop(k, None)


# =============================================================================
# Turnstile helpers
# =============================================================================

def _turnstile_nonce(name: str) -> int:
    key = f"turnstile_nonce__{name}"
    if key not in st.session_state:
        st.session_state[key] = 0
    return int(st.session_state[key])


def _bump_turnstile_nonce(name: str) -> None:
    key = f"turnstile_nonce__{name}"
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1


def _turnstile_component_key(name: str) -> str:
    # rotating key forces a fresh iframe + fresh token on the next render
    return f"turnstile__{name}__{_turnstile_nonce(name)}"


def _render_captcha(site_key: str, *, name: str) -> Optional[str]:
    """
    Render Turnstile and return token (or None).
    Using a rotating component key ensures we never reuse a token across submits.
    """
    component_key = _turnstile_component_key(name)
    token = render_turnstile(
        site_key,
        key=component_key,
        theme="auto",
        size="normal",
        appearance="always",  # keep 'always' while debugging; you can change to 'interaction-only' later
    )
    return token


def _attach_captcha(payload: Dict[str, Any], captcha_token: Optional[str]) -> Dict[str, Any]:
    """
    Supabase Auth (GoTrue) validates CAPTCHA from request body fields.
    Different clients map this differently, so we include all supported encodings:

    - top-level captcha_token
    - gotrue_meta_security: { captcha_token: ... }
    - options: { captchaToken: ... }

    This makes the request robust across auth client versions.
    """
    if not captcha_token:
        return payload

    payload = dict(payload)
    payload["captcha_token"] = captcha_token
    payload["gotrue_meta_security"] = {"captcha_token": captcha_token}

    opts = payload.get("options") or {}
    if isinstance(opts, dict):
        opts = dict(opts)
        opts["captchaToken"] = captcha_token
        payload["options"] = opts

    return payload


def _captcha_error_hint(e: Exception) -> Optional[str]:
    msg = str(e).lower()
    if "captcha" not in msg:
        return None
    return (
        "CAPTCHA verification failed. This usually means:\n"
        "1) Supabase Dashboard has the WRONG Turnstile *Secret Key* configured (site key != secret key), or\n"
        "2) The token is being reused/expired, or\n"
        "3) Hostname mismatch between Turnstile widget config and where the app is running.\n"
        "\n"
        "Confirm in Supabase:\n"
        "- Settings → Authentication → Bot & Abuse Protection\n"
        "- Provider = Turnstile\n"
        "- Secret Key = Turnstile *Secret Key* (NOT the Site Key)\n"
        "\n"
        "Confirm in Streamlit secrets/env:\n"
        "- CLOUDFLARE_TURNSTILE_SITE_KEY = Turnstile Site Key\n"
    )


# =============================================================================
# Auth UI / Flows
# =============================================================================

def require_login() -> Optional[dict]:
    """
    Blocks app until user is authenticated.
    Returns user dict on success.
    """
    u = current_user()
    if u:
        return u

    st.title("8law Secure Access")

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    site_key = _get_secret(TURNSTILE_SITE_KEY_KEY)

    with tab_login:
        st.subheader("Sign In")
        email = st.text_input("Email", key="auth_login_email")
        password = st.text_input("Password", type="password", key="auth_login_password")

        captcha_token = None
        if site_key:
            st.caption("Human verification:")
            captcha_token = _render_captcha(site_key, name="login")
        else:
            st.info("Turnstile site key not configured. If Supabase CAPTCHA protection is enabled, login will fail.")

        col_a, col_b = st.columns([1, 1])

        with col_a:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                # Always force a fresh token for next attempt (success or failure)
                _bump_turnstile_nonce("login")

                if not email or not password:
                    st.error("Email and password are required.")
                    st.stop()
                if site_key and not captcha_token:
                    st.error("Please complete the human verification.")
                    st.stop()

                try:
                    sb = _supabase()
                    payload = _attach_captcha({"email": email, "password": password}, captcha_token)
                    resp = sb.auth.sign_in_with_password(payload)

                    user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                    session = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                    if not user:
                        st.error("Sign-in failed. Check credentials and email confirmation status.")
                        st.stop()

                    access_token = getattr(session, "access_token", None) if session else None
                    refresh_token = getattr(session, "refresh_token", None) if session else None
                    _set_user_session(user if isinstance(user, dict) else user.__dict__, access_token, refresh_token)

                    st.rerun()

                except Exception as e:
                    hint = _captcha_error_hint(e)
                    if hint:
                        st.error(hint)
                    st.error(f"Sign-in error: {type(e).__name__}: {e}")
                    st.stop()

        with col_b:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                _bump_turnstile_nonce("login")

                if not email:
                    st.error("Enter your email above first.")
                    st.stop()
                if site_key and not captcha_token:
                    st.error("Please complete the human verification.")
                    st.stop()

                try:
                    sb = _supabase()

                    # Supabase expects type="signup" for confirmation resend in most setups.
                    base = _attach_captcha({"email": email, "type": "signup"}, captcha_token)

                    try:
                        sb.auth.resend(base)
                    except Exception:
                        # Fallback: some environments use "email" type
                        fallback = dict(base)
                        fallback["type"] = "email"
                        sb.auth.resend(fallback)

                    st.success("Confirmation email resent. Check your inbox and spam folder.")
                    st.stop()

                except Exception as e:
                    hint = _captcha_error_hint(e)
                    if hint:
                        st.error(hint)
                    st.error(f"Resend failed: {type(e).__name__}: {e}")
                    st.stop()

        st.markdown("---")
        st.caption(
            "If you see otp_expired, increase Email OTP Expiration in Supabase Auth settings, "
            "and ensure your app domain is in Supabase Redirect URLs."
        )

    with tab_signup:
        st.subheader("Create Account")
        email2 = st.text_input("Email", key="auth_signup_email")
        pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
        pw2 = st.text_input("Confirm password", type="password", key="auth_signup_pw2")

        policy = PasswordPolicy(min_len=MIN_PASSWORD_LEN_DEFAULT)
        score, unmet = _estimate_strength(pw1 or "", policy)

        st.caption("Password requirements:")
        st.write(f"- Minimum length: {policy.min_len} characters")
        if unmet:
            st.warning("Missing: " + ", ".join(unmet))
        st.progress(score / 100.0, text=f"Strength: {_strength_label(score)} ({score}/100)")

        captcha_token2 = None
        if site_key:
            st.caption("Human verification:")
            captcha_token2 = _render_captcha(site_key, name="signup")
        else:
            st.info("Turnstile site key not configured. If Supabase CAPTCHA protection is enabled, signup will fail.")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            _bump_turnstile_nonce("signup")

            if not email2 or not pw1 or not pw2:
                st.error("Email, password, and confirmation are required.")
                st.stop()
            if pw1 != pw2:
                st.error("Passwords do not match.")
                st.stop()
            if len(pw1) < policy.min_len:
                st.error(f"Password must be at least {policy.min_len} characters.")
                st.stop()
            if site_key and not captcha_token2:
                st.error("Please complete the human verification.")
                st.stop()

            try:
                sb = _supabase()
                payload = _attach_captcha({"email": email2, "password": pw1}, captcha_token2)

                resp = sb.auth.sign_up(payload)
                user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)

                if user:
                    st.success("Account created. Check your email for a confirmation link before signing in.")
                else:
                    st.warning(
                        "Signup submitted. If you do not receive an email, verify email provider settings "
                        "in Supabase Auth → Email."
                    )
                st.stop()

            except Exception as e:
                hint = _captcha_error_hint(e)
                if hint:
                    st.error(hint)
                st.error(f"Signup error: {type(e).__name__}: {e}")
                st.stop()

    st.stop()
    return None
