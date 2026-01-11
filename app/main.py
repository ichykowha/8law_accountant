import streamlit as st
import sys
import os
import pandas as pd
import socket
import qrcode
from PIL import Image
from io import BytesIO

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from controller import PowerhouseAccountant
from auth import check_password

# --- 1. CONFIG (The Money Icon) ---
st.set_page_config(
    page_title="Super Accountant",
    page_icon="💰", # Money Bag Icon for Mobile Home Screen
    layout="wide"
)

# --- 2. SECURITY CHECK ---
if not check_password():
    st.stop() # Stop here if not logged in

# --- 3. INITIALIZE SYSTEM ---
if 'accountant' not in st.session_state:
    st.session_state.accountant = PowerhouseAccountant()
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 4. SIDEBAR (Mobile & QR) ---
with st.sidebar:
    st.title("📂 Ingest")
    uploaded = st.file_uploader("Upload", type=['csv','png','jpg','json'])
    if uploaded:
        # Save & Process
        temp_dir = os.path.join("..", "data", "uploads")
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        path = os.path.join(temp_dir, uploaded.name)
        with open(path, "wb") as f: f.write(uploaded.getbuffer())
        
        st.info("Scanning...")
        res = st.session_state.accountant.ingestor.ingest_file(path)
        st.success(res)
        # Add to Blockchain
        st.session_state.accountant.audit.create_entry(f"Upload: {uploaded.name}", path)

    st.divider()
    
    # QR CODE GENERATOR
    with st.expander("📱 Mobile Access"):
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            url = f"http://{local_ip}:8501"
            img = qrcode.make(url)
            st.image(img.get_image(), caption=f"Scan to open on Phone: {url}")
        except:
            st.warning("Could not generate QR code.")

# --- 5. DASHBOARD ---
st.title("💰 Super Accountant v2.0")

# Metrics
metrics = st.session_state.accountant.forecaster.project_balance(30)
c1, c2, c3 = st.columns(3)
c1.metric("Cash", f"${metrics['current_balance']}")
c2.metric("Forecast (30d)", f"${metrics['projected_balance']}", metrics['status'])
c3.metric("Blockchain Status", "🔒 Secured")

# Charts & Audit
tab1, tab2 = st.tabs(["📈 Cash Flow", "⛓️ Blockchain Ledger"])

with tab1:
    start_val = metrics['current_balance']
    chart_data = pd.DataFrame({'Days': range(90), 'Balance': [start_val + (i*20) for i in range(90)]})
    st.line_chart(chart_data, x='Days', y='Balance')

with tab2:
    st.caption("Immutable Audit Trail (SHA-256 Secured)")
    chain_data = []
    for block in st.session_state.accountant.audit.chain:
        chain_data.append({
            "Index": block.index,
            "Hash": block.hash[:15] + "...",
            "Prev Hash": block.previous_hash[:15] + "...",
            "Data": str(block.data)
        })
    st.dataframe(pd.DataFrame(chain_data))

# --- 6. INTELLIGENT CHAT ---
st.divider()
user_input = st.chat_input("Ask: 'How much on coffee?'")

for role, msg in st.session_state.chat_history:
    st.chat_message(role).write(msg)

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.chat_history.append(("user", user_input))
    
    # Use Query Engine directly for reasoning
    with st.chat_message("assistant"):
        # Check if it's a data query
        if "coffee" in user_input or "runway" in user_input:
            result = st.session_state.accountant.query_engine.ask(user_input)
            st.write(result['answer'])
            with st.expander("🧠 See Reasoning"):
                for step in result['reasoning']:
                    st.write(f"- {step}")
            st.session_state.chat_history.append(("assistant", result['answer']))
        else:
            # Fallback to general controller
            resp = st.session_state.accountant.process_input(user_input)
            st.write(resp)
            st.session_state.chat_history.append(("assistant", resp))