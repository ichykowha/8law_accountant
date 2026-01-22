# app/auth_supabase.py
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import streamlit as st
from supabase import create_client


# -----------------------------
# Supabase client
# -----------------------------
@st.cache_resource
def _get_supabase():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL and/or SUPABASE_ANON_KEY in Streamlit secrets.")
    return create_client(url, key)


# -----------------------------
# Turnstile (no extra deps)
# Uses Streamlit Components v2 JS-only component
# -----------------------------
def turnstile_token(site_key: str, *, key: str = "turnstile") -> Optional[str]:
    """
    Renders Cloudflare Turnstile and returns a token string when solved.
    Requires CLOUDFLARE_TURNSTILE_SITE_KEY in secrets.
    """
    try:
        # Streamlit Components v2 (Streamlit >= 1.49)
        import streamlit.components.v2 as components  # type: ignore
    except Exception:
        st.warning("Turnstile requires Streamlit Components v2 (Streamlit >= 1.49).")
        return None

    js = r"""
// Turnstile JS-only component for Streamlit components.v2.component
// Receives site key in data.siteKey
// Returns { token: "..." } via setComponentValue

const SITE_KEY = data.siteKey;

function sendValue(obj) {
  setComponentValue(obj);
}

function loadScriptOnce(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) { resolve(); return; }
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load Turnstile script."));
    document.head.appendChild(s);
  });
}

async function render() {
  const containerId = "cf-turnstile-container";
  let container = document.getElementById(containerId);
  if (!container) {
    container = document.createElement("div");
    container.id = containerId;
    container.style.display = "flex";
    container.style.justifyContent = "center";
    container.style.margin = "8px 0";
    document.body.appendChild(container);
  } else {
    container.innerHTML = "";
  }

  await loadScriptOnce("https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit");

  // Turnstile attaches to window.turnstile
  if (!window.turnstile) {
    throw new Error("Turnstile did not initialize (window.turnstile missing).");
  }

  window.turnstile.render(container, {
    sitekey: SITE_KEY,
    callback: function(token) {
      sendValue({ token: token });
    },
    "expired-callback": function() {
      sendValue({ token: null, expired: true });
    },
    "error-callback": function() {
      sendValue({ token: null, error: true });
    }
  });
}

render().catch(err => {
  sendValue({ token: null, error: true, message: String(err) });
});
"""

    result = components.component(
        name="turnstile_component",
        js=js,
        data={"siteKey": site_key},
        key=key,
        isolate_styles=False,  # Turnstile script prefers normal DOM
    )

    if isinstance(result, dict):
        return result.get("token")
    return None


# -----------------------------
# Password policy + strength
# -----------------------------
def _password_policy() -> Dict[str, Any]:
    # Keep this aligned with your Supabase settings.
    # You can tighten later; do not weaken below recommended defaults.
    return {
        "min_len": 12,              # recommended (Supabase min recommended >= 8) :contentReference[oaicite:1]{index=1}
        "require_upper": True,
        "require_lower": True,
        "require_digit": True,
        "require_symbol": True,
        "max_len": 128,
    }


def validate_password(pw: str) -> Tuple[bool, str]:
    pol = _password_policy()
    if not pw or len(pw) < pol["min_len"]:
        return False, f"Password must be at least {pol['min_len']} characters."
    if len(pw) > pol["max_len"]:
        return False, f"Password must be at most {pol['max_len']} characters."
    if pol["require_upper"] and not re.search(r"[A-Z]", pw):
        return False, "Password must include at least one uppercase letter."
    if pol["require_lower"] and not re.search(r"[a-z]", pw):
        return False, "Password must include at least one lowercase letter."
    if pol["require_digit"] and not re.search(r"[0-9]", pw):
        return False, "Password must include at least one number."
    if pol["require_symbol"] and not re.search(r"[^A-Za-z0-9]", pw):
        return False, "Password must include at least one symbol."
    return True, "OK"


def password_strength(pw: str) -> Tuple[int, str]:
    """
    Lightweight heuristic strength meter (no extra dependency).
    Returns (0..100, label).
    """
    if not pw:
        return 0, "Empty"

    score = 0
    length = len(pw)

    # length scoring
    if length >= 12:
        score += 35
    elif length >= 10:
        score += 25
    elif length >= 8:
        score += 15
    else:
        score += 5

    # variety
    score += 15 if re.search(r"[A-Z]", pw) else 0
    score += 15 if re.search(r"[a-z]", pw) else 0
    score += 15 if re.search(r"[0-9]", pw) else 0
    score += 20 if re.search(r"[^A-Za-z0-9]", pw) else 0

    # simple penalties
    if re.search(r"(.)\1\1", pw):
        score -= 10
    if re.search(r"password|qwerty|letmein|123456|welcome", pw.lower()):
        score -= 25

    score = max(0, min(100, score))
    if score >= 80:
        return score, "Strong"
    if score >= 60:
        return score, "Good"
    if score >= 40:
        return score, "Fair"
    return score, "Weak"


# -----------------------------
# Session helpers
# -----------------------------
def _store_session(auth_response: Any) -> None:
    """
    Stores session tokens in st.session_state so they survive reruns.
    """
    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)

    if session:
        st.session_state["sb_access_token"] = getattr(session, "access_token", None)
        st.session_state["sb_refresh_token"] = getattr(session, "refresh_token", None)
    if user:
        st.session_state["sb_user_id"] = getattr(user, "id", None)
        st.session_state["sb_user_email"] = getattr(user, "email", None)


def supabase_restore_session() -> None:
    """
    If tokens exist in session_state, set them on the supabase client for RLS-backed calls.
    """
    sb = _get_supabase()
    at = st.session_state.get("sb_access_token")
    rt = st.session_state.get("sb_refresh_token")
    if at and rt:
        try:
            sb.auth.set_session(at, rt)
        except Exception:
            # If session is invalid/expired, clear
            for k in ["sb_access_token", "sb_refresh_token", "sb_user_id", "sb_user_email"]:
                st.session_state.pop(k, None)


def supabase_logout() -> None:
    sb = _get_supabase()
    try:
        sb.auth.sign_out()
    except Exception:
        pass
    for k in ["sb_access_token", "sb_refresh_token", "sb_user_id", "sb_user_email"]:
        st.session_state.pop(k, None)


def get_current_user() -> Optional[Dict[str, str]]:
    user_id = st.session_state.get("sb_user_id")
    email = st.session_state.get("sb_user_email")
    if user_id and email:
        return {"id": user_id, "email": email}
    return None


# -----------------------------
# Main gate: require_login()
# -----------------------------
def require_login() -> Optional[Dict[str, str]]:
    """
    Call this near the start of your Streamlit app.
    If logged in, returns {"id": ..., "email": ...}.
    If not logged in, renders auth UI and returns None.
    """
    supabase_restore_session()
    user = get_current_user()
    if user:
        return user

    st.title("8law — Secure Sign In")
    st.caption("Sign in is required before you can access client files and ingestion features.")

    tabs = st.tabs(["Sign In", "Create Account", "Resend Confirmation"])

    site_key = st.secrets.get("CLOUDFLARE_TURNSTILE_SITE_KEY")

    # --- Sign In ---
    with tabs[0]:
        email = st.text_input("Email", key="auth_login_email")
        password = st.text_input("Password", type="password", key="auth_login_password")

        token = None
        if site_key:
            st.write("Human verification:")
            token = turnstile_token(site_key, key="turnstile_login")

        if st.button("Sign In", type="primary", key="auth_login_btn"):
            if not email or not password:
                st.error("Email and password are required.")
                st.stop()
            if site_key and not token:
                st.error("Please complete the human verification.")
                st.stop()

            try:
                sb = _get_supabase()
                resp = sb.auth.sign_in_with_password(
                    {
                        "email": email,
                        "password": password,
                        "options": {"captcha_token": token} if token else {},
                    }
                )
                _store_session(resp)
                st.success("Signed in successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"Sign in failed: {type(e).__name__}: {e}")

    # --- Create Account ---
    with tabs[1]:
        email2 = st.text_input("Email", key="auth_signup_email")
        pw1 = st.text_input("Password", type="password", key="auth_signup_pw1")
        pw2 = st.text_input("Confirm Password", type="password", key="auth_signup_pw2")

        score, label = password_strength(pw1)
        st.progress(score / 100.0)
        st.caption(f"Strength: {label} ({score}/100)")

        pol = _password_policy()
        st.caption(
            f"Password rules: min {pol['min_len']} chars, uppercase, lowercase, number, symbol."
        )

        token2 = None
        if site_key:
            st.write("Human verification:")
            token2 = turnstile_token(site_key, key="turnstile_signup")

        if st.button("Create Account", type="primary", key="auth_signup_btn"):
            if not email2:
                st.error("Email is required.")
                st.stop()
            if pw1 != pw2:
                st.error("Passwords do not match.")
                st.stop()
            ok, msg = validate_password(pw1)
            if not ok:
                st.error(msg)
                st.stop()
            if site_key and not token2:
                st.error("Please complete the human verification.")
                st.stop()

            try:
                sb = _get_supabase()
                resp = sb.auth.sign_up(
                    {
                        "email": email2,
                        "password": pw1,
                        "options": {"captcha_token": token2} if token2 else {},
                    }
                )
                # With "Confirm email" enabled, session is typically null until verified. :contentReference[oaicite:2]{index=2}
                st.success("Account created. Check your email to confirm, then sign in.")
            except Exception as e:
                st.error(f"Sign up failed: {type(e).__name__}: {e}")

    # --- Resend Confirmation ---
    with tabs[2]:
        email3 = st.text_input("Email", key="auth_resend_email")
        token3 = None
        if site_key:
            st.write("Human verification:")
            token3 = turnstile_token(site_key, key="turnstile_resend")

        if st.button("Resend Confirmation Email", key="auth_resend_btn"):
            if not email3:
                st.error("Email is required.")
                st.stop()
            if site_key and not token3:
                st.error("Please complete the human verification.")
                st.stop()

            try:
                sb = _get_supabase()
                # Resend is supported in Supabase Auth clients; type 'signup' is commonly used. :contentReference[oaicite:3]{index=3}
                sb.auth.resend({"type": "signup", "email": email3})
                st.success("If that account exists and is unconfirmed, a confirmation email has been resent.")
            except Exception as e:
                st.error(f"Resend failed: {type(e).__name__}: {e}")

    st.info(
        "If your confirmation link opens localhost:3000 or shows otp_expired, fix Supabase Auth URL Configuration "
        "(Site URL + Additional Redirect URLs) to match your Streamlit app URL."
    )

    return None
