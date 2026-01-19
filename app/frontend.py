import os
import sys
import time
import subprocess
import shutil
from decimal import Decimal

import streamlit as st
import pandas as pd

# Make this module safe to import:
# - Avoid importing backend modules at top-level (prevents circular-import / partial-init issues).
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


def _fmt_money(v):
    """
    Format money values for Streamlit metrics.
    """
    return "—" if v is None else f"${float(v):,.2f}"


def _safe_import(module_name: str):
    """
    Import a module defensively; return (ok, details).
    """
    try:
        __import__(module_name)
        return True, f"Imported {module_name}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _run_self_tests() -> dict:
    """
    Runs lightweight diagnostics that should work in Streamlit Cloud:
    - T1DecisionEngine calculation sanity check
    - parse_t4_text sanity check with bundled sample text (no OCR)
    - OCR dependency validation (python imports + tesseract binary presence/version)
    """
    results = {
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "tests": {},
        "summary": {"passed": 0, "failed": 0},
    }

    def record(test_name: str, ok: bool, details: dict):
        results["tests"][test_name] = {"ok": ok, **details}
        if ok:
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1

    # --- Test 1: backend import ---
    t0 = time.time()
    try:
        T1DecisionEngine, scan_pdf, parse_t4_text = _get_backend()
        record(
            "backend_imports",
            True,
            {"duration_ms": int((time.time() - t0) * 1000), "details": "Imported backend.logic modules successfully"},
        )
    except Exception as e:
        record(
            "backend_imports",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )
        # If backend can't import, downstream tests will be unreliable.
        return results

    # --- Test 2: T1DecisionEngine calculation ---
    t0 = time.time()
    try:
        engine = T1DecisionEngine(tax_year=2024)
        processed = engine.process_income_stream("T4", 50000.0)
        tax_result = engine.calculate_federal_tax(Decimal("50000.00"), return_breakdown=True)

        # Extract something stable-ish for display, but remain defensive.
        sample_tax = None
        if isinstance(tax_result, dict):
            sample_tax = (
                tax_result.get("federal_tax_before_credits")
                or tax_result.get("federal_tax")
                or tax_result.get("total_tax")
            )

        record(
            "t1_engine_trivial_calc",
            True,
            {
                "duration_ms": int((time.time() - t0) * 1000),
                "processed_keys": sorted(list(processed.keys())) if isinstance(processed, dict) else str(type(processed)),
                "tax_result_keys": sorted(list(tax_result.keys())) if isinstance(tax_result, dict) else str(type(tax_result)),
                "sample_tax_value": sample_tax,
            },
        )
    except Exception as e:
        record(
            "t1_engine_trivial_calc",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    # --- Test 3: parser sanity check (no OCR) ---
    t0 = time.time()
    try:
        # Bundled sample text approximating what OCR might produce for a T4.
        # This is meant to validate "parse_t4_text" wiring and regex/heuristics.
        sample_t4_text = """
        T4 Statement of Remuneration Paid
        Employer: ACME INDUSTRIES LTD
        Box 14 Employment income 50000.00
        Box 22 Income tax deducted 7000.00
        Box 16 CPP contributions 2500.00
        Box 18 EI premiums 800.00
        Employee: John Doe
        SIN: 123 456 789
        """

        parsed = parse_t4_text(sample_t4_text)
        record(
            "t4_parser_sanity",
            True,
            {
                "duration_ms": int((time.time() - t0) * 1000),
                "parsed_preview": parsed,
            },
        )
    except Exception as e:
        record(
            "t4_parser_sanity",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    # --- Test 4: OCR dependencies validation ---
    # This does NOT run OCR on a PDF (needs a sample PDF + renderer). Instead it validates:
    # - python libs importable
    # - tesseract binary exists and returns a version
    t0 = time.time()
    try:
        dep_checks = {}

        # Python modules commonly needed for OCR/PDF extraction flows
        for mod in ["PIL", "pytesseract", "pdfplumber", "pypdf", "pypdfium2"]:
            ok, msg = _safe_import(mod)
            dep_checks[mod] = {"ok": ok, "details": msg}

        tesseract_path = shutil.which("tesseract")
        if not tesseract_path:
            dep_checks["tesseract_binary"] = {"ok": False, "details": "tesseract not found on PATH"}
            tesseract_version = None
        else:
            try:
                # Keep it short; streamlit logs remain readable.
                proc = subprocess.run(
                    ["tesseract", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                out = (proc.stdout or proc.stderr or "").splitlines()
                tesseract_version = out[0].strip() if out else "Unknown"
                dep_checks["tesseract_binary"] = {
                    "ok": proc.returncode == 0,
                    "details": f"{tesseract_path} | {tesseract_version}",
                }
            except Exception as e:
                dep_checks["tesseract_binary"] = {"ok": False, "details": f"{type(e).__name__}: {e}"}
                tesseract_version = None

        overall_ok = all(v["ok"] for v in dep_checks.values())

        record(
            "ocr_dependency_validation",
            overall_ok,
            {
                "duration_ms": int((time.time() - t0) * 1000),
                "checks": dep_checks,
                "tesseract_version": tesseract_version,
            },
        )
    except Exception as e:
        record(
            "ocr_dependency_validation",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    return results


def _render_self_test_panel():
    """
    Renders a diagnostics expander that the user can run on-demand.
    """
    with st.expander("Self-test / Diagnostics", expanded=False):
        st.caption(
            "Runs quick health checks: backend imports, T1 engine trivial calculation, T4 parser sanity check, and OCR dependency validation."
        )

        if st.button("Run self-tests", type="primary"):
            with st.spinner("Running self-tests..."):
                results = _run_self_tests()

            passed = results["summary"]["passed"]
            failed = results["summary"]["failed"]

            if failed == 0:
                st.success(f"All self-tests passed ({passed} passed, {failed} failed).")
            else:
                st.error(f"Self-tests completed with failures ({passed} passed, {failed} failed).")

            st.json(results)

            # Optional: show a human-readable rollup
            st.markdown("---")
            st.subheader("Rollup")
            for name, info in results["tests"].items():
                if info.get("ok"):
                    st.write(f"✅ {name}")
                else:
                    st.write(f"❌ {name} — {info.get('error', 'See details above')}")


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
        st.markdown("---")
        _render_self_test_panel()

    # --- Dashboard Page ---
    if nav == "Dashboard":
        st.title("Firm Overview")
        st.info("System initialized successfully.")
        st.markdown("---")
        st.subheader("Operational Checks")
        st.write("Run diagnostics from the sidebar to validate engine wiring and OCR dependencies.")

    # --- Tax Calculator ---
    elif nav == "Tax Calculator":
        st.title("T1 Decision Engine")

        default_amount = 50000.00
        if st.session_state["t4_data"]:
            t4 = st.session_state["t4_data"]
            st.success(f"⚡ Data Loaded from T4: {t4.get('employer', 'Unknown Employer')}")
            if t4.get("box_14_income") is not None:
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

                        col1.metric("Income (Box 14)", _fmt_money(parsed.get("box_14_income")))
                        col2.metric("Tax Paid (Box 22)", _fmt_money(parsed.get("box_22_tax_deducted")))
                        col3.metric("CPP (Box 16)", _fmt_money(parsed.get("box_16_cpp")))
                        col4.metric("EI (Box 18)", _fmt_money(parsed.get("box_18_ei")))

                        employer_val = parsed.get("employer") or "—"
                        st.info(f"Employer Identified: {employer_val}")

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


if __name__ == "__main__":
    main()
