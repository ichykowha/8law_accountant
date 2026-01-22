# app/supabase_auth.py
import os
import streamlit as st
from supabase import create_client


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
        options={
            "headers": {"Authorization": f"Bearer {access_token}"},
        },
    )


def _app_url() -> str:
    """
    Base URL where your Streamlit app runs.
    Must be allow-listed in Supabase Auth -> URL Configuration -> Additional Redirect URLs.

    Local default: http://localhost:8501
    Streamlit Cloud: https://<your-app>.streamlit.app
    """
    return (os.getenv("APP_URL") or "http://localhost:8501").rstrip("/")


def _validate_password(password: str) -> str | None:
    """
    Return error string if invalid, else None.
    Adjust policy later as needed.
    """
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    return None


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

            # If "Confirm email" is ON and they haven't confirmed, session can be null.
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
            resp = sb.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"email_redirect_to": redirect_to},
                }
            )

            # With Confirm Email enabled, session is usually null until confirmation.
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
            # Resends a signup confirmation email (only works if a signup was initiated previously).
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
