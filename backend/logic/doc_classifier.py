import re
from typing import Literal, Tuple

DocType = Literal["t4", "invoice", "noa", "unknown"]

_T4_SIGNALS = [
    r"\bT4\b",
    r"Statement of Remuneration Paid",
    r"État de la rémunération payée",
    r"\bBox\s*14\b",
    r"\bBox\s*22\b",
    r"\bEmployment income\b",
]

_INVOICE_SIGNALS = [
    r"\bInvoice\b",
    r"\bFacture\b",
    r"\bInvoice\s*#\b",
    r"\bOrder\s*#\b",
    r"\bTotal payable\b",
    r"\bAmount due\b",
    r"\bGST/HST\b",
    r"\bPST\b",
    r"\bSold by\b",
    r"\bItem subtotal\b",
]

_NOA_SIGNALS = [
    r"Notice of Assessment",
    r"Avis de cotisation",
]

def _score(text: str, patterns: list[str]) -> int:
    t = text or ""
    score = 0
    for p in patterns:
        if re.search(p, t, flags=re.IGNORECASE):
            score += 1
    return score

def detect_doc_type(text: str) -> Tuple[DocType, dict]:
    t4 = _score(text, _T4_SIGNALS)
    inv = _score(text, _INVOICE_SIGNALS)
    noa = _score(text, _NOA_SIGNALS)

    # Simple winner-takes-most logic with tie-breaking
    if inv >= 2 and inv >= t4 + 1 and inv >= noa + 1:
        return "invoice", {"t4": t4, "invoice": inv, "noa": noa}
    if t4 >= 2 and t4 >= inv + 1 and t4 >= noa + 1:
        return "t4", {"t4": t4, "invoice": inv, "noa": noa}
    if noa >= 2 and noa >= inv + 1 and noa >= t4 + 1:
        return "noa", {"t4": t4, "invoice": inv, "noa": noa}

    return "unknown", {"t4": t4, "invoice": inv, "noa": noa}
