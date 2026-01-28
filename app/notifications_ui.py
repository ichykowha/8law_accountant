# Add this to your dashboard or sidebar UI
import streamlit as st
from backend.notifications import get_user_notifications, mark_all_read

# Simulate current user (replace with real user/session)
user_id = "demo_user"

st.sidebar.markdown("### 🔔 Notifications")
notifications = get_user_notifications(user_id)

if notifications:
    unread = [n for n in notifications if not n["read"]]
    for n in unread:
        st.sidebar.info(f"{n['message']} ({n['timestamp'][:16].replace('T',' ')})")
    if st.sidebar.button("Mark all as read"):
        mark_all_read(user_id)
        st.experimental_rerun()
else:
    st.sidebar.success("No new notifications.")
