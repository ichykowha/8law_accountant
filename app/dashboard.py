import streamlit as st
from pathlib import Path

# Custom CSS for bold, abstract, modern look
def load_custom_css():
    css_path = Path(__file__).parent / "dashboard_style.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_custom_css()

st.markdown("""
<div class="dashboard-header">
    <h1>🎨 8law Dashboard</h1>
    <p style="font-size:1.2em;">Welcome! Your workspace, inspired by bold colors and abstract lines.</p>
</div>
""", unsafe_allow_html=True)

# Abstract angled divider
st.markdown('<div class="angled-divider"></div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Recent Activity")
    st.info("No recent activity yet. Your actions will appear here.")
with col2:
    st.markdown("#### Document Status")
    st.success("All documents are up to date!")

# Analytics section
st.markdown('<div class="angled-divider small"></div>', unsafe_allow_html=True)
st.markdown("### Analytics Snapshot")
st.markdown("- **Tax Savings:** $0 (demo)")
st.markdown("- **Audit Risk:** Low (demo)")
st.markdown("- **Document Completeness:** 100% (demo)")

st.markdown('<div class="angled-divider"></div>', unsafe_allow_html=True)

st.markdown("<div class='footer'>Inspired by your art: bold, abstract, and unique.</div>", unsafe_allow_html=True)
