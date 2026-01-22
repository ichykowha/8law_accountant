# app/auth_supabase.py
import os
import re
import time
from typing import Optional, Dict, Any

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client


# -----------------------------
# Config / Secrets
# -----------------------------

def _secret(key: str, default=None):
    return os.getenv(key) or st.secrets.get(key, default)

SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_ANON_KEY = _secret("SUPABASE_ANON_KEY")

# Optional: show Turnstile widget in UI if provided
TURNSTILE_SITE_KEY = _secret("CLOUDFLARE_TURNSTILE_SITE_KEY", None)

# If you want to hard-disable captcha UI (even if site key exists), set to "0"
TURNSTILE_UI_ENABLED = str(_secret("TURNSTILE_UI_ENABLED", "1")).strip() != "0"


# -----------------------------
# Supabase client
# -----------------------------

@st.cache_resource(show_spinner=False)
def _sb():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# -----------------------------
# Password policy helpers
# -----------------------------

def password_requirements_text(min_len: int = 8) -> str:
    return (
        f"Password requirements:\n"
        f"- At least {min_len} characters\n"
        f"- At least 1 uppercase letter\n"
        f"- At least 1 lowercase letter\n"
        f"- At least 1 number\n"
        f"- At least 1 symbol (!@#$%^&* etc.)"
    )

def password_strength(password: str) -> int:
    """
    Returns 0..100 strength score (simple heuristic).
    """
    if not password:
        return 0

    score = 0
    length = len(password)

    # Length
    if length >= 8: score += 20
    if length >= 12: score += 15
    if length >= 16: score += 10

    # Variety
    if re.search(r"[A-Z]", password): score += 15
    if re.search(r"[a-z]", password): score += 15
    if re.search(r"\d", password): score += 15
    if re.search(r"[^\w\s]", password): score += 15

    # Penalize very common patterns
    if re.search(r"(password|1234|qwer|admin|letmein)", password.lower()):
        score -= 25

    return max(0, min(100, score))

def is_password_strong(password: str, min_len: int = 8) -> bool:
    if len(password) < min_len:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^\w\s]", password):
        return False
    return True


# -----------------------------
# Turnstile rendering (no custom component build)
# -----------------------------

def turnstile_widget(site_key: str, widget_id: str) -> None:
    """
    Renders Turnstile in the Streamlit page via HTML.
    The token is written into a hidden input, and user copies it to paste field.
    This avoids streamlit component API incompatibilities.
    """
    html = f"""
    <div>
      <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
      <div class="cf-turnstile" data-sitekey="{site_key}" data-theme="light" data-callback="onTurnstileSuccess"></div>
      <input type="text" id="{widget_id}" placeholder="Turnstile token will appear here" style="width:100%; margin-top:8px;" readonly />
      <script>
        function onTurnstileSuccess(token) {{
          const el = document.getElementById("{widget_id}");
          if (el) {{
            el.value = token;
          }}
        }}
      </script>
      <p style="font-size:12px; color:#666; margin-top:8px;">
        After verification, copy the token from the field above and paste it into the 'Captcha token' box.
      </p>
    </div>
    """
    components.html(html, height=260)

def maybe_collect_turnstile_token() -> Optional[str]:
    """
    Returns token if Turnstile is enabled/configured, else None.
    We render widget + text_input for token paste.
    """
    if not TURNSTILE_UI_ENABLED:
        return None
    if not TURNSTILE_SITE_KEY:
        return None

    st.markdown("### Human verification (Turnstile)")
    widget_id = f"ts_token_{int(time.time()*1000)}"
    turnstile_widget(TURNSTILE_SITE_KEY, widget_id=widget_id)
    token = st.text_input("Captcha token", help="Copy/paste the token from the Turnstile widget above.")
    token = (token or "").strip()
    return token or None


# -----------------------------
# Session state
# -----------------------------

def _set_session(user: Dict[str, Any], access_token: str, refresh_token: str):
    st.session_state["sb_user"] = user
    st.session_state["sb_access_token"] = access_token
    st.session_state["sb_refresh_token"] = refresh_token

def _clear_session():
    for k in ["sb_user", "sb_access_token", "sb_refresh_token"]:
        if k in st.session_state:
            del st.session_state[k]

def current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("sb_user")


# -----------------------------
# Supabase Auth Operations
# -----------------------------

def supabase_sign_in(email: str, password: str, captcha_token: Optional[str] = None) -> Dict[str, Any]:
    sb = _sb()

    # Supabase Python SDK versions differ; captcha support may not be exposed.
    # We'll attempt sign_in normally; if captcha is required server-side and missing,
    # Supabase will return an error we can display.
    resp = sb.auth.sign_in_with_password({"email": email, "password": password})
    # resp contains session + user
    session = getattr(resp, "session", None)
    user = getattr(resp, "user", None)
    if not session or not user:
        raise RuntimeError("Login failed (no session returned).")

    _set_session(user.model_dump(), session.access_token, session.refresh_token)
    return {"user": user.model_dump(), "session": {"access_token": session.access_token}}

def supabase_sign_up(email: str, password: str, captcha_token: Optional[str] = None) -> Dict[str, Any]:
    sb = _sb()
    # Note: captcha token may be required by your Supabase settings, but SDK may not pass it.
    # If your Supabase project enforces captcha at signup and SDK cannot pass it, you’ll see an error.
    resp = sb.auth.sign_up({"email": email, "password": password})
    user = getattr(resp, "user", None)
    if not user:
        raise RuntimeError("Signup failed (no user returned).")
    return {"user": user.model_dump()}

def supabase_resend_confirmation(email: str) -> None:
    sb = _sb()
    # Resend signup confirmation email
    sb.auth.resend({"type": "signup", "email": email})

def supabase_send_password_reset(email: str) -> None:
    sb = _sb()
    sb.auth.reset_password_email(email)

def supabase_sign_out() -> None:
    sb = _sb()
    try:
        sb.auth.sign_out()
    except Exception:
        # Even if token is already invalid, we still clear local session
        pass
    _clear_session()


# -----------------------------
# UI: Auth Gate
# -----------------------------

def _auth_tabs():
    tab_login, tab_signup, tab_reset = st.tabs(["Sign in", "Create account", "Forgot password"])
    return tab_login, tab_signup, tab_reset

def _render_login():
    st.subheader("Sign in")

    email = st.text_input("Email", key="auth_login_email")
    password = st.text_input("Password", type="password", key="auth_login_password")

    captcha_token = maybe_collect_turnstile_token()

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Sign In", type="primary", key="auth_login_btn"):
            if not email or not password:
                st.error("Email and password are required.")
                return
            try:
                supabase_sign_in(email=email.strip(), password=password, captcha_token=captcha_token)
                st.success("Signed in.")
                st.rerun()
            except Exception as e:
                st.error(f"Sign in failed: {e}")

    with col2:
        if st.button("Resend confirmation email", key="auth_resend_confirm_btn"):
            if not email:
                st.error("Enter your email above first.")
                return
            try:
                supabase_resend_confirmation(email=email.strip())
                st.info("If that email exists, a new confirmation email has been sent.")
            except Exception as e:
                st.error(f"Resend failed: {e}")

def _render_signup():
    st.subheader("Create account")

    email = st.text_input("Email", key="auth_signup_email")

    st.caption(password_requirements_text(min_len=8))
    pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
    strength = password_strength(pw1)
    st.progress(strength)
    st.caption(f"Password strength: {strength}/100")

    pw2 = st.text_input("Repeat password", type="password", key="auth_signup_pw2")

    captcha_token = maybe_collect_turnstile_token()

    if st.button("Create account", type="primary", key="auth_signup_btn"):
        if not email or not pw1 or not pw2:
            st.error("Email and both password fields are required.")
            return
        if pw1 != pw2:
            st.error("Passwords do not match.")
            return
        if not is_password_strong(pw1, min_len=8):
            st.error("Password does not meet requirements.")
            return

        try:
            supabase_sign_up(email=email.strip(), password=pw1, captcha_token=captcha_token)
            st.success("Account created. Check your email to confirm your account, then return to sign in.")
        except Exception as e:
            st.error(f"Signup failed: {e}")

def _render_reset():
    st.subheader("Reset password")
    email = st.text_input("Email", key="auth_reset_email")

    if st.button("Send password reset email", type="primary", key="auth_reset_btn"):
        if not email:
            st.error("Email is required.")
            return
        try:
            supabase_send_password_reset(email=email.strip())
            st.info("If that email exists, a password reset email has been sent.")
        except Exception as e:
            st.error(f"Reset failed: {e}")

def require_login() -> Optional[Dict[str, Any]]:
    """
    Gate for the app. If logged in, returns user dict.
    Otherwise renders auth UI and returns None.
    """
    user = current_user()
    if user:
        with st.sidebar:
            st.success(f"Signed in: {user.get('email', 'user')}")
            if st.button("Sign out", key="auth_sign_out_btn"):
                supabase_sign_out()
                st.rerun()
        return user

    st.title("8law Secure Access")
    st.caption("Sign in with your account. This app uses Supabase Auth for multi-tenant security (RLS-ready).")

    tab_login, tab_signup, tab_reset = _auth_tabs()
    with tab_login:
        _render_login()
    with tab_signup:
        _render_signup()
    with tab_reset:
        _render_reset()

    return None
