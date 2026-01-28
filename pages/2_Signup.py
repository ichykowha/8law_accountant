import app.auth_supabase as auth

# This page will show the signup form directly

def main():
    # Force the signup tab to be active
    import streamlit as st
    st.session_state["auth_active_tab"] = "signup"
    auth.require_login()

if __name__ == "__main__":
    main()
