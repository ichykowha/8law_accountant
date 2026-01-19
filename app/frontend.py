import os
import sys
from decimal import Decimal

import streamlit as st
import pandas as pd


# Make this module safe to import:
# - Avoid importing backend modules at top-level (prevents circular-import / partial-init issues).
# - Keep a defensive sys.path insert, but do not depend on it being present elsewhere.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

__all__ = ["main"]


def _get_backend():
    """
    Lazy-load backend modules to avoid import-time failures / circular imports.
    Returns imported backend symbols.
    """
    from backend.logic.t1_engine import T1DecisionEngine
    from backend.logic.ocr_engine import scan_pdf
    from backend.logic.t4_parser import parse_t4_text
    return T1DecisionEngine, scan_pdf, parse_t4_text


def calculate_tax_local(income_type_ui: str, amount: float, province: str, tax_year: int = 2024) -> dict:
    """
    Local replacement for POST /tax/calculate
    Adjust the income_type mapping to what your T1DecisionEngine expects.
    """
    T1DecisionEngine, _, _ = _get_backend()

    income_type_map = {
        "EMPLOYMENT": "T4",
        "SELF_EMPLOYED": "SELF_EMPLOYED",
    }
    income_type = income_type_map.get(income_type_ui, income_type_ui)

    engine = T1DecisionEngine(tax_year=tax_year)

    processed = engine.process_income_stream(income_type, float(amount))

    taxable_source = processed.get("taxable_amount", amount)
    taxable_amt = Decimal(str(taxable_source))

    tax_result = engine.calculate_federal_tax(taxable_amt, return_breakdown=True)

    return {"analysis": processed, "tax_estimate": tax_result}


def scan_and_parse_pdf_local(pdf_bytes: bytes) -> dict:
    """
    Local replacement for POST /document/scan
    """
    _, scan_pdf, parse_t4_text = _get_backend()

    ocr_result = scan_pdf(pdf_bytes)
    raw_text = (ocr_result.get("raw_text") or "")
    parsed_data = parse_t4_text(raw_text)

    return {"scan_result": ocr_result, "parsed_data": parsed_data}


def main():
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
        st.write("**Status:** 🟢 System Online")

    # --- Dashboard Page ---
    if nav == "Dashboard":
        st.title("Firm Overview")
        st.info("System initialized successfully.")

    # --- Tax Calculator ---
    elif nav == "Tax Calculator":
        st.title("T1 Decision Engine")

        default_amount = 50000.00
        if st.session_state["t4_data"]:
            t4 = st.session_state["t4_data"]
            st.success(f"⚡ Data Loaded from T4: {t4.get('employer', 'Unknown Employer')}")
            if t4.get("box_14_income"):
                try:
                    default_amount = float(t4["box_14_income"])
                except Exception:
                    pass

        with st.form("tax_calc_form"):
            col1, col2 = st.columns(2)
            with col1:
                income_type_ui = st.selectbox("Income Type", ["EMPLOYMENT", "SELF_EMPLOYED"])
            with col2:
                amount = st.number_input("Amount ($)", min_value=0.0, value=float(default_amount), step=100.0)
            submitted = st.form_submit_button("Calculate Tax")

        if submitted:
            try:
                data = calculate_tax_local(
                    income_type_ui=income_type_ui,
                    amount=amount,
                    province="ON",
                    tax_year=2024,
                )

                st.success("Calculation Complete")

                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.subheader("Analysis")
                    st.json(data["analysis"])

                with res_col2:
                    st.subheader("Federal Tax Estimate")

                    federal_tax = data["tax_estimate"].get("federal_tax_before_credits")
                    if federal_tax is not None:
                        st.metric("Federal Tax Owing", f"${federal_tax}")
                    else:
                        st.write("Tax estimate:")
                        st.json(data["tax_estimate"])

                    breakdown = data["tax_estimate"].get("bracket_breakdown")
                    if breakdown:
                        with st.expander("View Bracket Breakdown"):
                            st.table(pd.DataFrame(breakdown))

            except Exception as e:
                st.error(f"Calculation failed: {type(e).__name__}: {e}")

    # --- Document Upload (With Smart Parser) ---
    elif nav == "Document Upload":
        st.title("Secure Vault Upload")
        uploaded_file = st.file_uploader("Upload Client Statements (PDF)", type=["pdf"])

        if uploaded_file:
            if st.button("Scan & Parse Document"):
                with st.spinner("AI Reading Document..."):
                    try:
                        result = scan_and_parse_pdf_local(uploaded_file.getvalue())

                        st.success("Scan Complete!")

                        parsed = result.get("parsed_data", {}) or {}
                        raw_text = (result.get("scan_result", {}) or {}).get("raw_text", "")

                        st.session_state["t4_data"] = parsed

                        st.subheader("Extracted Data")
                        col1, col2, col3, col4 = st.columns(4)

                        col1.metric("Income (Box 14)", f"${parsed.get('box_14_income')}")
                        col2.metric("Tax Paid (Box 22)", f"${parsed.get('box_22_tax_deducted')}")
                        col3.metric("CPP (Box 16)", f"${parsed.get('box_16_cpp')}")
                        col4.metric("EI (Box 18)", f"${parsed.get('box_18_ei')}")

                        st.info(f"Employer Identified: {parsed.get('employer')}")

                        st.markdown("---")
                        st.warning("⚠️ Algorithm Debugging Zone")
                        with st.expander("🔎 View Raw AI Vision", expanded=True):
                            st.text(raw_text)

                    except Exception as e:
                        st.error(f"Scan failed: {type(e).__name__}: {e}")

    # --- Client Management ---
    elif nav == "Client Management":
        st.title("Client Registry")
        st.write("Database connection can be added here (direct SQLAlchemy or Supabase client).")
