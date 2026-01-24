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
    Used by DB modules so PostgREST calls respect RLS with the user's JWT.
    """
    sb = _supabase()

    access = st.session_state.get("auth_access_token")
    refresh = st.session_state.get("auth_refresh_token")
    if access and refresh:
        try:
            sb.auth.set_session(access, refresh)
        except Exception:
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
# Turnstile helper
# =============================================================================

def _render_captcha(site_key: str, *, key: str) -> Optional[str]:
    """
    Render Turnstile and return token (or None).
    We force appearance='always' during debugging.
    """
    token = render_turnstile(
        site_key,
        key=key,
        theme="auto",
        size="normal",
        appearance="always",
    )
    return token


def _attach_captcha(payload: Dict[str, Any], captcha_token: Optional[str]) -> Dict[str, Any]:
    """
    Supabase Auth (GoTrue) validates CAPTCHA from request body fields.
    Different clients map this differently, so we include all supported encodings:

    - top-level captcha_token (Auth reads request body for captcha_token)
    - gotrue_meta_security: { captcha_token: ... } (auth-go security embed)
    - options: { captchaToken: ... } (supabase-js convention; harmless if ignored)

    This avoids “token generated but not received” failures.
    """
    if not captcha_token:
        return payload

    payload = dict(payload)  # no mutation surprises

    payload["captcha_token"] = captcha_token
    payload["gotrue_meta_security"] = {"captcha_token": captcha_token}

    opts = payload.get("options") or {}
    if isinstance(opts, dict):
        opts = dict(opts)
        opts["captchaToken"] = captcha_token
        payload["options"] = opts

    return payload


def _consume_turnstile_value(component_key: str) -> None:
    """
    Turnstile tokens are single-use and short-lived.
    After any submit attempt, force the UI to require a fresh verification.
    """
    st.session_state.pop(component_key, None)


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
            captcha_token = _render_captcha(site_key, key="turnstile_login")

        # Optional debug (remove later)
        with st.expander("CAPTCHA debug", expanded=False):
            st.write(
                {
                    "site_key_present": bool(site_key),
                    "token_present": bool(captcha_token),
                    "token_len": len(captcha_token) if captcha_token else 0,
                }
            )

        if site_key and not captcha_token:
            st.info("Complete the verification to proceed.")

        col_a, col_b = st.columns([1, 1])

        with col_a:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                if not email or not password:
                    st.error("Email and password are required.")
                    return None
                if site_key and not captcha_token:
                    st.error("Please complete the human verification.")
                    return None

                try:
                    sb = _supabase()

                    base_payload: Dict[str, Any] = {"email": email, "password": password}
                    payload = _attach_captcha(base_payload, captcha_token)

                    resp = sb.auth.sign_in_with_password(payload)

                    user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                    session = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                    if not user:
                        st.error("Sign-in failed. Check credentials and email confirmation status.")
                        return None

                    access_token = getattr(session, "access_token", None) if session else None
                    refresh_token = getattr(session, "refresh_token", None) if session else None
                    _set_user_session(user if isinstance(user, dict) else user.__dict__, access_token, refresh_token)

                    # consume token so next action must re-verify
                    if site_key:
                        _consume_turnstile_value("turnstile_login")

                    st.rerun()

                except Exception as e:
                    # consume token even on failure; Turnstile tokens are often single-use
                    if site_key:
                        _consume_turnstile_value("turnstile_login")
                    st.error(f"Sign-in error: {type(e).__name__}: {e}")

        with col_b:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                if not email:
                    st.error("Enter your email above first.")
                    return None
                if site_key and not captcha_token:
                    st.error("Please complete the human verification.")
                    return None

                try:
                    sb = _supabase()

                    base_payload: Dict[str, Any] = {"type": "signup", "email": email}
                    payload = _attach_captcha(base_payload, captcha_token)

                    sb.auth.resend(payload)

                    if site_key:
                        _consume_turnstile_value("turnstile_login")

                    st.success("Confirmation email resent. Check your inbox and spam folder.")

                except Exception as e:
                    if site_key:
                        _consume_turnstile_value("turnstile_login")
                    st.error(f"Resend failed: {type(e).__name__}: {e}")

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
            captcha_token2 = _render_captcha(site_key, key="turnstile_signup")

        with st.expander("CAPTCHA debug (signup)", expanded=False):
            st.write(
                {
                    "site_key_present": bool(site_key),
                    "token_present": bool(captcha_token2),
                    "token_len": len(captcha_token2) if captcha_token2 else 0,
                }
            )

        if site_key and not captcha_token2:
            st.info("Complete the verification to proceed.")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            if not email2 or not pw1 or not pw2:
                st.error("Email, password, and confirmation are required.")
                return None
            if pw1 != pw2:
                st.error("Passwords do not match.")
                return None
            if len(pw1) < policy.min_len:
                st.error(f"Password must be at least {policy.min_len} characters.")
                return None
            if site_key and not captcha_token2:
                st.error("Please complete the human verification.")
                return None

            try:
                sb = _supabase()

                base_payload: Dict[str, Any] = {"email": email2, "password": pw1}
                payload = _attach_captcha(base_payload, captcha_token2)

                resp = sb.auth.sign_up(payload)
                user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)

                if site_key:
                    _consume_turnstile_value("turnstile_signup")

                if user:
                    st.success("Account created. Check your email for a confirmation link before signing in.")
                else:
                    st.warning(
                        "Signup submitted. If you do not receive an email, verify email provider settings "
                        "in Supabase Auth → Email."
                    )

            except Exception as e:
                if site_key:
                    _consume_turnstile_value("turnstile_signup")
                st.error(f"Signup error: {type(e).__name__}: {e}")

    st.stop()
    return None
