import streamlit as st
import hashlib

def check_password():
    """Returns True if the user had the correct password."""
    
    # 1. Check if we are already logged in
    if st.session_state.get("password_correct", False):
        return True

    # 2. Show Login Form
    st.title("🔒 8law Secure Access")
    password = st.text_input("Enter Password", type="password")
    
    if st.button("Login"):
        # SIMPLE SECURITY FOR DEMO:
        # In real life, we use st.secrets. Here we hardcode a hash for "admin123"
        # Hash for 'admin123' is: 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9
        
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        correct_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9" 
        
        if input_hash == correct_hash:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect Password")
            
    return False