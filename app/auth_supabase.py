# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import requests
from typing import Any, Dict, Optional, Tuple

import streamlit as st
from supabase import Client, create_client

from app.components.hcaptcha_component.hcaptcha_component import hcaptcha

__all__ = [
    "require_login",
    "supabase_logout",
    "current_user",
    "supabase_for_user",
]

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

HCAPTCHA_SITE_KEY_KEY = "HCAPTCHA_SITE_KEY"
HCAPTCHA_SECRET_KEY = "HCAPTCHA_SECRET_KEY"
def verify_hcaptcha_token(token: str, secret_key: str, debug: bool = True) -> bool:
    """
    Verify hCaptcha token server-side. Always print the response to Streamlit for debugging.
    """
    if not token or not secret_key:
        st.error("Missing hCaptcha token or secret key for verification.")
        st.info(f"hCaptcha verification response: token={token}, secret_key={'set' if secret_key else 'missing'}")
        return False
    url = "https://hcaptcha.com/siteverify"
    data = {"secret": secret_key, "response": token}
    try:
        resp = requests.post(url, data=data, timeout=5)
        result = resp.json()
        st.info(f"hCaptcha verification response: {result}")
        return result.get("success", False)
    except Exception as e:
        st.error(f"Error verifying hCaptcha token: {e}")
        return False

MIN_PASSWORD_LEN_DEFAULT = 12


# ---------------------------------------------------------------------
# Config / secrets
# ---------------------------------------------------------------------
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v and str(v).strip():
        return str(v).strip()
    try:
        return st.secrets.get(name, default)  # type: ignore[attr-defined]
    except Exception:
        return default


def _get_supabase_client() -> Client:
    url = _get_secret(SUPABASE_URL_KEY)
    anon = _get_secret(SUPABASE_ANON_KEY_KEY)
    if not url or not anon:
        raise RuntimeError(
        from app.components.hcaptcha_component.hcaptcha_component import hcaptcha
            "Missing SUPABASE_URL and/or SUPABASE_ANON_KEY "
            "(env or .streamlit/secrets.toml)"
        )
        HCAPTCHA_SITE_KEY_KEY = "HCAPTCHA_SITE_KEY"
        HCAPTCHA_SECRET_KEY = "HCAPTCHA_SECRET_KEY"
        def verify_hcaptcha_token(token: str, secret_key: str, debug: bool = True) -> bool:


# ---------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class PasswordPolicy:
    min_len: int = MIN_PASSWORD_LEN_DEFAULT
    require_upper: bool = False
    require_lower: bool = False
    require_digit: bool = False
    require_symbol: bool = False


class PasswordStrength:
    @staticmethod
    def evaluate(pw: str, policy: PasswordPolicy) -> Tuple[int, list[str]]:
        unmet: list[str] = []
        pw = pw or ""
        class HcaptchaManager:
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

        # Deterministic heuristic score (UI-only; do not rely on this for security policy).
        score = 0
        score += min(len(pw) * 4, 44)  # length contribution
        score += 14 if has_lower else 0
        score += 14 if has_upper else 0
        score += 14 if has_digit else 0
        score += 14 if has_symbol else 0

        if len(pw) < 8:
            score = min(score, 45)
        if len(pw) < policy.min_len:
            score = min(score, 35)

        score = max(0, min(score, 100))
        return score, unmet

    @staticmethod
    def label(score: int) -> str:
        if score < 35:
            return "Weak"
        if score < 60:
            return "Fair"
        if score < 80:
            return "Good"
        return "Strong"


# ---------------------------------------------------------------------
# Session / tokens (fail-closed)
# ---------------------------------------------------------------------
_AUTH_KEYS = ["auth_user", "auth_access_token", "auth_refresh_token", "auth_last_set_ts"]


def _clear_auth_state() -> None:
    for k in _AUTH_KEYS:
        st.session_state.pop(k, None)


def _set_user_session(
    user: dict,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> None:
    st.session_state["auth_user"] = user
    if access_token:
        st.session_state["auth_access_token"] = access_token
    if refresh_token:
        st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_last_set_ts"] = time.time()


def _normalize_user(u: Any) -> dict:
    """
    Normalize the Supabase user object into a stable, JSON-serializable dict.
    Avoid storing user.__dict__ wholesale; keep only what you need.
    """
    if u is None:
        return {}

    if isinstance(u, dict):
        src = u
    else:
        src = getattr(u, "__dict__", {}) or {}

    return {
        "id": src.get("id"),
        "email": src.get("email"),
        "role": src.get("role"),
        "aud": src.get("aud"),
        "app_metadata": src.get("app_metadata") or {},
        "user_metadata": src.get("user_metadata") or {},
        "created_at": src.get("created_at"),
        "updated_at": src.get("updated_at"),
    }


def _extract_user_and_session(resp: Any) -> tuple[Optional[Any], Optional[Any]]:
    """
    Support both dict-like and attribute-like responses across supabase-py versions.
    """
    if resp is None:
        return None, None

    if isinstance(resp, dict):
        return resp.get("user"), resp.get("session")

    return getattr(resp, "user", None), getattr(resp, "session", None)


def _extract_access_refresh(session: Any) -> tuple[Optional[str], Optional[str]]:
    if session is None:
        return None, None
    if isinstance(session, dict):
        return session.get("access_token"), session.get("refresh_token")
    return getattr(session, "access_token", None), getattr(session, "refresh_token", None)


def _ensure_valid_session() -> Optional[dict]:
    """
    Validate current tokens with Supabase:
      - auth.set_session(access, refresh) (auto-refreshes access token if possible)
      - auth.get_user() for authoritative server validation
    If anything fails, clear local auth state and return None (fail closed).
    """
    access = st.session_state.get("auth_access_token")
    refresh = st.session_state.get("auth_refresh_token")
    if not access or not refresh:
        return None

    sb = _get_supabase_client()

    try:
        # Will refresh tokens if needed, or raise if invalid.
        set_resp = sb.auth.set_session(access, refresh)
        _, session = _extract_user_and_session(set_resp)

        new_access, new_refresh = _extract_access_refresh(session)
        if new_access:
            st.session_state["auth_access_token"] = new_access
        if new_refresh:
            st.session_state["auth_refresh_token"] = new_refresh

        # Authoritative validation on the server.
        user_resp = sb.auth.get_user()
        user_obj = (
            user_resp.get("user") if isinstance(user_resp, dict) else getattr(user_resp, "user", None)
        )
        if not user_obj:
            raise RuntimeError("No user returned from Supabase auth.get_user()")

        user_dict = _normalize_user(user_obj)
        st.session_state["auth_user"] = user_dict
        st.session_state["auth_last_set_ts"] = time.time()
        return user_dict

    except Exception:
        _clear_auth_state()
        return None


def current_user() -> Optional[dict]:
    """
    Cached user view. Do not use this alone for authorization decisions.
    require_login() calls _ensure_valid_session() first.
    """
    return st.session_state.get("auth_user")


def supabase_for_user() -> Client:
    """
    Returns a Supabase client bound to the current validated session.
    Fail-closed: if set_session fails, it clears auth state.
    """
    sb = _get_supabase_client()
    access = st.session_state.get("auth_access_token")
    refresh = st.session_state.get("auth_refresh_token")
    if access and refresh:
        try:
            sb.auth.set_session(access, refresh)
        except Exception:
            _clear_auth_state()
    return sb


def supabase_logout() -> None:
    """
    Best-effort remote sign-out, then clear local session state.
    """
    try:
        sb = _get_supabase_client()
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
    _clear_auth_state()


# ---------------------------------------------------------------------


# hCaptcha manager
class HcaptchaManager:
    def __init__(self, site_key: Optional[str]) -> None:
        self.site_key = site_key

    @staticmethod
    def _nonce_key(scope: str) -> str:
        return f"hcaptcha_nonce_{scope}"

    def bump_nonce(self, scope: str) -> None:
        key = self._nonce_key(scope)
        st.session_state[key] = int(st.session_state.get(key, 0)) + 1

    def _widget_key(self, scope: str) -> str:
        nonce = int(st.session_state.get(self._nonce_key(scope), 0))
        return f"hcaptcha_{scope}_{nonce}"

    def render(self, scope: str) -> Optional[str]:
        if not self.site_key:
            return None
        return hcaptcha(
            self.site_key,
            key=self._widget_key(scope),
            theme="light",
            size="normal",
        )

    @staticmethod
    def attach(payload: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
        """
        Attach hCaptcha token to Supabase Auth payload.
        supabase-py (v2+) expects the captcha token here:
            payload["options"]["captcha_token"]
        """
        if not token:
            return payload
        options = payload.get("options") or {}
        options["captcha_token"] = token
        payload["options"] = options
        return payload

# ---------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------
def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --main-pink: #ff2d95;
            --main-purple: #a259ff;
            --main-dark: #050509;
            --main-light: #f9fafb;
        }
        .auth-root {
            min-height: 100vh;
            display: flex;
            flex-direction: row;
            background: var(--main-dark);
            color: var(--main-light);
            margin: -3rem -3rem 0 -3rem;
        }
        .auth-left {
            flex: 1.1;
            padding: 4rem 3.5rem;
            background: radial-gradient(circle at top left, var(--main-pink) 0, var(--main-purple) 40%, var(--main-dark) 80%);
            color: var(--main-light);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .auth-left-logo {
            font-size: 1.1rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            font-weight: 600;
            opacity: 0.9;
        }
        .auth-left-title {
            font-size: 2.4rem;
            font-weight: 700;
            line-height: 1.2;
            margin-top: 2rem;
            color: var(--main-pink);
            text-shadow: 0 2px 16px var(--main-purple, #a259ff);
        }
        .auth-left-subtitle {
            margin-top: 1rem;
            font-size: 0.98rem;
            max-width: 26rem;
            opacity: 0.9;
        }
        .auth-left-footer {
            font-size: 0.8rem;
            opacity: 0.7;
        }
        .auth-right {
            flex: 1;
            background: var(--main-light);
            color: #2d0036;
            padding: 3.5rem 3rem;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .auth-card {
            max-width: 420px;
            margin: 0 auto;
            background: #fff;
            border-radius: 18px;
            padding: 2.2rem 2.4rem;
            box-shadow: 0 18px 45px rgba(255, 45, 149, 0.10), 0 2px 8px rgba(162, 89, 255, 0.08);
            border: 1px solid var(--main-pink, #ff2d95);
        }
        .auth-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            color: var(--main-pink);
            letter-spacing: 0.01em;
        }
        .auth-caption {
            font-size: 0.95rem;
            color: var(--main-purple);
            margin-bottom: 1.5rem;
        }
        .auth-tabs-row {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .auth-tab-pill {
            flex: 1;
            text-align: center;
            padding: 0.55rem 0.75rem;
            border-radius: 999px;
            font-size: 1rem;
            border: 2px solid transparent;
            font-weight: 600;
            transition: background 0.2s, color 0.2s, border 0.2s;
        }
        .auth-tab-pill-active {
            background: linear-gradient(90deg, var(--main-pink), var(--main-purple));
            color: #fff;
            border-color: var(--main-pink);
            box-shadow: 0 2px 12px var(--main-pink, #ff2d95, 0.12);
        }
        .auth-tab-pill-inactive {
            background: var(--main-light);
            color: var(--main-purple);
            border-color: var(--main-purple);
        }
        .auth-label {
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            color: var(--main-pink);
        }
        .auth-footer-note {
            margin-top: 1.5rem;
            font-size: 0.85rem;
            color: var(--main-purple);
        }
        .auth-progress-label {
            font-size: 0.85rem;
            margin-top: 0.25rem;
            color: var(--main-pink);
        }
        /* Streamlit button overrides */
        button[kind="primary"], .stButton > button {
            background: linear-gradient(90deg, var(--main-pink), var(--main-purple));
            color: #fff;
            border: none;
            border-radius: 999px;
            font-weight: 700;
            font-size: 1.05rem;
            padding: 0.6rem 1.5rem;
            box-shadow: 0 2px 12px var(--main-pink, #ff2d95, 0.12);
            transition: background 0.2s, color 0.2s;
        }
        button[kind="primary"]:hover, .stButton > button:hover {
            background: linear-gradient(90deg, var(--main-purple), var(--main-pink));
            color: #fff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------
def require_login() -> Optional[dict]:
    """
    Entry gate for Streamlit pages.

    - Validates tokens with Supabase (fail-closed) before granting access.
    - If not authenticated, renders the login/signup UI and stops execution.
    """
    user = _ensure_valid_session()
    if user:
        return user

    _inject_styles()
    site_key = _get_secret(HCAPTCHA_SITE_KEY_KEY)
    hcaptcha_mgr = HcaptchaManager(site_key)

    if "auth_active_tab" not in st.session_state:
        st.session_state["auth_active_tab"] = "login"

    with st.container():
        st.markdown('<div class="auth-root">', unsafe_allow_html=True)

        _render_left_panel()

        st.markdown('<div class="auth-right"><div class="auth-card">', unsafe_allow_html=True)
        _render_tabs()

        active_tab = st.session_state["auth_active_tab"]
        if active_tab == "login":
            _render_login(hcaptcha_mgr)
        else:
            _render_signup(hcaptcha_mgr)

        st.markdown("</div></div></div>", unsafe_allow_html=True)

    st.stop()
    return None


# ---------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------
def _render_left_panel() -> None:
    st.markdown(
        """
        <div class="auth-left">
          <div>
            <div class="auth-left-logo">8LAW</div>
            <div class="auth-left-title">
              Secure access<br/>for serious accounting workflows.
            </div>
            <div class="auth-left-subtitle">
              Multi-tenant, RLS-enforced, audit-ready. Your ledgers stay isolated,
              your automations stay explainable, and every action leaves a trail.
            </div>
          </div>
          <div class="auth-left-footer">
            Protected by Supabase Auth and Row Level Security.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_tabs() -> None:
    col_login, col_signup = st.columns(2)

    with col_login:
        if st.button("Sign In", key="auth_tab_login_btn"):
            st.session_state["auth_active_tab"] = "login"
        active = st.session_state["auth_active_tab"] == "login"
        cls = "auth-tab-pill auth-tab-pill-active" if active else "auth-tab-pill auth-tab-pill-inactive"
        st.markdown(f'<div class="{cls}">Sign In</div>', unsafe_allow_html=True)

    with col_signup:
        if st.button("Create Account", key="auth_tab_signup_btn"):
            st.session_state["auth_active_tab"] = "signup"
        active = st.session_state["auth_active_tab"] == "signup"
        cls = "auth-tab-pill auth-tab-pill-active" if active else "auth-tab-pill auth-tab-pill-inactive"
        st.markdown(f'<div class="{cls}">Create Account</div>', unsafe_allow_html=True)


def _render_login(hcaptcha_mgr: HcaptchaManager) -> None:
    st.markdown('<div class="auth-title">Welcome back</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="auth-caption">Sign in to continue your 8law session.</div>',
        unsafe_allow_html=True,
    )

    st.text_input("Email", key="auth_login_email")
    st.text_input("Password", type="password", key="auth_login_password")

    email = st.session_state.get("auth_login_email", "").strip()
    password = st.session_state.get("auth_login_password", "")


    captcha_token = None
    if hcaptcha_mgr.site_key:
        st.markdown('<div class="auth-label">Human verification</div>', unsafe_allow_html=True)
        captcha_token = hcaptcha_mgr.render("login")
        if not captcha_token:
            st.info("Complete the verification to proceed.")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Sign In", type="primary", key="auth_login_btn"):
            if not email or not password:
                st.error("Email and password are required.")
                st.stop()

            #
            pass

            try:
                sb = _get_supabase_client()
                payload: Dict[str, Any] = {"email": email, "password": password}
                payload = HcaptchaManager.attach(payload, captcha_token)

                resp = sb.auth.sign_in_with_password(payload)
                user_obj, session = _extract_user_and_session(resp)

                if not user_obj or not session:
                    st.error("Sign-in failed. Check credentials and email confirmation status.")
                    hcaptcha_mgr.bump_nonce("login")
                    st.stop()

                access_token, refresh_token = _extract_access_refresh(session)
                if not access_token or not refresh_token:
                    st.error("Sign-in failed: missing session tokens.")
                    hcaptcha_mgr.bump_nonce("login")
                    st.stop()

                _set_user_session(
                    _normalize_user(user_obj),
                    access_token,
                    refresh_token,
                )

                # Immediately validate/refresh and normalize server-side.
                valid_user = _ensure_valid_session()
                if not valid_user:
                    st.error("Sign-in failed: session validation error.")
                    pass
                    st.stop()

                hcaptcha_mgr.bump_nonce("login")
                st.rerun()

            except Exception as e:
                hcaptcha_mgr.bump_nonce("login")
                st.error(f"Sign-in error: {type(e).__name__}: {e}")

    with col_b:
        if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
            if not email:
                st.error("Enter your email above first.")
                st.stop()
            if hcaptcha_mgr.site_key and not captcha_token:
                st.error("Please complete the human verification.")
                st.stop()

            try:
                sb = _get_supabase_client()
                resend_payload: Dict[str, Any] = {"type": "signup", "email": email}
                resend_payload = HcaptchaManager.attach(resend_payload, captcha_token)

                sb.auth.resend(resend_payload)
                hcaptcha_mgr.bump_nonce("login")
                st.success("Confirmation email resent. Check your inbox and spam folder.")
            except Exception as e:
                pass
                st.error(f"Resend failed: {type(e).__name__}: {e}")

    st.markdown(
        '<div class="auth-footer-note">Trouble signing in? Confirm your email is verified in your inbox.</div>',
        unsafe_allow_html=True,
    )


def _render_signup(hcaptcha_mgr: HcaptchaManager) -> None:
    st.markdown('<div class="auth-title">Create your 8law account</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="auth-caption">One secure login for all your clients and ledgers.</div>',
        unsafe_allow_html=True,
    )

    st.text_input("Email", key="auth_signup_email")
    st.text_input("Password", type="password", key="auth_signup_pw1")
    st.text_input("Confirm password", type="password", key="auth_signup_pw2")

    email2 = st.session_state.get("auth_signup_email", "").strip()
    pw1 = st.session_state.get("auth_signup_pw1", "")
    pw2 = st.session_state.get("auth_signup_pw2", "")

    policy = PasswordPolicy()
    score, unmet = PasswordStrength.evaluate(pw1 or "", policy)

    st.markdown('<div class="auth-label">Password requirements</div>', unsafe_allow_html=True)
    st.write(f"- Minimum length: {policy.min_len} characters")
    if unmet:
        st.warning("Missing: " + ", ".join(unmet))
    st.progress(score / 100.0)
    st.markdown(
        f'<div class="auth-progress-label">Strength: {PasswordStrength.label(score)} ({score}/100)</div>',
        unsafe_allow_html=True,
    )

    captcha_token2 = None
    if hcaptcha_mgr.site_key:
        st.markdown('<div class="auth-label">Human verification</div>', unsafe_allow_html=True)
        captcha_token2 = hcaptcha_mgr.render("signup")
        if not captcha_token2:
            st.info("Complete the verification to proceed.")


    if st.button("Create Account", type="primary", key="auth_signup_btn"):
        if not email2 or not pw1 or not pw2:
            st.error("Email, password, and confirmation are required.")
            st.stop()
        if pw1 != pw2:
            st.error("Passwords do not match.")
            st.stop()
        if len(pw1) < policy.min_len:
            st.error(f"Password must be at least {policy.min_len} characters.")
            st.stop()
        #
        pass

        try:
            sb = _get_supabase_client()
            payload: Dict[str, Any] = {"email": email2, "password": pw1}
            payload = HcaptchaManager.attach(payload, captcha_token2)

            resp = sb.auth.sign_up(payload)
            user_obj, _ = _extract_user_and_session(resp)

            hcaptcha_mgr.bump_nonce("signup")

            if user_obj:
                st.success("Account created. Check your email for a confirmation link before signing in.")
            else:
                st.warning(
                    "Signup submitted. If you do not receive an email, verify provider "
                    "settings in Supabase Auth → Email."
                )
        except Exception as e:
            pass
            st.error(f"Signup error: {type(e).__name__}: {e}")

    st.markdown(
        '<div class="auth-footer-note">By creating an account you agree to keep client data confidential and audit-ready.</div>',
        unsafe_allow_html=True,
    )
