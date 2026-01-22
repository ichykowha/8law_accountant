# app/frontend.py
import os
import sys
import time
import subprocess
import shutil
from decimal import Decimal
from typing import Any, List, Tuple

import streamlit as st
import pandas as pd

from app.supabase_auth import require_auth, sign_out
from app.client_manager import require_active_client

# -----------------------------------------------------------------------------
# Streamlit UI (safe to import)
# -----------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

__all__ = ["main"]


# ---------------------------------------------------------------------
# Lazy backend imports (prevents circular import / partial-init issues)
# ---------------------------------------------------------------------
def _get_backend():
    from backend.logic.t1_engine import T1DecisionEngine
    from backend.logic.ocr_engine import scan_pdf
    from backend.logic.t4_parser import parse_t4_text
    from backend.logic.doc_classifier import detect_doc_type
    from backend.logic.invoice_parser import parse_invoice_text
    return T1DecisionEngine, scan_pdf, parse_t4_text, detect_doc_type, parse_invoice_text


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------
def _fmt_money(v: Any) -> str:
    try:
        if v is None:
            return "—"
        return f"${float(v):,.2f}"
    except Exception:
        return str(v) if v is not None else "—"


def _fmt_date(v: Any) -> str:
    return str(v) if v else "—"


# -----------------------------------------------------------------------------
# Core operations
# -----------------------------------------------------------------------------
def calculate_tax_local(income_type_ui: str, amount: float, province: str, tax_year: int = 2024) -> dict:
    T1DecisionEngine, _, _, _, _ = _get_backend()

    income_type_map = {
        "EMPLOYMENT": "T4",
        "SELF_EMPLOYED": "SELF_EMPLOYED",
    }
    income_type = income_type_map.get(income_type_ui, income_type_ui)

    engine = T1DecisionEngine(tax_year=tax_year)
    processed = engine.process_income_stream(income_type, float(amount))

    taxable_source = processed.get("taxable_amount", amount) if isinstance(processed, dict) else amount
    taxable_amt = Decimal(str(taxable_source))

    tax_result = engine.calculate_federal_tax(taxable_amt, return_breakdown=True)

    return {"analysis": processed, "tax_estimate": tax_result}


def _embed_texts(texts: List[str]) -> List[List[float]]:
    from backend.logic.embeddings import embed_texts
    return embed_texts(texts)


def scan_and_extract_pdf_local(pdf_bytes: bytes, requested_doc_type: str = "auto") -> dict:
    _, scan_pdf, parse_t4_text, detect_doc_type, parse_invoice_text = _get_backend()

    ocr_result = scan_pdf(pdf_bytes)
    raw_text = (ocr_result.get("raw_text") or "").strip()

    suggested_type, scores = detect_doc_type(raw_text)
    doc_type = suggested_type if requested_doc_type == "auto" else requested_doc_type

    def _not_implemented(dt: str) -> dict:
        return {
            "doc_type": dt,
            "message": f"Parser for '{dt}' not implemented yet. Showing raw text for review.",
        }

    if doc_type == "t4":
        extracted = parse_t4_text(raw_text) or {}
        if isinstance(extracted, dict):
            extracted["doc_type"] = "t4"

    elif doc_type == "invoice":
        extracted = parse_invoice_text(raw_text) or {}
        if isinstance(extracted, dict):
            extracted["doc_type"] = "invoice"

    elif doc_type in {"receipt", "bank_statement", "credit_card_statement"}:
        extracted = _not_implemented(doc_type)

    else:
        extracted = {
            "doc_type": doc_type,
            "scores": scores,
            "message": "Unrecognized document type. Showing raw text for review.",
        }

    return {
        "scan_result": ocr_result,
        "raw_text": raw_text,
        "requested_doc_type": requested_doc_type,
        "suggested_doc_type": suggested_type,
        "scores": scores,
        "doc_type": doc_type,
        "extracted": extracted,
    }


# -----------------------------------------------------------------------------
# Diagnostics helpers
# -----------------------------------------------------------------------------
def _safe_import(module_name: str) -> Tuple[bool, str]:
    try:
        __import__(module_name)
        return True, f"Imported {module_name}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _run_self_tests() -> dict:
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

    # --- backend import ---
    t0 = time.time()
    try:
        T1DecisionEngine, _, parse_t4_text, detect_doc_type, parse_invoice_text = _get_backend()
        record("backend_imports", True, {"duration_ms": int((time.time() - t0) * 1000)})
    except Exception as e:
        record("backend_imports", False, {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})
        return results

    # --- T1 engine trivial calc ---
    t0 = time.time()
    try:
        engine = T1DecisionEngine(tax_year=2024)
        processed = engine.process_income_stream("T4", 50000.0)
        tax_result = engine.calculate_federal_tax(Decimal("50000.00"), return_breakdown=True)

        record(
            "t1_engine_trivial_calc",
            True,
            {
                "duration_ms": int((time.time() - t0) * 1000),
                "processed_keys": sorted(list(processed.keys())) if isinstance(processed, dict) else str(type(processed)),
                "tax_result_keys": sorted(list(tax_result.keys())) if isinstance(tax_result, dict) else str(type(tax_result)),
            },
        )
    except Exception as e:
        record("t1_engine_trivial_calc", False, {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})

    # --- Doc classifier sanity ---
    t0 = time.time()
    try:
        invoice_text = "Invoice / Facture\nTotal payable / Total à payer: $26.67\nInvoice # CA386..."
        t4_text = "T4 Statement of Remuneration Paid\nBox 14 Employment income 50000.00\nBox 22 Income tax deducted 7000.00"
        doc_a, scores_a = detect_doc_type(invoice_text)
        doc_b, scores_b = detect_doc_type(t4_text)
        record(
            "doc_classifier_sanity",
            True,
            {
                "duration_ms": int((time.time() - t0) * 1000),
                "invoice_detected": doc_a,
                "invoice_scores": scores_a,
                "t4_detected": doc_b,
                "t4_scores": scores_b,
            },
        )
    except Exception as e:
        record("doc_classifier_sanity", False, {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})

    # --- Invoice parser sanity ---
    t0 = time.time()
    try:
        sample_invoice = """
        Invoice / Facture
        Sold by / Vendu par: Amazon.com.ca, Inc
        Invoice date / Date de facturation: 05 December 2023
        Invoice # / # de facture: CA386KE42M0I
        Total payable / Total à payer: $26.67
        GST/HST # / # de TPS/TVH: 85730 5932 RT0001
        PST # / # de TVP: PST-1017-2103
        Total $24.55 -$0.74 $1.19 $1.67 $2.86
        """
        parsed = parse_invoice_text(sample_invoice)
        record("invoice_parser_sanity", True, {"duration_ms": int((time.time() - t0) * 1000), "parsed_preview": parsed})
    except Exception as e:
        record("invoice_parser_sanity", False, {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})

    # --- OCR dependency validation ---
    t0 = time.time()
    try:
        dep_checks = {}
        for mod in ["PIL", "pytesseract", "pdfplumber", "pypdf", "pypdfium2"]:
            ok, msg = _safe_import(mod)
            dep_checks[mod] = {"ok": ok, "details": msg}

        tesseract_path = shutil.which("tesseract")
        if not tesseract_path:
            dep_checks["tesseract_binary"] = {"ok": False, "details": "tesseract not found on PATH"}
        else:
            try:
                proc = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=8, check=False)
                out = (proc.stdout or proc.stderr or "").splitlines()
                ver = out[0].strip() if out else "Unknown"
                dep_checks["tesseract_binary"] = {"ok": proc.returncode == 0, "details": f"{tesseract_path} | {ver}"}
            except Exception as e:
                dep_checks["tesseract_binary"] = {"ok": False, "details": f"{type(e).__name__}: {e}"}

        overall_ok = all(v["ok"] for v in dep_checks.values())
        record("ocr_dependency_validation", overall_ok, {"duration_ms": int((time.time() - t0) * 1000), "checks": dep_checks})
    except Exception as e:
        record("ocr_dependency_validation", False, {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})

    return results


def _render_self_test_panel():
    with st.expander("Self-test / Diagnostics", expanded=False):
        st.caption("Quick health checks: backend imports, classifiers/parsers, OCR dependencies.")
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


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="8law Professional", page_icon="⚖️", layout="wide")

    # 1) Auth guard (Supabase Auth)
    require_auth()

    # 2) Client guard (forces dashboard until selected)
    require_active_client()

    # --- Session State ---
    st.session_state.setdefault("t4_data", None)
    st.session_state.setdefault("last_doc", None)
    st.session_state.setdefault("authentication_status", True)

    active_client_name = st.session_state.get("current_client_name") or "—"

    # --- Sidebar ---
    with st.sidebar:
        st.title("8law Accountant")
        st.caption(f"Active client: **{active_client_name}**")
        st.markdown("---")

        nav = st.radio(
            "Navigation",
            ["Dashboard", "Tax Calculator", "Document Upload", "Knowledge Base", "Client Management"],
        )

        st.markdown("---")
        if st.button("Sign out"):
            sign_out()

        st.markdown("---")
        _render_self_test_panel()

    # --- Dashboard ---
    if nav == "Dashboard":
        st.title("Firm Overview")
        st.info("System initialized successfully.")
        st.write(f"Active client file: {active_client_name}")

    # --- Tax Calculator ---
    elif nav == "Tax Calculator":
        st.title("T1 Decision Engine")

        default_amount = 50000.00
        if st.session_state["t4_data"]:
            t4 = st.session_state["t4_data"]
            st.success(f"Data loaded from T4: {t4.get('employer', 'Unknown Employer')}")
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
                amount = st.number_input("Amount ($)", value=float(default_amount), step=100.0, key="tax_amount")
            submitted = st.form_submit_button("Calculate Tax")

        if submitted:
            try:
                data = calculate_tax_local(income_type_ui=income_type_ui, amount=amount, province="ON", tax_year=2024)
                st.success("Calculation Complete")
                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.subheader("Analysis")
                    st.json(data["analysis"])
                with res_col2:
                    st.subheader("Federal Tax Estimate")
                    if isinstance(data["tax_estimate"], dict):
                        federal_tax = data["tax_estimate"].get("federal_tax_before_credits") or data["tax_estimate"].get("federal_tax")
                        if federal_tax is not None:
                            st.metric("Federal Tax Owing", f"${federal_tax}")
                        breakdown = data["tax_estimate"].get("bracket_breakdown")
                        if breakdown:
                            with st.expander("View Bracket Breakdown"):
                                st.table(pd.DataFrame(breakdown))
                    else:
                        st.json(data["tax_estimate"])
            except Exception as e:
                st.error(f"Calculation failed: {type(e).__name__}: {e}")

    # --- Document Upload ---
    elif nav == "Document Upload":
        st.title("Secure Vault Upload")

        doc_choice = st.selectbox(
            "Document type",
            [
                "Auto-detect (beta)",
                "T4 (Employment slip)",
                "Invoice",
                "Receipt",
                "Bank statement",
                "Credit card statement",
            ],
            index=0,
        )

        choice_to_type = {
            "Auto-detect (beta)": "auto",
            "T4 (Employment slip)": "t4",
            "Invoice": "invoice",
            "Receipt": "receipt",
            "Bank statement": "bank_statement",
            "Credit card statement": "credit_card_statement",
        }
        requested_doc_type = choice_to_type.get(doc_choice, "auto")

        uploaded_file = st.file_uploader("Upload Client Statements (PDF)", type=["pdf"])

        if uploaded_file:
            if st.button("Scan & Extract Document", type="primary"):
                with st.spinner("AI Reading Document..."):
                    try:
                        result = scan_and_extract_pdf_local(uploaded_file.getvalue(), requested_doc_type=requested_doc_type)

                        st.success("Scan Complete!")

                        extracted = result.get("extracted", {}) or {}
                        raw_text = result.get("raw_text", "") or ""
                        doc_type = result.get("doc_type", "unknown")
                        scores = result.get("scores", {}) or {}
                        suggested = result.get("suggested_doc_type", "unknown")

                        st.session_state["last_doc"] = result

                        st.caption(f"Requested: {requested_doc_type} | Used: {doc_type} | Suggested: {suggested} | scores={scores}")
                        if requested_doc_type != "auto" and suggested and suggested != requested_doc_type:
                            st.warning(
                                f"Classifier suggests '{suggested}', but you selected '{requested_doc_type}'. Proceeding with your selection."
                            )

                        st.subheader("Extracted Data")

                        if doc_type == "t4":
                            st.session_state["t4_data"] = extracted
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Income (Box 14)", _fmt_money(extracted.get("box_14_income")))
                            col2.metric("Tax Paid (Box 22)", _fmt_money(extracted.get("box_22_tax_deducted")))
                            col3.metric("CPP (Box 16)", _fmt_money(extracted.get("box_16_cpp")))
                            col4.metric("EI (Box 18)", _fmt_money(extracted.get("box_18_ei")))
                            employer_val = extracted.get("employer") or "—"
                            st.info(f"Employer Identified: {employer_val}")

                        elif doc_type == "invoice":
                            total_payable = extracted.get("total_payable") or extracted.get("total") or extracted.get("amount_due")
                            invoice_date = extracted.get("invoice_date") or extracted.get("date")
                            gst_amt = extracted.get("gst_hst_amount") or extracted.get("gst") or extracted.get("hst")
                            pst_amt = extracted.get("pst_amount") or extracted.get("pst")

                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Total Payable", _fmt_money(total_payable))
                            col2.metric("Invoice Date", _fmt_date(invoice_date))
                            col3.metric("GST/HST", _fmt_money(gst_amt))
                            col4.metric("PST", _fmt_money(pst_amt))

                            seller = extracted.get("sold_by") or extracted.get("seller") or extracted.get("vendor") or "—"
                            st.info(f"Seller Identified: {seller}")

                            invoice_no = extracted.get("invoice_number") or extracted.get("invoice_no")
                            if invoice_no:
                                st.write(f"**Invoice #:** {invoice_no}")

                            items = extracted.get("items") or extracted.get("line_items") or []
                            if isinstance(items, list) and items:
                                with st.expander("Line Items", expanded=True):
                                    st.table(pd.DataFrame(items))
                            else:
                                st.caption("No line items detected (or invoice parser does not output them yet).")

                        elif doc_type in {"receipt", "bank_statement", "credit_card_statement"}:
                            st.warning(extracted.get("message", "Parsing not implemented yet."))
                            st.json(extracted)

                        else:
                            st.warning(extracted.get("message", "Unrecognized document type."))
                            st.json(extracted)

                        st.markdown("---")
                        st.warning("⚠️ Algorithm Debugging Zone")
                        with st.expander("🔎 View Raw AI Vision", expanded=True):
                            st.text(raw_text)

                    except Exception as e:
                        st.error(f"Scan failed: {type(e).__name__}: {e}")

    # --- Knowledge Base ---
    elif nav == "Knowledge Base":
        st.title("Knowledge Base Ingestion (Textbook)")

        book_default = os.getenv("BOOK_NAME") or "Accounting Textbook"
        book = st.text_input("Book name", value=book_default)
        chapter = st.text_input("Chapter label", value="Chapter 11")

        pdf = st.file_uploader("Upload Chapter PDF", type=["pdf"])

        if pdf and st.button("Ingest Chapter", type="primary"):
            with st.spinner("Extracting and chunking..."):
                from backend.logic.kb_ingest import extract_text_by_page, chunk_text
                from backend.logic.kb_store import upsert_chunks

                pdf_bytes = pdf.getvalue()
                pages = extract_text_by_page(pdf_bytes)
                chunks = chunk_text(pages, book=book, chapter=chapter)
                st.write(f"Extracted {len(pages)} pages, created {len(chunks)} chunks.")

            with st.spinner("Embedding and upserting to Pinecone..."):
                texts = [c.text for c in chunks]
                vectors = _embed_texts(texts)

                upsert_payload = []
                for c, v in zip(chunks, vectors):
                    md = dict(c.metadata)
                    md["text"] = c.text
                    upsert_payload.append((c.id, v, md))

                resp = upsert_chunks(upsert_payload)

            st.success("Ingestion complete.")
            st.json(resp)

    # --- Client Management ---
    elif nav == "Client Management":
        st.title("Client Management")
        st.info("Client selection is enforced by a global session guard.")
        st.write(f"Current active client: {active_client_name}")
        if st.button("Switch client"):
            st.session_state["current_client_id"] = None
            st.session_state["current_client_name"] = None
            st.rerun()


if __name__ == "__main__":
    main()
