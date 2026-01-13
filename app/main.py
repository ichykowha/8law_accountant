import streamlit as st
import streamlit_authenticator as stauth
import os
import sys

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from controller import PowerhouseAccountant

# --- 1. CONFIG ---
st.set_page_config(page_title="8law Accountant", page_icon="💰", layout="wide")

# --- 2. AUTHENTICATION (FROM SECRETS) ---
# We load the config directly from the secure vault
try:
    config = st.secrets
except FileNotFoundError:
    st.error("⚠️ Security Error: Secrets not found.")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Login Widget
if st.session_state.get("authentication_status") is None:
    authenticator.login()
elif st.session_state["authentication_status"] is False:
    authenticator.login()
    st.error('Username/password is incorrect')

# --- 3. THE SECURE APP ---
if st.session_state["authentication_status"]:
    
    # Sidebar Logout
    with st.sidebar:
        st.write(f"Welcome, *{st.session_state['name']}*")
        authenticator.logout('Logout', 'main')
        st.divider()

    # Initialize System
    if 'accountant' not in st.session_state:
        st.session_state.accountant = PowerhouseAccountant()
    if 'vector_db' not in st.session_state:
        st.session_state.vector_db = None 

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📂 Document Upload")
        uploaded_file = st.file_uploader("Drop Bank Statements (PDF)", type="pdf")
        
        if uploaded_file:
            with st.spinner("Reading document..."):
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                st.session_state.accountant.process_document(temp_path)
                st.success("Saved to Pinecone Memory 🧠")
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        st.divider()
        st.metric(label="System Status", value="Online", delta="Gemini 2.5 Pro")

    # --- CHAT INTERFACE ---
    st.title("8law Super Accountant")
    st.markdown("#### *Industry Grade Financial Intelligence*")

    # Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User Input
    if prompt := st.chat_input("Ask about your finances..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_data = st.session_state.accountant.process_input(prompt)
                
                answer = response_data.get("answer", "⚠️ No answer provided.")
                reasoning = response_data.get("reasoning", [])
                
                st.markdown(answer)
                
                with st.expander("View Logic & Reasoning"):
                    st.write(reasoning)
                    
        st.session_state.messages.append({"role": "assistant", "content": answer})
