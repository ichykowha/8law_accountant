from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_MONEY_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))")
_DATE_RE = re.compile(r"(?:invoice date|date de facturation)\s*:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", re.I)
_INVNO_RE = re.compile(r"(?:invoice\s*#|#\s*de\s*facture)\s*[:/]*\s*([A-Z0-9\-]+)", re.I)
_TOTAL_PAYABLE_RE = re.compile(r"(?:total payable|total à payer)\s*[:/]*\s*\$?\s*([0-9,]+\.[0-9]{2})", re.I)
_SOLD_BY_RE = re.compile(r"(?:sold by|vendu par)\s*[:/]*\s*(.+)", re.I)
_GSTNO_RE = re.compile(r"(?:gst/hst\s*#|#\s*de\s*tps/tvh)\s*[:/]*\s*([A-Z0-9 \-]+)", re.I)
_PSTNO_RE = re.compile(r"(?:pst\s*#|#\s*de\s*tvp)\s*[:/]*\s*([A-Z0-9 \-]+)", re.I)


def _money_to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s.replace(",", "").strip())
    except Exception:
        return None


def parse_invoice_text(raw_text: str) -> Dict[str, Any]:
    """
    Parse invoice-like OCR text into a structured dict.
    This is intentionally conservative: it pulls reliable header fields + totals,
    and optionally attempts to extract a small item list if patterns are present.
    """
    text = (raw_text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    invoice_date = None
    m = _DATE_RE.search(text)
    if m:
        invoice_date = m.group(1).strip()

    invoice_number = None
    m = _INVNO_RE.search(text)
    if m:
        invoice_number = m.group(1).strip()

    total_payable = None
    m = _TOTAL_PAYABLE_RE.search(text)
    if m:
        total_payable = _money_to_float(m.group(1))

    sold_by = None
    m = _SOLD_BY_RE.search(text)
    if m:
        sold_by = m.group(1).strip()
        # OCR sometimes captures too much; truncate at common separators
        sold_by = sold_by.split("Invoice")[0].strip()

    gst_hst_number = None
    m = _GSTNO_RE.search(text)
    if m:
        gst_hst_number = m.group(1).strip()

    pst_number = None
    m = _PSTNO_RE.search(text)
    if m:
        pst_number = m.group(1).strip()

    # Attempt to extract GST/HST and PST monetary amounts.
    # In Amazon invoices, item lines often show ... GST ... PST ... item subtotal
    # We'll attempt best-effort capture by looking for a "Total" line with multiple currency figures.
    gst_hst_amount = None
    pst_amount = None

    for ln in reversed(lines):
        if ln.lower().startswith("total "):
            amounts = [a.group(1) for a in _MONEY_RE.finditer(ln)]
            floats = [_money_to_float(x) for x in amounts]
            floats = [f for f in floats if f is not None]
            # Heuristic: line like "Total $24.55 -$0.74 $1.19 $1.67 $2.86"
            # Choose the last two small-ish positive values as gst/pst when present.
            positives = [f for f in floats if f >= 0]
            if len(positives) >= 2:
                # Best guess: GST then PST appear near the end for these layouts
                gst_hst_amount = positives[-2]
                pst_amount = positives[-1]
            break

    # Best-effort item extraction: capture lines that look like:
    # "<description> ... $<amount>"
    items: List[Dict[str, Any]] = []
    for ln in lines:
        if "asin:" in ln.lower():
            # Keep ASIN line as metadata, skip as item itself
            continue
        if "$" in ln and len(ln) > 20:
            m = _MONEY_RE.search(ln)
            if m:
                amt = _money_to_float(m.group(1))
                if amt is not None:
                    # strip trailing amount from description
                    desc = ln[: m.start()].strip(" -:\t")
                    if desc and len(desc) >= 6:
                        items.append({"description": desc[:200], "amount": amt})
        if len(items) >= 15:
            break

    return {
        "doc_type": "invoice",
        "invoice_date": invoice_date,
        "invoice_number": invoice_number,
        "total_payable": total_payable,
        "sold_by": sold_by,
        "gst_hst_number": gst_hst_number,
        "pst_number": pst_number,
        "gst_hst_amount": gst_hst_amount,
        "pst_amount": pst_amount,
        "items": items,
    }
