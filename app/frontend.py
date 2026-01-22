# app/frontend.py
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
from app.client_gate import require_client_selected


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

    # Always compute suggested type for debugging, but only *use* it when requested_doc_type == "auto"
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
    """
    Runs lightweight diagnostics that should work in Streamlit Cloud:
    - backend imports
    - T1DecisionEngine calculation sanity check
    - T4 parser sanity check with bundled sample text (no OCR)
    - OCR dependency validation (python imports + tesseract binary presence/version)
    - Doc classifier sanity check
    - Invoice parser sanity check
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
        dep_checks = {}
        for mod in ["PIL", "pytesseract", "pdfplumber", "pypdf", "pypdfium2"]:
            ok, msg = _safe_import(mod)
            dep_checks[mod] = {"ok": ok, "details": msg}

        tesseract_path = shutil.which("tesseract")
        if not tesse
