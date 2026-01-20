import re
from typing import Any, Dict, Optional, List, Tuple

__all__ = ["parse_t4_text"]

# Common T4 box numbers that appear in OCR output.
# Used to prevent mis-reading box numbers as cents.
T4_BOX_NUMBERS = {
    10, 12, 14, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16,
    16, 16, 16, 16,  # harmless repetition, kept simple
    16, 17, 18, 20, 22, 24, 26, 28, 29,
    44, 45, 46, 50, 52, 54, 55, 56,
    57, 58, 59, 60,
    66, 67, 69, 71, 74, 75, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87, 88
}


def _clean_text(raw: str) -> str:
    """
    Normalize OCR text WITHOUT globally converting "space decimals".
    That conversion is now done safely during token parsing to avoid
    mistakes like "692308 58" (where 58 is a box number, not cents).
    """
    if not raw:
        return ""

    txt = raw
    txt = re.sub(r"\(cid:\d+\)", " ", txt)
    txt = txt.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt


def _find_data_region(txt: str) -> str:
    """
    Cut off before CRA instruction blocks (keeps the data area).
    """
    if not txt:
        return ""

    markers = [
        "Report these amounts",
        "Veuillez déclarer ces montants",
        "For Canada Revenue Agency use only",
        "À l'usage de l'Agence du revenu du Canada seulement",
        "REV OSP",
    ]

    cut = len(txt)
    for m in markers:
        idx = txt.find(m)
        if idx != -1:
            cut = min(cut, idx)

    return txt[:cut]


def _extract_year(region: str) -> Optional[int]:
    m = re.search(r"\b(20\d{2})\b", region)
    if not m:
        return None
    y = int(m.group(1))
    return y if 2000 <= y <= 2100 else None


def _extract_employer(region: str) -> Optional[str]:
    """
    Heuristic employer extraction: pick the first non-empty line
    that looks like a company name and is not a header phrase.
    """
    if not region:
        return None

    lines = [ln.strip() for ln in region.splitlines() if ln.strip()]
    if not lines:
        return None

    bad = [
        "T4",
        "Employer's name", "Nom de l'employeur",
        "Year Statement", "Statement of Remuneration",
        "Année", "État", "rémunération", "payée",
        "Box", "Case", "Amount", "Montant",
    ]

    for ln in lines[:25]:
        low = ln.lower()
        if any(b.lower() in low for b in bad):
            continue
        # must contain letters and not be mostly numeric
        if not re.search(r"[A-Za-z]", ln):
            continue
        if re.fullmatch(r"[0-9 .,\-]+", ln):
            continue
        return ln

    return None


def _tokenize_numbers(region: str) -> List[str]:
    """
    Extract numeric tokens from region:
    - integers (e.g., 692308)
    - decimals (e.g., 49155.13)
    We intentionally ignore commas here; OCR rarely includes them.
    """
    if not region:
        return []
    return re.findall(r"\d+\.\d{2}|\d+", region)


def _as_int(token: str) -> Optional[int]:
    try:
        return int(token)
    except Exception:
        return None


def _as_float(token: str) -> Optional[float]:
    try:
        return float(token)
    except Exception:
        return None


def _reconstruct_amounts(tokens: List[str]) -> List[float]:
    """
    Convert tokens into monetary amounts.

    Rules:
    - If token is already X.YY -> amount
    - If token is large integer and next token is 2 digits:
        - If next token is a known T4 box number -> do NOT treat as cents.
          Instead, if the integer has >=5 digits, split last 2 digits as cents.
          Example: 692308 + next box 58 => 6923.08
        - Otherwise treat as cents: 49155 13 => 49155.13
    - Otherwise ignore token (to avoid turning every box number into money).
    """
    out: List[float] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]

        # Already a decimal amount
        if re.fullmatch(r"\d+\.\d{2}", t):
            v = _as_float(t)
            if v is not None:
                out.append(v)
            i += 1
            continue

        # Integer token
        n = _as_int(t)
        if n is None:
            i += 1
            continue

        # Consider "split decimals": N + (two-digit token)
        if i + 1 < len(tokens):
            nxt = tokens[i + 1]
            nxt_int = _as_int(nxt)

            # nxt must be 2 digits to be "cents candidate"
            if nxt_int is not None and 0 <= nxt_int <= 99 and len(nxt) == 2:
                # If nxt is actually a box number, do NOT treat as cents.
                if nxt_int in T4_BOX_NUMBERS:
                    # Try salvage: split last 2 digits of current integer as cents
                    # Only if it looks like it was squeezed (>= 5 digits).
                    s = str(n)
                    if len(s) >= 5:
                        dollars = s[:-2]
                        cents = s[-2:]
                        v = _as_float(f"{dollars}.{cents}")
                        if v is not None:
                            out.append(v)
                    i += 1
                    continue

                # Normal case: treat nxt as cents
                v = _as_float(f"{n}.{nxt}")
                if v is not None:
                    out.append(v)
                i += 2
                continue

        # If no usable pairing, try salvage squeezed integer like 692308 (-> 6923.08)
        s = str(n)
        if len(s) >= 5:
            dollars = s[:-2]
            cents = s[-2:]
            v = _as_float(f"{dollars}.{cents}")
            if v is not None:
                out.append(v)

        i += 1

    return out


def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    txt = _clean_text(raw_text)
    region = _find_data_region(txt)

    year = _extract_year(region)
    employer = _extract_employer(region)

    # Reconstruct monetary values safely
    tokens = _tokenize_numbers(region)
    amounts = _reconstruct_amounts(tokens)

    # If your OCR includes 57–60 blocks, exclude those from being treated as box14 candidates.
    # This prevents the "COVID-period boxes" from being mistaken as total employment income.
    # Practical heuristic: throw away amounts that appear immediately after tokens 57/58/59/60.
    # (We keep it simple by excluding any "very large" amount that looks like a box join artifact.)
    safe_amounts = [a for a in amounts if a < 300000.00]  # keeps typical T4 ranges sane
    if not safe_amounts:
        safe_amounts = amounts

    # Core fields heuristic:
    # - box14 (income): largest "safe" amount
    # - box22: next largest below income
    # - box18 (EI): smallest positive <= 2000
    # - box16 (CPP): largest positive below box22 (and above box18 if present)
    box14 = max(safe_amounts) if safe_amounts else None

    below_income = [a for a in safe_amounts if box14 is not None and a < box14 - 0.009]
    box22 = max(below_income) if below_income else None

    small = [a for a in safe_amounts if 0 < a <= 2000.00]
    box18 = min(small) if small else None

    candidates = [a for a in safe_amounts if a > 0]
    if box22 is not None:
        candidates = [a for a in candidates if a < box22 - 0.009]
    if box18 is not None:
        candidates = [a for a in candidates if a > box18 + 0.009]
    box16 = max(candidates) if candidates else None

    return {
        "doc_type": "T4 Statement of Remuneration",
        "employer": employer,
        "year": year,
        "box_14_income": box14,
        "box_22_tax_deducted": box22,
        "box_16_cpp": box16,
        "box_18_ei": box18,
    }
