# app/preflight.py
import os
import streamlit as st

REQUIRED_AT_BOOT = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
]

# Strongly recommended for correct email confirmation redirects (avoid localhost / otp_expired confusion)
RECOMMENDED_AT_BOOT = [
    "AUTH_REDIRECT_URL",
]

# Turnstile (Cloudflare) - optional unless you enabled Captcha protection in Supabase Auth
TURNSTILE_KEYS = [
    "CLOUDFLARE_TURNSTILE_SITE_KEY",
    "CLOUDFLARE_TURNSTILE_SECRET_KEY",
]

OPTIONAL_FEATURE_SECRETS = [
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
]


def _get_secret(key: str):
    v = os.getenv(key)
    if v:
        return v
    try:
        return st.secrets.get(key, None)
    except Exception:
        return None


def _missing(keys):
    return [k for k in keys if not _get_secret(k)]


def run():
    # --- Hard requirements ---
    missing_boot = _missing(REQUIRED_AT_BOOT)
    if missing_boot:
        st.error(
            "Missing required secrets: " + ", ".join(missing_boot) + "\n\n"
            "Add them in Streamlit Cloud → App Settings → Secrets.\n\n"
            "Until these are set, authentication and database access will not work."
        )
        st.stop()

    # --- Recommended (do not stop) ---
    missing_recommended = _missing(RECOMMENDED_AT_BOOT)
    if missing_recommended:
        st.warning(
            "Recommended secret not set: AUTH_REDIRECT_URL\n\n"
            "Why this matters:\n"
            "- Supabase email confirmation / recovery links should redirect back to your Streamlit app.\n"
            "- If missing or misconfigured, users often see links pointing to localhost (or OTP expired flows).\n\n"
            "Set AUTH_REDIRECT_URL to your deployed app URL, for example:\n"
            "  https://8lawaccountant-xxxxx.streamlit.app"
        )

    # --- Turnstile (Captcha) guidance (do not stop) ---
    site_key = _get_secret("CLOUDFLARE_TURNSTILE_SITE_KEY")
    secret_key = _get_secret("CLOUDFLARE_TURNSTILE_SECRET_KEY")

    if site_key and not secret_key:
        st.info(
            "Turnstile site key is set, but CLOUDFLARE_TURNSTILE_SECRET_KEY is missing.\n\n"
            "The app can still render the Turnstile widget, but server-side verification is weaker.\n"
            "For best security, set both the site key and the secret key in Streamlit secrets."
        )

    if (not site_key) and (not secret_key):
        st.info(
            "Turnstile is not configured in Streamlit secrets.\n\n"
            "If Supabase Auth → Attack Protection → Captcha is enabled, you should set:\n"
            "- CLOUDFLARE_TURNSTILE_SITE_KEY\n"
            "- CLOUDFLARE_TURNSTILE_SECRET_KEY\n\n"
            "If Captcha is disabled in Supabase, you can ignore this."
        )

    # --- Optional feature secrets (do not stop) ---
    missing_optional = _missing(OPTIONAL_FEATURE_SECRETS)
    if missing_optional:
        st.warning(
            "Optional features disabled until secrets are set: "
            + ", ".join(missing_optional)
            + "\n\nEmbeddings / Pinecone will not work until these are provided."
        )
