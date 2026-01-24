# app/frontend.py
from __future__ import annotations

import os
import sys
import time
import subprocess
import shutil
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import streamlit as st
import pandas as pd

from app.auth_supabase import require_login, supabase_logout
from app.client_gate import require_client_selected, clear_selected_client


# -----------------------------------------------------------------------------
# Streamlit UI (safe to import)
# -----------------------------------------------------------------------------

# Ensure repo root is on sys.path so we can import backend/app modules reliably.
# If this file is app/frontend.py, repo root is one level above /app.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

__all__ = ["main"]


# -----------------------------------------------------------------------------
# Lazy backend imports (prevents circular import / partial-init issues)
# -----------------------------------------------------------------------------

def _get_backend():
    """
    Lazy-load backend modules to avoid import-time failures / circular imports.
    Returns imported backend symbols.
    """
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
# Core operations (local replacements for API endpoints)
# -----------------------------------------------------------------------------

def calculate_tax_local(income_type_ui: str, amount: float, province: str, tax_year: int = 2024) -> dict:
    """
    Local replacement for POST /tax/calculate
    Adjust the income_type mapping to what your T1DecisionEngine expects.
    """
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
    """
    OpenAI embedding provider (8law default).
    Requires OPENAI_API_KEY in environment.
    Optional OPENAI_EMBED_MODEL.
    """
    from backend.logic.embeddings import embed_texts
    return embed_texts(texts)


def scan_and_extract_pdf_local(pdf_bytes: bytes, requested_doc_type: str = "auto") -> dict:
    """
    OCR -> raw_text -> route parse based on requested_doc_type (or auto-detect).

    requested_doc_type:
      - "auto" | "t4" | "invoice" | "receipt" | "bank_statement" | "credit_card_statement"
    """
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
    results: Dict[str, Any] = {
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
        T1DecisionEngine, _, parse_t4_text, detect_doc_type, parse_invoice_text = _get_backend()
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
        return results

    # --- Test 2: T1DecisionEngine calculation ---
    t0 = time.time()
    try:
        engine = T1DecisionEngine(tax_year=2024)
        processed = engine.process_income_stream("T4", 50000.0)
        tax_result = engine.calculate_federal_tax(Decimal("50000.00"), return_breakdown=True)

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

    # --- Test 3: T4 parser sanity check (no OCR) ---
    t0 = time.time()
    try:
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
            {"duration_ms": int((time.time() - t0) * 1000), "parsed_preview": parsed},
        )
    except Exception as e:
        record(
            "t4_parser_sanity",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    # --- Test 4: doc classifier sanity check ---
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
        record(
            "doc_classifier_sanity",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    # --- Test 5: invoice parser sanity check ---
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
        record(
            "invoice_parser_sanity",
            True,
            {"duration_ms": int((time.time() - t0) * 1000), "parsed_preview": parsed},
        )
    except Exception as e:
        record(
            "invoice_parser_sanity",
            False,
            {"duration_ms": int((time.time() - t0) * 1000), "error": f"{type(e).__name__}: {e}"},
        )

    # --- Test 6: OCR dependencies validation ---
    t0 = time.time()
    try:
        dep_checks: Dict[str, Any] = {}
        for mod in ["PIL", "pytesseract", "pdfplumber", "pypdf", "pypdfium2"]:
            ok, msg = _safe_import(mod)
            dep_checks[mod] = {"ok": ok, "details": msg}

        tesseract_path = shutil.which("tesseract")
        if not tesseract_path:
            dep_checks["tesseract_binary"] = {"ok": False, "details": "tesseract not found on PATH"}
            tesseract_version = None
        else:
            try:
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
    with st.expander("Self-test / Diagnostics", expanded=False):
        st.caption(
            "Runs quick health checks: backend imports, T1 engine trivial calculation, T4 parser sanity check, "
            "doc classification, invoice parser sanity, and OCR dependency validation."
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

            st.markdown("---")
            st.subheader("Rollup")
            for name, info in results["tests"].items():
                if info.get("ok"):
                    st.write(f"✅ {name}")
                else:
                    st.write(f"❌ {name} — {info.get('error', 'See details above')}")


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="8law Professional", page_icon="⚖️", layout="wide")

    # --- Require login first ---
    user = require_login()
    if not user:
        return

    # --- HARD client selection gate ---
    client_id, client_name = require_client_selected()

    # --- Session State ---
    st.session_state.setdefault("t4_data", None)
    st.session_state.setdefault("last_doc", None)

    # --- Sidebar ---
    with st.sidebar:
        st.title("8law Accountant")
        st.caption(f"Signed in as: {user.get('email')}")

        st.markdown("**Active Client:**")
        st.write(client_name or "—")

        colx, coly = st.columns([1, 1])
        with colx:
            if st.button("Switch Client"):
                clear_selected_client()
                st.rerun()
        with coly:
            if st.button("Logout"):
                supabase_logout()
                clear_selected_client()
                st.rerun()

        st.markdown("---")
        nav = st.radio(
            "Navigation",
            ["Dashboard", "Tax Calculator", "Document Upload", "Knowledge Base", "Client Management"],
        )
        st.markdown("---")
        st.write("**Status:** 🟢 System Online")
        st.markdown("---")
        _render_self_test_panel()

    # --- Dashboard ---
    if nav == "Dashboard":
        st.title("Firm Overview")
        st.info("System initialized successfully.")
        st.markdown("---")
        st.subheader("Active Context")
        st.write(f"Client: **{client_name}**")
        st.caption(f"client_id: {client_id}")

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

                    federal_tax = data["tax_estimate"].get("federal_tax_before_credits") if isinstance(data["tax_estimate"], dict) else None
                    if federal_tax is not None:
                        st.metric("Federal Tax Owing", f"${federal_tax}")
                    else:
                        st.write("Tax estimate:")
                        st.json(data["tax_estimate"])

                    breakdown = data["tax_estimate"].get("bracket_breakdown") if isinstance(data["tax_estimate"], dict) else None
                    if breakdown:
                        with st.expander("View Bracket Breakdown"):
                            st.table(pd.DataFrame(breakdown))

            except Exception as e:
                st.error(f"Calculation failed: {type(e).__name__}: {e}")

    # --- Document Upload ---
    elif nav == "Document Upload":
        st.title("Secure Vault Upload")
        st.caption(f"Uploading into client file: {client_name}")

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
                        result = scan_and_extract_pdf_local(
                            uploaded_file.getvalue(),
                            requested_doc_type=requested_doc_type,
                        )

                        st.success("Scan Complete!")

                        extracted = result.get("extracted", {}) or {}
                        raw_text = result.get("raw_text", "") or ""
                        doc_type = result.get("doc_type", "unknown")
                        scores = result.get("scores", {}) or {}
                        suggested = result.get("suggested_doc_type", "unknown")

                        st.session_state["last_doc"] = result

                        st.caption(
                            f"Requested: {requested_doc_type} | Used: {doc_type} | Suggested: {suggested} | scores={scores}"
                        )
                        if requested_doc_type != "auto" and suggested and suggested != requested_doc_type:
                            st.warning(
                                f"Classifier suggests '{suggested}', but you selected '{requested_doc_type}'. "
                                "Proceeding with your selection."
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

                        elif doc_type == "receipt":
                            st.warning(extracted.get("message", "Receipt parsing not implemented yet."))
                            st.json(extracted)

                        elif doc_type == "bank_statement":
                            st.warning(extracted.get("message", "Bank statement parsing not implemented yet."))
                            st.json(extracted)

                        elif doc_type == "credit_card_statement":
                            st.warning(extracted.get("message", "Credit card statement parsing not implemented yet."))
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
        st.title("Client Registry")
        st.write("Client tables + RLS + selection gate are now wired.")
        st.markdown("---")
        st.write(f"Active client: **{client_name}**")
        st.caption(f"client_id: {client_id}")
        st.info("Next: document storage + expense_events scoped to client_id.")

    else:
        st.warning("Unknown navigation state.")


if __name__ == "__main__":
    main()
