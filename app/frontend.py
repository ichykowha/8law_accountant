import streamlit as st
import requests
import json
import pandas as pd

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="8law Professional", page_icon="⚖️", layout="wide")

# --- Session State (The Memory) ---
# We use this to remember the T4 data when switching tabs
if "t4_data" not in st.session_state:
    st.session_state["t4_data"] = None

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = True 

# --- Sidebar ---
with st.sidebar:
    st.image("favicon.png", width=50) 
    st.title("8law Accountant")
    st.markdown("---")
    nav = st.radio("Navigation", ["Dashboard", "Tax Calculator", "Document Upload", "Client Management"])
    st.markdown("---")
    st.write(f"**Status:** 🟢 System Online")

# --- Dashboard Page ---
if nav == "Dashboard":
    st.title("Firm Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Active Clients", "12")
    col2.metric("Documents Pending", "5")
    col3.metric("Tax Season Days Left", "104")
    st.info("System initialized successfully.")

# --- Tax Calculator (Auto-Fill Enabled) ---
elif nav == "Tax Calculator":
    st.title("T1 Decision Engine")

    # Check if we have T4 data in memory
    default_amount = 50000.00
    if st.session_state["t4_data"]:
        t4 = st.session_state["t4_data"]
        st.success(f"⚡ Data Loaded from T4: {t4.get('employer', 'Unknown Employer')}")
        # Auto-fill the amount from Box 14
        if t4.get("box_14_income"):
            default_amount = float(t4["box_14_income"])
    
    with st.form("tax_calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            income_type = st.selectbox("Income Type", ["EMPLOYMENT", "SELF_EMPLOYED", "CAPITAL_GAINS"])
        with col2:
            amount = st.number_input("Amount ($)", min_value=0.0, value=default_amount, step=100.0)
        
        submitted = st.form_submit_button("Calculate Tax")
        
    if submitted:
        payload = {"income_type": income_type, "amount": amount, "province": "ON"}
        with st.spinner("Consulting the AI Brain..."):
            try:
                response = requests.post(f"{API_URL}/tax/calculate", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    st.success("Calculation Complete")
                    
                    # Display Results
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
            except Exception as e:
                st.error(f"Connection Error: {e}")

# --- Document Upload (Parser Visualization) ---
elif nav == "Document Upload":
    st.title("Secure Vault Upload")
    uploaded_file = st.file_uploader("Upload Client Statements (PDF)", type=["pdf"])
    
    if uploaded_file:
        if st.button("Scan & Parse Document"):
            with st.spinner("AI Reading Document..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{API_URL}/document/scan", files=files)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("Scan Complete!")
                        
                        # --- THE NEW PART: Display Parsed Data ---
                        parsed = result.get("parsed_data", {})
                        
                        # Save to memory (Session State)
                        st.session_state["t4_data"] = parsed
                        
                        st.subheader("extracted T4 Data")
                        
                        # Create 3 nice columns for the data
                        d_col1, d_col2, d_col3 = st.columns(3)
                        d_col1.metric("Box 14 (Income)", f"${parsed.get('box_14_income') or 0}")
                        d_col2.metric("Box 22 (Tax Paid)", f"${parsed.get('box_22_tax_deducted') or 0}")
                        d_col3.metric("Box 16 (CPP)", f"${parsed.get('box_16_cpp') or 0}")
                        
                        st.write(f"**Employer:** {parsed.get('employer')}")
                        
                        st.info("👉 Go to the 'Tax Calculator' tab. This data has been auto-filled for you.")
                            
                    else:
                        st.error(f"Scanning Failed: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")