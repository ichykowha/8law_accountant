import streamlit as st
import requests
import json
import pandas as pd

# --- Configuration ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="8law Professional", page_icon="⚖️", layout="wide")

# --- Session State ---
if "t4_data" not in st.session_state:
    st.session_state["t4_data"] = None

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = True 

# --- Sidebar ---
with st.sidebar:
    st.title("8law Accountant")
    st.markdown("---")
    nav = st.radio("Navigation", ["Dashboard", "Tax Calculator", "Document Upload", "Client Management"])
    st.markdown("---")
    st.write(f"**Status:** 🟢 System Online")

# --- Dashboard Page ---
if nav == "Dashboard":
    st.title("Firm Overview")
    st.info("System initialized successfully.")

# --- Tax Calculator ---
elif nav == "Tax Calculator":
    st.title("T1 Decision Engine")
    
    # Auto-fill logic
    default_amount = 50000.00
    if st.session_state["t4_data"]:
        t4 = st.session_state["t4_data"]
        st.success(f"⚡ Data Loaded from T4: {t4.get('employer', 'Unknown Employer')}")
        if t4.get("box_14_income"):
            default_amount = float(t4["box_14_income"])
    
    with st.form("tax_calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            income_type = st.selectbox("Income Type", ["EMPLOYMENT", "SELF_EMPLOYED"])
        with col2:
            amount = st.number_input("Amount ($)", min_value=0.0, value=default_amount, step=100.0)
        submitted = st.form_submit_button("Calculate Tax")
        
    if submitted:
        try:
            payload = {"income_type": income_type, "amount": amount, "province": "ON"}
            response = requests.post(f"{API_URL}/tax/calculate", json=payload)
            
            if response.status_code == 200:
                st.success("Calculation Complete")
                data = response.json()
                
                # Display Analysis & Estimate
                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.subheader("Analysis")
                    st.json(data["analysis"])
                with res_col2:
                    st.subheader("Federal Tax Estimate")
                    st.metric("Federal Tax Owing", f"${data['tax_estimate']['federal_tax_before_credits']}")
                    with st.expander("View Bracket Breakdown"):
                        st.table(pd.DataFrame(data['tax_estimate']['bracket_breakdown']))
            else:
                st.error(f"API Error: {response.status_code}")
                
        except Exception as e:
            st.error(f"Connection Error: {e}")

# --- Document Upload (With Smart Parser) ---
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
                        
                        parsed = result.get("parsed_data", {})
                        raw_text = result.get("scan_result", {}).get("raw_text", "")
                        
                        # Save to memory for the calculator
                        st.session_state["t4_data"] = parsed
                        
                        # Display Metrics (4 Columns)
                        st.subheader("Extracted Data")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        col1.metric("Income (Box 14)", f"${parsed.get('box_14_income')}")
                        col2.metric("Tax Paid (Box 22)", f"${parsed.get('box_22_tax_deducted')}")
                        col3.metric("CPP (Box 16)", f"${parsed.get('box_16_cpp')}")
                        col4.metric("EI (Box 18)", f"${parsed.get('box_18_ei')}")
                        
                        st.info(f"Employer Identified: {parsed.get('employer')}")

                        # --- DEBUG SECTION ---
                        st.markdown("---")
                        st.warning("⚠️ Algorithm Debugging Zone")
                        with st.expander("🔎 View Raw AI Vision", expanded=True):
                            st.text(raw_text)
                            
                    else:
                        st.error(f"Scanning Failed: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- Client Management ---
elif nav == "Client Management":
    st.title("Client Registry")
    st.write("Database connection active via API.")