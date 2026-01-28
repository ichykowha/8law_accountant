# app/audit_log_ui.py
import streamlit as st
from backend.audit_logger import get_audit_log

st.title("Audit Trail")

user_id = 1  # Demo user
logs = get_audit_log(user_id)

if not logs:
    st.info("No audit log entries yet.")
else:
    for entry in logs:
        st.write(f"{entry['timestamp']} | {entry['action']} | {entry['details']}")
    st.download_button("Export Log", str(logs), file_name="audit_log.txt")
