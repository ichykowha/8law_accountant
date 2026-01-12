import streamlit as st
import os
import sys

# Path Setup to ensure we can find the backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from controller import PowerhouseAccountant

# --- 1. CONFIG ---
st.set_page_config(page_title="8law Accountant", page_icon="💰", layout="wide")

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stTextInput > div > div > input { border: 2px solid #2c3e50; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INITIALIZE SYSTEM ---
if 'accountant' not in st.session_state:
    st.session_state.accountant = PowerhouseAccountant()

# Initialize Pinecone Memory
if 'vector_db' not in st.session_state:
    st.session_state.vector_db = None 

# --- 4. SIDEBAR (The "Office") ---
with st.sidebar:
    st.header("📂 Document Upload")
    uploaded_file = st.file_uploader("Drop Bank Statements (PDF)", type="pdf")
    
    if uploaded_file:
        with st.spinner("Reading document..."):
            # Save temp file
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Process
            st.session_state.accountant.process_document(temp_path)
            st.success("Saved to Pinecone Memory 🧠")
            os.remove(temp_path)

    st.divider()
    st.markdown("### 📊 Status")
    st.metric(label="System Status", value="Online", delta="Ready")

# --- 5. MAIN FLOOR (The Chat) ---
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
    # Show User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Get AI Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_data = st.session_state.accountant.process_input(prompt)
            answer = response_data["answer"]
            
            st.markdown(answer)
            
            # Show Reasoning (The "Audit Trail")
            with st.expander("View Logic & Reasoning"):
                st.write(response_data["reasoning"])
                
    st.session_state.messages.append({"role": "assistant", "content": answer})
    
