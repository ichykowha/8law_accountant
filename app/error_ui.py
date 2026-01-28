# User-friendly error display for Streamlit
import streamlit as st
from backend.error_handler import log_error

def show_error_ui(error_msg: str, context: str = ""): 
    st.error(f"Oops! Something went wrong.\n\n**Error:** {error_msg}")
    log_error(error_msg, {"context": context})

# Example usage (uncomment to test)
# try:
#     1/0
# except Exception as e:
#     show_error_ui(str(e), context="dashboard")
