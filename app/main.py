import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
import sys

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from controller import PowerhouseAccountant

# --- 1. CONFIG ---
st.set_page_config(page_title="8law Accountant", page_icon="💰", layout="wide")

# --- 2. LOAD CONFIGURATION ---
# We look for config.yaml in the main directory
config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

try:
    with open(config_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("⚠️ Security Error: config.yaml not found.")
    st.stop()

# --- 3. AUTHENTICATION SETUP ---
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# This draws the login widget
# We ask it to return the status (True/False)
if st.session_state.get("authentication_status") is None:
    # First run, show login
    authenticator.login()
elif st.session_state["authentication_status"] is False:
    # Failed run
    authenticator.login()
    st.error('Username/password is incorrect')

# --- 4. THE GATEKEEPER ---
if st.session_state["authentication_status"]:
    # === ONLY RUN THIS IF LOGGED IN ===
    
    # Logout Button (Sidebar)
    with st.sidebar:
        st.write(f"Welcome, *{st.session_state['name']}*")
        authenticator.logout('Logout', 'main')
        st.divider()

    # --- INITIALIZE SYSTEM ---
    if 'accountant' not in st.session_state:
        st.session_state.accountant = PowerhouseAccountant()
    if 'vector_db' not in st.session_state:
        st.session_state.vector_db = None 

    # --- SIDEBAR WORKSPACE ---
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

    # --- MAIN FLOOR ---
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

# === END OF SECURE ZONE ===
