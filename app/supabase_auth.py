# app/supabase_auth.py
import os
import re
import streamlit as st
from supabase import create_client


# -----------------------------
# Supabase client helpers
# -----------------------------
def _get_supabase_public():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def _get_supabase_authed(access_token: str):
    """
    Create a Supabase client that enforces RLS by authenticating as the user.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")

    return create_client(
        url,
        key,
        options={"headers": {"Authorization": f"Bearer {access_token}"}},
    )


def _app_url() -> str:
    """
    Base URL where your Streamlit app runs.
    Must be allow-listed in Supabase Auth -> URL Configuration -> Additional Redirect URLs.
    """
    return (os.getenv("APP_URL") or "http://localhost:8501").rstrip("/")


# -----------------------------
# Password policy + strength
# -----------------------------
PASSWORD_MIN_LEN = 10

_RX_LOWER = re.compile(r"[a-z]")
_RX_UPPER = re.compile(r"[A-Z]")
_RX_DIGIT = re.compile(r"\d")
_RX_SPECIAL = re.compile(r"""[ !"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~\\]""")  # broad ASCII specials


def _password_requirements(password: str) -> dict:
    pw = password or ""
    return {
        "min_len": len(pw) >= PASSWORD_MIN_LEN,
        "lower": bool(_RX_LOWER.search(pw)),
        "upper": bool(_RX_UPPER.search(pw)),
        "digit": bool(_RX_DIGIT.search(pw)),
        "special": bool(_RX_SPECIAL.search(pw)),
    }


def _password_strength(password: str) -> tuple[int, str]:
    """
    Returns (score_0_to_100, label).
    This is a heuristic meter (no external deps).
    """
    req = _password_requirements(password)
    score = 0

    # Base scoring
    if req["min_len"]:
        score += 25
    if req["lower"]:
        score += 15
    if req["upper"]:
        score += 15
    if req["digit"]:
        score += 15
    if req["special"]:
        score += 15

    # Bonus for length beyond minimum
    extra = max(0, len(password or "") - PASSWORD_MIN_LEN)
    score += min(15, extra)  # up to +15 bonus

    score = max(0, min(100, score))

    if score < 35:
        label = "Weak"
    elif score < 60:
        label = "Fair"
    elif score < 80:
        label = "Good"
    else:
        label = "Strong"

    return score, label


def _validate_password(password: str) -> str | None:
    """
    Returns error string if invalid, else None.
    """
    req = _password_requirements(password)
    if all(req.values()):
        return None

    missing = []
    if not req["min_len"]:
        missing.append(f"at least {PASSWORD_MIN_LEN} characters")
    if not req["lower"]:
        missing.append("a lowercase letter")
    if not req["upper"]:
        missing.append("an uppercase letter")
    if not req["digit"]:
        missing.append("a number")
    if not req["special"]:
        missing.append("a special character")

    return "Password must contain " + ", ".join(missing) + "."


def _render_password_rules(password: str):
    """
    Live checklist + strength bar.
    """
    req = _password_requirements(password)
    score, label = _password_strength(password)

    st.caption("Password requirements:")
    st.write(("✅" if req["min_len"] else "❌") + f" At least {PASSWORD_MIN_LEN} characters")
    st.write(("✅" if req["lower"] else "❌") + " Contains a lowercase letter (a-z)")
    st.write(("✅" if req["upper"] else "❌") + " Contains an uppercase letter (A-Z)")
    st.write(("✅" if req["digit"] else "❌") + " Contains a number (0-9)")
    st.write(("✅" if req["special"] else "❌") + " Contains a special character (e.g., ! @ # $ %)")

    st.caption(f"Strength: {label} ({score}/100)")
    st.progress(score)


# -----------------------------
# Session / auth state
# -----------------------------
def is_authenticated() -> bool:
    return bool(st.session_state.get("sb_access_token") and st.session_state.get("sb_user_id"))


def get_authed_client():
    token = st.session_state.get("sb_access_token")
    if not token:
        raise RuntimeError("Not authenticated (missing sb_access_token).")
    return _get_supabase_authed(token)


def sign_out():
    for k in [
        "sb_access_token",
        "sb_refresh_token",
        "sb_user_id",
        "sb_user_email",
        "current_client_id",
        "current_client_name",
    ]:
        st.session_state.pop(k, None)
    st.rerun()


# -----------------------------
# UI forms
# -----------------------------
def _login_form():
    st.subheader("Sign in")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    submitted = st.button("Sign in", type="primary")

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
            return

        sb = _get_supabase_public()
        try:
            resp = sb.auth.sign_in_with_password({"email": email, "password": password})
            session = resp.session
            user = resp.user

            if not session:
                st.error(
                    "Sign-in did not return a session. If you just signed up, you may need to confirm your email first. "
                    "Use the 'Resend confirmation' tab if needed."
                )
                return
            if not user:
                st.error("Sign in failed: no user returned.")
                return

            st.session_state["sb_access_token"] = session.access_token
            st.session_state["sb_refresh_token"] = session.refresh_token
            st.session_state["sb_user_id"] = user.id
            st.session_state["sb_user_email"] = user.email

            st.success("Signed in.")
            st.rerun()

        except Exception as e:
            st.error(f"Sign in failed: {type(e).__name__}: {e}")


def _signup_form():
    st.subheader("Create account")
    email = st.text_input("Email", key="signup_email")

    col1, col2 = st.columns(2)
    with col1:
        password = st.text_input("Password", type="password", key="signup_password")
    with col2:
        password2 = st.text_input("Confirm password", type="password", key="signup_password2")

    # Live rules + strength meter
    _render_password_rules(password)

    submitted = st.button("Create account", type="secondary")

    if submitted:
        if not email:
            st.error("Email is required.")
            return

        policy_err = _validate_password(password)
        if policy_err:
            st.error(policy_err)
            return

        if password != password2:
            st.error("Passwords do not match. Please type them exactly the same.")
            return

        sb = _get_supabase_public()
        redirect_to = _app_url()

        try:
            sb.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"email_redirect_to": redirect_to},
                }
            )
            st.success(
                "Account created. Check your email for a confirmation link. "
                f"After confirming, return to {redirect_to} and sign in."
            )
        except Exception as e:
            st.error(f"Sign up failed: {type(e).__name__}: {e}")


def _resend_confirmation_form():
    st.subheader("Resend confirmation email")
    st.caption("Use this if the user never received the email or the link expired.")

    email = st.text_input("Email", key="resend_email")
    submitted = st.button("Resend confirmation", type="primary")

    if submitted:
        if not email:
            st.error("Email is required.")
            return

        sb = _get_supabase_public()
        redirect_to = _app_url()

        try:
            sb.auth.resend(
                {
                    "type": "signup",
                    "email": email,
                    "options": {"email_redirect_to": redirect_to},
                }
            )
            st.success(
                "If that email exists and is pending confirmation, a new confirmation link has been sent. "
                "Check inbox and spam/junk. Click the newest link."
            )
        except Exception as e:
            st.error(f"Resend failed: {type(e).__name__}: {e}")


def require_auth():
    if is_authenticated():
        return

    st.title("8law Secure Sign-in")
    st.caption("Sign in with Supabase Auth. Tenant isolation should be enforced by Postgres RLS.")

    tab1, tab2, tab3 = st.tabs(["Sign in", "Create account", "Resend confirmation"])
    with tab1:
        _login_form()
    with tab2:
        _signup_form()
    with tab3:
        _resend_confirmation_form()

    st.stop()
