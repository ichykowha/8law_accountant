# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import streamlit as st
from supabase import Client, create_client

from app.components.turnstile_component import reset_turnstile, turnstile_token


# =============================================================================
# Configuration / Secrets
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

# Optional Turnstile (Cloudflare)
TURNSTILE_SITE_KEY_KEY = "CLOUDFLARE_TURNSTILE_SITE_KEY"

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


def supabase_logout() -> None:
    try:
        sb = _supabase()
        access = st.session_state.get("auth_access_token")
        if access:
            sb.auth.set_session(access, st.session_state.get("auth_refresh_token") or "")
        sb.auth.sign_out()
    except Exception:
        pass

    for k in ["auth_user", "auth_access_token", "auth_refresh_token", "auth_last_set_ts"]:
        st.session_state.pop(k, None)


# =============================================================================
# Auth UI / Flows
# =============================================================================

def _require_turnstile(site_key: str, component_key: str) -> Optional[str]:
    """
    Renders Turnstile and requires completion.
    Provides a deterministic reset control to break any stuck state.
    """
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.caption("Human verification:")
    with col_b:
        if st.button("Reset verification", key=f"{component_key}__reset_btn"):
            reset_turnstile(component_key)
            st.rerun()

    token = turnstile_token(site_key=site_key, component_key=component_key, height=90)
    if not token:
        st.warning("Please complete the human verification.")
        return None
    return token


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
            captcha_token = _require_turnstile(site_key, component_key="turnstile_login")

        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                if not email or not password:
                    st.error("Email and password are required.")
                elif site_key and not captcha_token:
                    st.error("Complete the human verification to proceed.")
                else:
                    try:
                        sb = _supabase()
                        payload: Dict[str, Any] = {"email": email, "password": password}
                        if captcha_token:
                            payload["captcha_token"] = captcha_token

                        resp = sb.auth.sign_in_with_password(payload)

                        user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                        session = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                        if not user:
                            st.error("Sign-in failed. Check credentials and email confirmation status.")
                        else:
                            access_token = getattr(session, "access_token", None) if session else None
                            refresh_token = getattr(session, "refresh_token", None) if session else None
                            _set_user_session(user if isinstance(user, dict) else user.__dict__, access_token, refresh_token)

                            # Clear captcha token state after use
                            reset_turnstile("turnstile_login")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Sign-in error: {type(e).__name__}: {e}")

        with col_b:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                if not email:
                    st.error("Enter your email above first.")
                elif site_key and not captcha_token:
                    st.error("Complete the human verification to proceed.")
                else:
                    try:
                        sb = _supabase()
                        resend_payload: Dict[str, Any] = {"type": "signup", "email": email}
                        if captcha_token:
                            resend_payload["captcha_token"] = captcha_token

                        try:
                            sb.auth.resend(resend_payload)
                            st.success("Confirmation email resent. Check your inbox and spam folder.")
                            reset_turnstile("turnstile_login")
                        except Exception as inner:
                            st.error(
                                "Unable to resend via API. You can resend from Supabase Dashboard: "
                                "Authentication → Users → select user → resend invite/confirmation.\n\n"
                                f"{type(inner).__name__}: {inner}"
                            )
                    except Exception as e:
                        st.error(f"Resend failed: {type(e).__name__}: {e}")

        st.markdown("---")
        st.caption(
            "If you see otp_expired, increase Email OTP Expiration in Supabase Auth settings, "
            "and ensure your Streamlit domain is in Supabase Redirect URLs."
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
            captcha_token2 = _require_turnstile(site_key, component_key="turnstile_signup")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            if not email2 or not pw1 or not pw2:
                st.error("Email, password, and confirmation are required.")
            elif pw1 != pw2:
                st.error("Passwords do not match.")
            elif len(pw1) < policy.min_len:
                st.error(f"Password must be at least {policy.min_len} characters.")
            elif site_key and not captcha_token2:
                st.error("Complete the human verification to proceed.")
            else:
                try:
                    sb = _supabase()
                    payload: Dict[str, Any] = {"email": email2, "password": pw1}
                    if captcha_token2:
                        payload["captcha_token"] = captcha_token2

                    resp = sb.auth.sign_up(payload)
                    user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)

                    if user:
                        st.success("Account created. Check your email for a confirmation link before signing in.")
                        reset_turnstile("turnstile_signup")
                    else:
                        st.warning(
                            "Signup submitted. If you do not receive an email, verify email provider settings "
                            "in Supabase Auth → Email."
                        )
                except Exception as e:
                    st.error(f"Signup error: {type(e).__name__}: {e}")

    st.stop()
    return None
