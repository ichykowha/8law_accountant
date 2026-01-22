# app/auth_supabase.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests
import streamlit as st
from supabase import create_client, Client


# =============================================================================
# Secrets / Config
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

# Optional: your deployed app URL (used only for guidance text)
AUTH_REDIRECT_URL_KEY = "AUTH_REDIRECT_URL"

# Client-side UX policy (server-side policy still enforced by Supabase settings)
MIN_PASSWORD_LEN_DEFAULT = 12


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
# Session model
# =============================================================================

@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str


def _set_user_session(user_id: str, email: str, access_token: Optional[str], refresh_token: Optional[str]) -> None:
    st.session_state["auth_user"] = {"id": user_id, "email": email}
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_last_set_ts"] = time.time()


def current_user() -> Optional[AuthUser]:
    u = st.session_state.get("auth_user")
    if not u or not isinstance(u, dict):
        return None
    uid = u.get("id")
    em = u.get("email")
    if not uid or not em:
        return None
    return AuthUser(user_id=str(uid), email=str(em))


def supabase_logout() -> None:
    """
    Clears local Streamlit auth state, and attempts Supabase sign_out().
    """
    try:
        sb = _supabase()
        access = st.session_state.get("auth_access_token")
        refresh = st.session_state.get("auth_refresh_token") or ""
        if access:
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

    for k in [
        "auth_user",
        "auth_access_token",
        "auth_refresh_token",
        "auth_last_set_ts",
        "current_client_id",
    ]:
        if k in st.session_state:
            del st.session_state[k]


# =============================================================================
# Resend confirmation: direct HTTP fallback
# =============================================================================

def _resend_confirmation_email(email: str) -> Dict[str, Any]:
    """
    Best-effort resend confirmation email.
    Uses Supabase Auth REST endpoint directly to avoid SDK mismatch.

    Endpoint: POST {SUPABASE_URL}/auth/v1/resend
    Headers: apikey + Authorization: Bearer {anon_key}
    Body: { "type": "signup", "email": ... }
    """
    url = _get_secret(SUPABASE_URL_KEY)
    anon = _get_secret(SUPABASE_ANON_KEY_KEY)
    if not url or not anon:
        return {"ok": False, "error": "Missing SUPABASE_URL / SUPABASE_ANON_KEY"}

    endpoint = url.rstrip("/") + "/auth/v1/resend"
    headers = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
        "Content-Type": "application/json",
    }
    payload = {"type": "signup", "email": email}

    try:
        r = requests.post(endpoint, headers=headers, json=payload, timeout=12)
        if 200 <= r.status_code < 300:
            return {"ok": True, "status_code": r.status_code}
        return {"ok": False, "status_code": r.status_code, "response": _safe_json(r)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _safe_json(r: requests.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return r.text


# =============================================================================
# UI helpers
# =============================================================================

def _password_requirements_block(min_len: int) -> None:
    st.caption("Password policy")
    st.write(f"- Minimum length: {min_len} characters")
    st.write("- Avoid reused passwords (enable leaked-password protection in Supabase)")
    st.write("- Use a unique password per account")


def _basic_strength_score(pw: str) -> int:
    """
    Deterministic, minimal, no extra deps.
    Score 0..100.
    """
    if not pw:
        return 0
    length = len(pw)
    has_lower = any("a" <= c <= "z" for c in pw)
    has_upper = any("A" <= c <= "Z" for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    has_symbol = any(not c.isalnum() for c in pw)

    score = 0
    score += min(length * 5, 50)  # length up to 50
    score += 15 if has_lower else 0
    score += 15 if has_upper else 0
    score += 10 if has_digit else 0
    score += 10 if has_symbol else 0

    # cap for short passwords
    if length < 12:
        score = min(score, 60)
    if length < 8:
        score = min(score, 35)

    return max(0, min(score, 100))


def _strength_label(score: int) -> str:
    if score < 35:
        return "Weak"
    if score < 60:
        return "Fair"
    if score < 80:
        return "Good"
    return "Strong"


# =============================================================================
# Main gate
# =============================================================================

def require_login() -> AuthUser:
    """
    Hard gate: blocks app until user is authenticated.
    Returns AuthUser.
    """
    u = current_user()
    if u:
        return u

    st.set_page_config(page_title="8law Secure Access", page_icon="⚖️", layout="centered")
    st.title("8law Secure Access")

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        st.subheader("Sign In")
        email = st.text_input("Email", key="auth_login_email")
        password = st.text_input("Password", type="password", key="auth_login_password")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                if not email or not password:
                    st.error("Email and password are required.")
                else:
                    try:
                        sb = _supabase()
                        resp = sb.auth.sign_in_with_password({"email": email, "password": password})

                        user_obj = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                        sess_obj = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                        if not user_obj:
                            st.error("Sign-in failed. Check credentials and email confirmation status.")
                        else:
                            # Normalize user/session objects
                            user_dict = user_obj if isinstance(user_obj, dict) else user_obj.__dict__
                            uid = str(user_dict.get("id") or "")
                            em = str(user_dict.get("email") or email)

                            access = None
                            refresh = None
                            if sess_obj:
                                sess_dict = sess_obj if isinstance(sess_obj, dict) else sess_obj.__dict__
                                access = sess_dict.get("access_token")
                                refresh = sess_dict.get("refresh_token")

                            if not uid:
                                st.error("Sign-in failed: missing user id from Supabase response.")
                            else:
                                _set_user_session(uid, em, access, refresh)
                                st.rerun()
                    except Exception as e:
                        st.error(f"Sign-in error: {type(e).__name__}: {e}")

        with col2:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                if not email:
                    st.error("Enter your email above first.")
                else:
                    result = _resend_confirmation_email(email)
                    if result.get("ok"):
                        st.success("Confirmation email resent. Check your inbox/spam.")
                    else:
                        st.warning(
                            "Unable to resend via API. You can resend from Supabase Dashboard: "
                            "Authentication → Users → select user → resend invite/confirmation."
                        )
                        st.write(result)

        st.markdown("---")
        redirect_url = _get_secret(AUTH_REDIRECT_URL_KEY)
        st.caption("Deployment notes")
        if redirect_url:
            st.write(f"- Expected redirect URL: `{redirect_url}` (must be included in Supabase Auth URL Configuration).")
        st.write("- If you see `otp_expired`, increase Email OTP Expiration in Supabase Auth settings.")
        st.write("- Ensure your Streamlit app domain is added to Supabase Additional Redirect URLs.")

    with tab_signup:
        st.subheader("Create Account")
        email2 = st.text_input("Email", key="auth_signup_email")
        pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
        pw2 = st.text_input("Confirm Password", type="password", key="auth_signup_pw2")

        min_len = MIN_PASSWORD_LEN_DEFAULT
        _password_requirements_block(min_len)

        score = _basic_strength_score(pw1 or "")
        st.progress(score / 100.0, text=f"Strength: {_strength_label(score)} ({score}/100)")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            if not email2 or not pw1 or not pw2:
                st.error("Email, password, and confirmation are required.")
            elif pw1 != pw2:
                st.error("Passwords do not match.")
            elif len(pw1) < min_len:
                st.error(f"Password must be at least {min_len} characters.")
            else:
                try:
                    sb = _supabase()
                    resp = sb.auth.sign_up({"email": email2, "password": pw1})

                    user_obj = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                    if user_obj:
                        st.success("Account created. Check your email for a confirmation link before signing in.")
                    else:
                        st.warning(
                            "Signup submitted. If no email arrives, confirm your Supabase email provider configuration."
                        )
                except Exception as e:
                    st.error(f"Signup error: {type(e).__name__}: {e}")

    st.stop()
