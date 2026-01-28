import streamlit as st
from pathlib import Path

def load_admin_css():
    css_path = Path(__file__).parent / "dashboard_style.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_admin_css()

st.markdown("""
<div class="dashboard-header">
    <h1>🛠️ Admin Panel</h1>
    <p style='font-size:1.2em;'>Manage users, view logs, and monitor system health.</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="angled-divider"></div>', unsafe_allow_html=True)

# Tabs for admin features
tab1, tab2, tab3 = st.tabs(["Users", "Logs", "System Health"])

with tab1:
    st.markdown("#### User Management")
    st.info("User list and management actions will appear here.")

with tab2:
    st.markdown("#### Logs")
    st.info("System and audit logs will appear here.")

with tab3:
    st.markdown("#### System Health")
    st.info("Health checks and metrics will appear here.")

st.markdown('<div class="angled-divider"></div>', unsafe_allow_html=True)
