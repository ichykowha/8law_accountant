from __future__ import annotations

from typing import Dict, Tuple


def detect_doc_type(raw_text: str) -> Tuple[str, Dict[str, float]]:
    """
    Lightweight classifier for routing OCR text to the right parser.
    Returns: (doc_type, scores)

    doc_type: "t4" | "invoice" | "unknown"
    scores:  simple weighted keyword evidence
    """
    t = (raw_text or "").lower()

    # T4 signals
    t4_terms = [
        ("t4", 2.0),
        ("statement of remuneration paid", 3.0),
        ("box 14", 3.0),
        ("employment income", 2.5),
        ("income tax deducted", 2.5),
        ("cpp contributions", 2.0),
        ("ei premiums", 2.0),
        ("sin", 1.5),
    ]

    # Invoice signals
    inv_terms = [
        ("invoice", 2.0),
        ("facture", 2.0),
        ("invoice #", 3.0),
        ("total payable", 3.0),
        ("total à payer", 3.0),
        ("sold by", 2.0),
        ("vendu par", 2.0),
        ("order #", 2.0),
        ("gst/hst", 2.0),
        ("pst", 2.0),
        ("subtotal", 1.5),
        ("quantity", 1.0),
        ("unit", 0.5),
        ("shipping charges", 1.0),
    ]

    t4_score = 0.0
    inv_score = 0.0

    for term, w in t4_terms:
        if term in t:
            t4_score += w

    for term, w in inv_terms:
        if term in t:
            inv_score += w

    scores = {"t4": round(t4_score, 2), "invoice": round(inv_score, 2)}

    # Decision policy:
    # - Require a minimum signal to avoid false positives
    if t4_score >= 4.0 and t4_score > inv_score:
        return "t4", scores
    if inv_score >= 4.0 and inv_score > t4_score:
        return "invoice", scores

    return "unknown", scores
