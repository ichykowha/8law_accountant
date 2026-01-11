import streamlit as st
import sys
import os
import pandas as pd
import socket
import qrcode
from PIL import Image

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from controller import PowerhouseAccountant
from auth import check_password

# --- 1. CONFIG ---
st.set_page_config(
    page_title="8law Scanner",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed" # Hides sidebar on mobile by default
)

# --- 2. SECURITY ---
if not check_password():
    st.stop()

# --- 3. INIT ---
if 'accountant' not in st.session_state:
    st.session_state.accountant = PowerhouseAccountant()
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 4. MOBILE-FIRST NAVIGATION ---
st.title("💰 8law Mobile")
tab_scan, tab_dash, tab_chat = st.tabs(["📸 Scan", "📊 Stats", "💬 Chat"])

# --- TAB 1: THE SCANNER ---
with tab_scan:
    st.header("Receipt Scanner")
    
    # The Camera Widget - Shows viewfinder in browser
    camera_photo = st.camera_input("Tap to Snap")
    
    if camera_photo:
        st.success("Image Captured!")
        
        # 1. Save locally so Tesseract can read it
        temp_dir = os.path.join("..", "data", "uploads")
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        
        # We name it with a timestamp so it doesn't overwrite
        filename = f"scan_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(temp_dir, filename)
        
        with open(save_path, "wb") as f:
            f.write(camera_photo.getbuffer())
            
        # 2. Process with AI
        with st.spinner("👀 Reading receipt..."):
            try:
                # Call the Universal Ingestor
                result_text = st.session_state.accountant.ingestor.ingest_file(save_path)
                
                # 3. Add to Blockchain
                st.session_state.accountant.audit.create_entry("Mobile Scan", save_path)
                
                # 4. Show Result
                st.success("✅ Processed Successfully")
                st.text_area("Extracted Data:", result_text, height=150)
                
            except Exception as e:
                st.error(f"Error reading image: {e}")

# --- TAB 2: DASHBOARD ---
with tab_dash:
    st.header("Financial Health")
    metrics = st.session_state.accountant.forecaster.project_balance(30)
    
    col1, col2 = st.columns(2)
    col1.metric("Cash Now", f"${metrics['current_balance']}")
    col2.metric("Runway", metrics['status'])
    
    # Simple Chart
    st.line_chart(pd.DataFrame({'Days': range(30), 'Balance': [metrics['current_balance'] - (i*10) for i in range(30)]}))

# --- TAB 3: CHAT ---
with tab_chat:
    st.header("Ask 8law")
    
    # Display History
    for role, msg in st.session_state.chat_history:
        st.chat_message(role).write(msg)

    # Chat Input
    user_input = st.chat_input("Type here...")
    if user_input:
        st.chat_message("user").write(user_input)
        st.session_state.chat_history.append(("user", user_input))
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                resp = st.session_state.accountant.process_input(user_input)
                st.write(resp)
        st.session_state.chat_history.append(("assistant", resp))
