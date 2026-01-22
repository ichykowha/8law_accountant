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

    # supabase-py allows passing extra headers
    return create_client(
        url,
        key,
        options={
            "headers": {
                "Authorization": f"Bearer {access_token}",
            }
        },
    )


def is_authenticated() -> bool:
    return bool(st.session_state.get("sb_access_token") and st.session_state.get("sb_user_id"))


def get_authed_client():
    """
    Returns an authed supabase client (RLS enforced) or raises.
    """
    token = st.session_state.get("sb_access_token")
    if not token:
        raise RuntimeError("Not authenticated (missing sb_access_token).")
    return _get_supabase_authed(token)


def sign_out():
    st.session_state.pop("sb_access_token", None)
    st.session_state.pop("sb_refresh_token", None)
    st.session_state.pop("sb_user_id", None)
    st.session_state.pop("sb_user_email", None)
    # Also clear client selection on logout
    st.session_state.pop("current_client_id", None)
    st.session_state.pop("current_client_name", None)
    st.rerun()


def _login_form():
    st.subheader("Sign in")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    submitted = st.button("Sign in", type="primary")

    if submitted:
        sb = _get_supabase_public()
        try:
            resp = sb.auth.sign_in_with_password({"email": email, "password": password})
            session = resp.session
            user = resp.user
            if not session or not user:
                st.error("Sign in failed: no session returned.")
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
    password = st.text_input("Password", type="password", key="signup_password")
    submitted = st.button("Create account", type="secondary")

    if submitted:
        sb = _get_supabase_public()
        try:
            resp = sb.auth.sign_up({"email": email, "password": password})
            # Depending on Supabase settings, user may need email confirmation.
            st.success("Account created. If email confirmation is enabled, check your inbox, then sign in.")
        except Exception as e:
            st.error(f"Sign up failed: {type(e).__name__}: {e}")


def require_auth():
    """
    Global auth guard. If not authenticated, show auth UI and stop execution.
    """
    if is_authenticated():
        return

    st.title("8law Secure Sign-in")
    st.caption("Sign in with Supabase Auth. Tenant isolation is enforced by Postgres RLS.")

    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        _login_form()
    with tab2:
        _signup_form()

    st.stop()
