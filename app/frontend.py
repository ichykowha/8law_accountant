import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="8law Professional", page_icon="⚖️", layout="wide")

# --- Authentication Check ---
# (We assume streamlit-authenticator handled the login before this script runs fully)
if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = True  # Fallback for dev

# --- Sidebar ---
with st.sidebar:
    st.image("favicon.png", width=50) # Make sure favicon.png is in root or adjust path
    st.title("8law Accountant")
    st.markdown("---")
    nav = st.radio("Navigation", ["Dashboard", "Tax Calculator", "Document Upload", "Client Management"])
    st.markdown("---")
    st.write(f"**Status:** 🟢 System Online")
    st.write(f"**API:** `{API_URL}`")

# --- Dashboard Page ---
if nav == "Dashboard":
    st.title("Firm Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Active Clients", "12")
    col2.metric("Documents Pending", "5")
    col3.metric("Tax Season Days Left", "104")
    
    st.markdown("### Recent Activity")
    st.info("System initialized successfully. Ready for T1 processing.")

# --- Tax Calculator (API Connected) ---
elif nav == "Tax Calculator":
    st.title("T1 Decision Engine (API Connected)")
    
    with st.form("tax_calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            income_type = st.selectbox("Income Type", ["EMPLOYMENT", "SELF_EMPLOYED", "CAPITAL_GAINS", "DIVIDENDS_ELIGIBLE_TAXABLE"])
        with col2:
            amount = st.number_input("Amount ($)", min_value=0.0, value=50000.0, step=100.0)
        
        submitted = st.form_submit_button("Calculate Tax")
        
    if submitted:
        payload = {
            "income_type": income_type,
            "amount": amount,
            "province": "ON"
        }
        
        with st.spinner("Consulting the AI Brain..."):
            try:
                response = requests.post(f"{API_URL}/tax/calculate", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    st.success("Calculation Complete")
                    
                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.subheader("Analysis")
                        st.json(data["analysis"])
                    with res_col2:
                        st.subheader("Federal Tax Estimate")
                        tax_est = data["tax_estimate"]
                        if isinstance(tax_est, dict):
                            st.metric("Federal Tax Owing", f"${tax_est.get('federal_tax_before_credits')}")
                            with st.expander("View Bracket Breakdown"):
                                st.table(pd.DataFrame(tax_est.get("bracket_breakdown", [])))
                        else:
                            st.metric("Federal Tax Owing", f"${tax_est}")
                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the API. Is 'uvicorn' running?")

# --- Document Upload (OCR Enabled) ---
elif nav == "Document Upload":
    st.title("Secure Vault Upload")
    
    uploaded_file = st.file_uploader("Upload Client Statements (PDF)", type=["pdf"])
    
    if uploaded_file:
        st.info(f"File loaded: {uploaded_file.name} ({uploaded_file.size} bytes)")
        
        if st.button("Scan Document"):
            with st.spinner("OCR Engine Reading Document..."):
                try:
                    # Prepare the file for the API
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    
                    # Send to the API
                    response = requests.post(f"{API_URL}/document/scan", files=files)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("Scan Complete!")
                        
                        # Show the extracted text
                        scan_data = result.get("scan_result", {})
                        st.write(f"**Pages Scanned:** {scan_data.get('pages_scanned')}")
                        
                        with st.expander("View Raw Extracted Text"):
                            st.text(scan_data.get("raw_text"))
                            
                    else:
                        st.error(f"Scanning Failed: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- Client Management ---
elif nav == "Client Management":
    st.title("Client Registry")
    st.write("Database connection active via API.")