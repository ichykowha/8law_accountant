# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import streamlit as st
from supabase import Client, create_client


# =============================================================================
# Configuration / Secrets
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"
AUTH_REDIRECT_URL_KEY = "AUTH_REDIRECT_URL"

# Client-side UX only (Supabase enforces server-side rules too)
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
# Password policy UX helpers (client-side)
# =============================================================================

@dataclass
class PasswordPolicy:
    min_len: int = MIN_PASSWORD_LEN_DEFAULT
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = True


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

    # Simple heuristic
    score = 0
    score += min(len(pw) * 4, 40)
    score += 15 if has_lower else 0
    score += 15 if has_upper else 0
    score += 15 if has_digit else 0
    score += 15 if has_symbol else 0

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
    st.session_state["auth_access_token"] = access_token
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
        access = st.session_state.get("auth_access_token")
        refresh = st.session_state.get("auth_refresh_token")
        if access and refresh:
            sb.auth.set_session(access, refresh)
        sb.auth.sign_out()
    except Exception:
        pass

    for k in [
        "auth_user",
        "auth_access_token",
        "auth_refresh_token",
        "auth_last_set_ts",
    ]:
        st.session_state.pop(k, None)


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

    # Helpful note about captcha setting (since Turnstile in Streamlit is non-trivial)
    st.info(
        "If you enabled Supabase Captcha protection (Turnstile), disable it for now unless you have a dedicated web frontend "
        "to supply captcha tokens. Streamlit cannot reliably pass Turnstile tokens back to Python without a packaged component."
    )

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        st.subheader("Sign In")
        email = st.text_input("Email", key="auth_login_email")
        password = st.text_input("Password", type="password", key="auth_login_password")

        col_a, col_b = st.columns([1, 1])

        with col_a:
            if st.button("Sign In", type="primary", key="auth_login_btn"):
                if not email or not password:
                    st.error("Email and password are required.")
                else:
                    try:
                        sb = _supabase()
                        resp = sb.auth.sign_in_with_password({"email": email, "password": password})

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
                        # NOTE: supabase-py client-side resend support varies by version and auth config.
                        # For reliable resend, use Supabase Dashboard -> Auth -> Users -> resend / invite.
                        try:
                            sb.auth.resend({"type": "signup", "email": email})
                            st.success("Confirmation email resent. Check your inbox and spam folder.")
                        except Exception:
                            st.warning(
                                "Resend is not available from this client context. "
                                "Use Supabase Dashboard → Authentication → Users to resend/invite."
                            )
                    except Exception as e:
                        st.error(f"Resend failed: {type(e).__name__}: {e}")

        st.markdown("---")
        st.caption(
            "If you see OTP expired errors, increase Email OTP Expiration in Supabase Auth settings, "
            "and ensure your Streamlit app URL is in Supabase URL Configuration."
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
        st.write("- At least one uppercase letter")
        st.write("- At least one lowercase letter")
        st.write("- At least one number")
        st.write("- At least one symbol")

        if unmet:
            st.warning("Missing: " + ", ".join(unmet))
        st.progress(score / 100.0, text=f"Strength: {_strength_label(score)} ({score}/100)")

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

                    # Redirect URL for email confirmations (optional; Supabase settings still matter most)
                    redirect_to = _get_secret(AUTH_REDIRECT_URL_KEY)
                    payload = {"email": email2, "password": pw1}
                    if redirect_to:
                        payload["options"] = {"email_redirect_to": redirect_to}

                    resp = sb.auth.sign_up(payload)

                    user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                    if user:
                        st.success("Account created. Check your email for a confirmation link before signing in.")
                    else:
                        st.warning(
                            "Signup submitted. If you do not receive an email, verify email provider settings "
                            "in Supabase Auth → Email."
                        )
                except Exception as e:
                    st.error(f"Signup error: {type(e).__name__}: {e}")

    st.stop()
    return None
