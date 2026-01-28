import streamlit as st
import streamlit.components.v1 as components


# Load the frontend build (after running vite build)
import os
HCAPTCHA_COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "frontend", "dist")
HCAPTCHA_BUNDLE_PATH = os.path.join(HCAPTCHA_COMPONENT_PATH, "index.umd.cjs")

def hcaptcha(site_key: str, theme: str = "light", size: str = "normal") -> str:
    """
    Renders hCaptcha widget and returns the token if solved.
    """
    token = components.declare_component(
        "hcaptcha",
        path=HCAPTCHA_BUNDLE_PATH,
    )(
        siteKey=site_key,
        theme=theme,
        size=size,
        default=None,
        key="hcaptcha"
    )
    return token
