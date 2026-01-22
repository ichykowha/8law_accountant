# app/auth_supabase.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List

import requests
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client


# =============================================================================
# Secrets / Config
# =============================================================================

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"

# Turnstile (Cloudflare) optional
TURNSTILE_SITE_KEY_KEY = "CLOUDFLARE_TURNSTILE_SITE_KEY"
TURNSTILE_SECRET_KEY_KEY = "CLOUDFLARE_TURNSTILE_SECRET_KEY"

# Where Supabase email links should redirect after confirmation / recovery
# Put your Streamlit Cloud URL here.
AUTH_REDIRECT_URL_KEY = "AUTH_REDIRECT_URL"  # e.g. https://8lawaccountant-xxxxx.streamlit.app

# Client-side UX policy (Supabase enforces server-side too)
MIN_PASSWORD_LEN_DEFAULT = 10  # recommend 10+ for finance apps


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


def _auth_redirect_url() -> Optional[str]:
    # Prefer explicit secret; otherwise attempt to infer from Streamlit runtime.
    explicit = _get_secret(AUTH_REDIRECT_URL_KEY)
    if explicit:
        return explicit.rstrip("/")
    # Fallback: Streamlit may provide this in runtime, but do not rely on it.
    return None


# =============================================================================
# Turnstile component (returns token)
# =============================================================================

_COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "components", "turnstile_component")
_turnstile_component = None
if os.path.isdir(_COMPONENT_PATH):
    _turnstile_component = components.declare_component(
        "turnstile_component",
        path=_COMPONENT_PATH,
    )


def turnstile_token(site_key: str, key: str) -> Optional[str]:
    """
    Renders Turnstile and returns a token (string) once the user passes.
    Requires app/components/turnstile_component/index.html to exist.
    """
    if not _turnstile_component:
        st.warning(
            "Turnstile component not found. Create app/components/turnstile_component/index.html "
            "from the provided code, or disable Captcha in Supabase."
        )
        return None

    # Component returns token or None
    token = _turnstile_component(site_key=site_key, key=key, default=None)
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _verify_turnstile_if_possible(token: Optional[str]) -> Tuple[bool, str]:
    """
    Optional server-side verification (defense-in-depth).
    If TURNSTILE_SECRET is not set, we skip verification and just return OK.
    """
    if not token:
        return False, "Missing Turnstile token."

    secret = _get_secret(TURNSTILE_SECRET_KEY_KEY)
    if not secret:
        # Supabase can still verify if captcha protection is enabled on their side,
        # but we cannot do our own server-side verify without the secret.
        return True, "Turnstile secret not set; skipping local verification."

    try:
        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token},
            timeout=10,
        )
        data = resp.json() if resp.ok else {}
        if data.get("success") is True:
            return True, "Turnstile verified."
        # Provide minimal failure detail (avoid leaking anything sensitive)
        return False, f"Turnstile verification failed: {data.get('error-codes') or 'unknown'}"
    except Exception as e:
        return False, f"Turnstile verification error: {type(e).__name__}"


# =============================================================================
# Password UX helpers (client-side)
# =============================================================================

@dataclass
class PasswordPolicy:
    min_len: int = MIN_PASSWORD_LEN_DEFAULT
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = True


def _estimate_strength(pw: str, policy: PasswordPolicy) -> Tuple[int, List[str]]:
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
    score += min(len(pw) * 4, 40)  # length up to 40
    score += 15 if has_lower else 0
    score += 15 if has_upper else 0
    score += 15 if has_digit else 0
    score += 15 if has_symbol else 0

    # Penalize short
    if len(pw) < 10:
        score = min(score, 55)
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

def _set_user_session(user: dict, access_token: Optional[str], refresh_token: Optional[str]) -> None:
    st.session_state["auth_user"] = user
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_last_set_ts"] = time.time()


def current_user() -> Optional[dict]:
    return st.session_state.get("auth_user")


def supabase_logout() -> None:
    try:
        sb = _supabase()
        access = st.session_state.get("auth_access_token")
        refresh = st.session_state.get("auth_refresh_token") or ""
        if access:
            # set_session(access, refresh) is supported in newer clients; safe to try
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
# Resend confirmation (with robust fallback)
# =============================================================================

def _resend_signup_confirmation(email: str) -> Tuple[bool, str]:
    """
    Uses supabase.auth.resend if available, otherwise falls back to REST.
    Supabase docs show: auth.resend({"type":"signup","email":..., "options":{"email_redirect_to":...}})
    """
    sb = _supabase()
    redirect_to = _auth_redirect_url()

    payload = {"type": "signup", "email": email}
    if redirect_to:
        payload["options"] = {"email_redirect_to": redirect_to}

    # Preferred: SDK
    if hasattr(sb.auth, "resend"):
        try:
            sb.auth.resend(payload)
            return True, "Confirmation email resent. Check inbox/spam."
        except Exception as e:
            # fall through to REST
            sdk_err = f"{type(e).__name__}: {e}"
    else:
        sdk_err = "SDK resend() not available."

    # Fallback: REST
    try:
        url = _get_secret(SUPABASE_URL_KEY)
        anon = _get_secret(SUPABASE_ANON_KEY_KEY)
        if not url or not anon:
            return False, "Missing SUPABASE_URL / SUPABASE_ANON_KEY."

        r = requests.post(
            f"{url.rstrip('/')}/auth/v1/resend",
            headers={
                "apikey": anon,
                "Authorization": f"Bearer {anon}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=12,
        )
        if 200 <= r.status_code < 300:
            return True, "Confirmation email resent. Check inbox/spam."
        return False, f"Resend failed (HTTP {r.status_code}). SDK error was: {sdk_err}"
    except Exception as e:
        return False, f"Resend failed. SDK error was: {sdk_err}. REST error: {type(e).__name__}"


# =============================================================================
# Main auth gate
# =============================================================================

def require_login() -> Optional[dict]:
    """
    Blocks app until authenticated. Returns user dict on success.
    """
    u = current_user()
    if u:
        return u

    st.title("8law Secure Access")

    site_key = _get_secret(TURNSTILE_SITE_KEY_KEY)
    secret_key = _get_secret(TURNSTILE_SECRET_KEY_KEY)

    if site_key and not secret_key:
        st.info(
            "Turnstile site key is set. For strongest protection, also set "
            "CLOUDFLARE_TURNSTILE_SECRET_KEY so the app can verify tokens server-side."
        )

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    # ----------------------------
    # Sign In
    # ----------------------------
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
                    if site_key:
                        ok, msg = _verify_turnstile_if_possible(token)
                        if not ok:
                            st.error(msg)
                            st.stop()

                    try:
                        sb = _supabase()
                        creds = {"email": email, "password": password}

                        # If Supabase captcha protection is enabled, pass captcha_token
                        if token:
                            creds["options"] = {"captcha_token": token}

                        resp = sb.auth.sign_in_with_password(creds)

                        user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
                        session = getattr(resp, "session", None) or (resp.get("session") if isinstance(resp, dict) else None)

                        if not user or not session:
                            st.error("Sign-in failed. Check credentials and email confirmation status.")
                        else:
                            access = getattr(session, "access_token", None)
                            refresh = getattr(session, "refresh_token", None)
                            _set_user_session(user if isinstance(user, dict) else user.__dict__, access, refresh)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Sign-in error: {type(e).__name__}: {e}")

        with col_b:
            if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
                if not email:
                    st.error("Enter your email above first.")
                else:
                    ok, msg = _resend_signup_confirmation(email)
                    (st.success if ok else st.error)(msg)

        st.markdown("---")
        st.caption(
            "If you get OTP expired errors, increase Email OTP Expiration in Supabase Auth settings, "
            "and ensure your Streamlit domain is in Supabase Redirect URLs / Additional Redirect URLs."
        )

    # ----------------------------
    # Create Account
    # ----------------------------
    with tab_signup:
        st.subheader("Create Account")
        email2 = st.text_input("Email", key="auth_signup_email")

        pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
        pw2 = st.text_input("Confirm password", type="password", key="auth_signup_pw2")

        policy = PasswordPolicy()
        score, unmet = _estimate_strength(pw1 or "", policy)

        st.caption("Password requirements (recommended):")
        st.write(f"- Minimum length: {policy.min_len} characters")
        st.write("- At least one uppercase letter")
        st.write("- At least one lowercase letter")
        st.write("- At least one number")
        st.write("- At least one symbol")

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
                st.stop()

            if pw1 != pw2:
                st.error("Passwords do not match.")
                st.stop()

            # Client-side guardrails (Supabase also enforces server-side)
            if len(pw1) < policy.min_len or unmet:
                st.error("Password does not meet the recommended requirements.")
                st.stop()

            if site_key:
                ok, msg = _verify_turnstile_if_possible(token2)
                if not ok:
                    st.error(msg)
                    st.stop()

            try:
                sb = _supabase()
                redirect_to = _auth_redirect_url()

                payload = {"email": email2, "password": pw1}
                options = {}
                if token2:
                    options["captcha_token"] = token2
                if redirect_to:
                    options["email_redirect_to"] = redirect_to
                if options:
                    payload["options"] = options

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
