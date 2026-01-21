# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Streamlit Frontend Entry Point
# File: app/streamlit_app.py
# ------------------------------------------------------------------------------

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.frontend import main

main()

from decimal import Decimal

import streamlit as st

# Ensure repo root is on sys.path so we can import `backend.*`
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Backend imports (direct module calls, no HTTP required)
from backend.logic.t1_engine import T1DecisionEngine
from backend.logic.ocr_engine import scan_pdf
from backend.logic.t4_parser import parse_t4_text


st.set_page_config(page_title="8law Super Accountant", layout="wide")

st.title("8law Super Accountant")
st.caption("Streamlit UI for 8law. This runs on port 8501 and calls backend logic directly.")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    tax_year = st.number_input("Tax Year", min_value=2000, max_value=2100, value=2024, step=1)
    province = st.selectbox("Province", ["ON", "BC", "AB", "QC", "MB", "SK", "NS", "NB", "NL", "PE", "NT", "NU", "YT"])

tab_tax, tab_scan = st.tabs(["Tax Estimate", "Scan & Parse (T4 PDF)"])


# ----------------------------
# Tab 1: Tax Estimate
# ----------------------------
with tab_tax:
    st.subheader("Tax Estimate")

    income_type = st.selectbox("Income Type", ["T4", "CAPITAL_GAINS"])
    amount = st.number_input("Amount", min_value=0.0, value=0.0, step=100.0)

    col1, col2 = st.columns([1, 3])
    with col1:
        run_calc = st.button("Calculate", use_container_width=True)

    if run_calc:
        try:
            engine = T1DecisionEngine(tax_year=int(tax_year))
            processed = engine.process_income_stream(income_type, float(amount))

            taxable_amt = Decimal(str(p_
