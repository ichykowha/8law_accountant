import re
from typing import Any, Dict, Optional


# -----------------------------
# Helpers
# -----------------------------

def _clean_text(raw: str) -> str:
    """
    Normalize OCR text to make regex extraction reliable.
    - Removes common OCR artifacts like (cid:123)
    - Normalizes whitespace
    - Converts '43266 67' -> '43266.67' for amounts (only when left side has >=3 digits)
    """
    if not raw:
        return ""

    txt = raw

    # Remove common PDF/OCR artifacts like (cid:379)
    txt = re.sub(r"\(cid:\d+\)", " ", txt)

    # Normalize weird whitespace
    txt = txt.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")

    # Collapse repeated spaces but keep newlines for line-based heuristics
    txt = re.sub(r"[ \t]+", " ", txt)

    # Convert OCR "space-decimals" to decimals:
    # IMPORTANT: only convert when the left side has >=3 digits (avoid converting box numbers like "20 46")
    # Examples: 43266 67 -> 43266.67, 705 26 -> 705.26
    txt = re.sub(r"\b(\d{3,})\s(\d{2})\b", r"\1.\2", txt)

    return txt


def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    try:
        # Remove commas if any
        s2 = s.replace(",", "").strip()
        return float(s2)
    except Exception:
        return None


def _find_data_region(txt: str) -> str:
    """
    Limit parsing to the region that typically contains the employer/year/amounts.
    We cut off at the CRA instructions section ("Report these amounts..." / French equivalent),
    which appears after the data block in your OCR.
    """
    if not txt:
        return ""

    markers = [
        "Report these amounts",
        "Veuillez déclarer ces montants",
        "REV OSP",
        "For Canada Revenue Agency use only",
        "À l'usage de l'Agence du revenu du Canada seulement",
    ]

    cut = len(txt)
    for m in markers:
        idx = txt.find(m)
        if idx != -1:
            cut = min(cut, idx)

    return txt[:cut]


def _extract_year(region: str) -> Optional[int]:
    # Pick the first reasonable year in the region
    m = re.search(r"\b(20\d{2})\b", region)
    if not m:
        return None
    y = int(m.group(1))
    # sanity
    if 2000 <= y <= 2100:
        return y
    return None


def _extract_employer(region: str) -> Optional[str]:
    """
    Attempt to identify employer name from lines near the year / address block.
    Strategy:
    - Consider lines that look like company names (contain Corporation/Ltd/Inc/Company/Corp/etc.)
    - Exclude bilingual header phrases (Année / État / rémunération / etc.)
    - Prefer a company-name line that occurs shortly before a year line.
    """
    if not region:
        return None

    lines = [ln.strip() for ln in region.splitlines() if ln.strip()]
    if not lines:
        return None

    # Exclusions (header noise)
    bad_fragments = [
        "Année", "État", "rémunération", "payée",
        "Employer's name", "Nom de l'employeur",
        "Year Statement", "Statement of Remuneration",
        "T4", "Box–Case", "Amount–Montant",
    ]

    company_markers = r"(Corporation|Corp\.?|Company|Co\.?|Limited|Ltd\.?|Incorporated|Inc\.?|LLC|LP|Partners|Partnership)"
    year_pat = re.compile(r"\b20\d{2}\b")

    # Find indices of year lines
    year_idxs = [i for i, ln in enumerate(lines) if year_pat.search(ln)]
    if not year_idxs:
        # fallback: pick first plausible company line anywhere
        for ln in lines:
            if re.search(company_markers, ln, re.IGNORECASE):
                if not any(b.lower() in ln.lower() for b in bad_fragments):
                    return ln
        return None

    # For each year occurrence, look back a few lines for employer
    for yi in year_idxs:
        lookback = range(max(0, yi - 5), yi)
        candidates = []
        for j in lookback:
            ln = lines[j]
            if any(b.lower() in ln.lower() for b in bad_fragments):
                continue
            # Must be mostly letters/spaces/punctuation and not just numeric
            if re.search(company_markers, ln, re.IGNORECASE) or (len(ln) >= 6 and re.search(r"[A-Za-z]", ln)):
                # Avoid lines that are clearly box/label content
                if re.search(r"\b(Box|Case|Amount|Montant|Employment income|Income tax deducted)\b", ln, re.IGNORECASE):
                    continue
                candidates.append(ln)

        # Prefer the closest candidate to the year
        if candidates:
            return candidates[-1]

    # fallback: any company marker line
    for ln in lines:
        if re.search(company_markers, ln, re.IGNORECASE):
            if not any(b.lower() in ln.lower() for b in bad_fragments):
                return ln

    return None


def _extract_amounts(region: str) -> list[float]:
    """
    Extract all decimal amounts in the region (after space-decimal normalization).
    We keep only values that look like money amounts with 2 decimals.
    """
    if not region:
        return []

    # Money/amount pattern: 1,234.56 or 1234.56
    matches = re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b", region)
    amounts = []
    for m in matches:
        v = _to_float(m)
        if v is None:
            continue
        amounts.append(v)
    return amounts


# -----------------------------
# Public API
# -----------------------------

def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    """
    Parse OCR'd T4 text and extract key fields.

    Returns keys compatible with your frontend:
      - doc_type
      - employer
      - year
      - box_14_income
      - box_22_tax_deducted
      - box_16_cpp
      - box_18_ei
    """
    txt = _clean_text(raw_text)
    region = _find_data_region(txt)

    year = _extract_year(region)
    employer = _extract_employer(region)

    # Extract amounts from the data region.
    # In your sample, the first three meaningful amounts are:
    #   box14, box22, box16
    # EI premium typically appears later and is usually <= ~2000 (often <= ~1200 in many years).
    amounts = _extract_amounts(region)

    box14 = amounts[0] if len(amounts) >= 1 else None
    box22 = amounts[1] if len(amounts) >= 2 else None
    box16 = amounts[2] if len(amounts) >= 3 else None

    # EI: choose the first "smallish" amount after CPP.
    # We avoid grabbing huge values like insurable earnings (often same as box14).
    box18 = None
    if len(amounts) >= 4:
        for v in amounts[3:]:
            if v <= 2000.00 and v > 0:
                # avoid re-selecting CPP if duplicated
                if box16 is not None and abs(v - box16) < 0.01:
                    continue
                box18 = v
                break

    return {
        "doc_type": "T4 Statement of Remuneration",
        "employer": employer,
        "year": year,
        "box_14_income": box14,
        "box_22_tax_deducted": box22,
        "box_16_cpp": box16,
        "box_18_ei": box18,
    }
