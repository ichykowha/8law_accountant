# Example Streamlit role check usage
from backend.rbac import get_user_role, has_permission
import streamlit as st

# Simulate current user (replace with real user/session)
user_id = "1"  # admin
role = get_user_role(user_id)
st.sidebar.markdown(f"**Role:** {role}")

if has_permission(user_id, "view_users"):
    st.sidebar.info("You can view users.")
if has_permission(user_id, "edit_users"):
    st.sidebar.info("You can edit users.")
if has_permission(user_id, "manage_settings"):
    st.sidebar.info("You can manage settings.")
