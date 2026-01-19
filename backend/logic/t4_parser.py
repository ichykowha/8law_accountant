import re
from typing import Any, Dict, Optional, List, Tuple


# -----------------------------
# Helpers
# -----------------------------

def _clean_text(raw: str) -> str:
    """
    Normalize OCR text to make extraction reliable.
    - Removes common OCR artifacts like (cid:123)
    - Normalizes whitespace
    - Converts '43266 67' (even across newlines/tabs) -> '43266.67' for amounts
      (only when left side has >=3 digits to avoid converting box numbers like "20 46")
    """
    if not raw:
        return ""

    txt = raw

    # Remove common PDF/OCR artifacts like (cid:379)
    txt = re.sub(r"\(cid:\d+\)", " ", txt)

    # Normalize weird whitespace characters
    txt = txt.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")

    # Normalize line endings
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse runs of spaces/tabs (keep newlines)
    txt = re.sub(r"[ \t]+", " ", txt)

    # Convert OCR "space-decimals" to decimals across ANY whitespace (space/tab/newline)
    # Examples: 43266 67 -> 43266.67, 705\n26 -> 705.26
    txt = re.sub(r"\b(\d{3,})[ \t\n]+(\d{2})\b", r"\1.\2", txt)

    return txt


def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    try:
        s2 = s.replace(",", "").strip()
        return float(s2)
    except Exception:
        return None


def _split_into_blocks(txt: str) -> List[str]:
    """
    OCR often repeats the full T4 template twice and includes a CRA instruction section.
    We split into blocks so we can select the most "data-rich" issuer block.
    """
    if not txt:
        return []

    # Common cut markers that begin instructions (usually after the issuer data block)
    cut_markers = [
        "Report these amounts",
        "Veuillez déclarer ces montants",
        "For Canada Revenue Agency use only",
        "À l'usage de l'Agence du revenu du Canada seulement",
    ]

    # Cut off instruction tail to reduce noise
    cut = len(txt)
    for m in cut_markers:
        idx = txt.find(m)
        if idx != -1:
            cut = min(cut, idx)
    txt = txt[:cut]

    # Split on repeated "T4" headers to isolate repeated template sections.
    # Keep blocks reasonably large.
    parts = re.split(r"\n\s*T4\s*\n", txt, flags=re.IGNORECASE)
    blocks = []
    for p in parts:
        p = p.strip()
        if len(p) >= 200:
            blocks.append(p)

    # If split didn't work, treat whole as one block
    return blocks if blocks else [txt.strip()]


def _extract_year(txt: str) -> Optional[int]:
    m = re.search(r"\b(20\d{2})\b", txt)
    if not m:
        return None
    y = int(m.group(1))
    return y if 2000 <= y <= 2100 else None


def _extract_employer(txt: str) -> Optional[str]:
    """
    Prefer a line that:
    - looks like a company name,
    - is not a bilingual header,
    - and appears near a year/address region.
    We also strongly prefer lines containing company markers.
    """
    if not txt:
        return None

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return None

    bad_fragments = [
        "Année", "État", "rémunération", "payée",
        "Employer's name", "Nom de l'employeur",
        "Year Statement", "Statement of Remuneration",
        "Employment income", "Income tax deducted",
        "Employee's CPP", "Employee's EI premiums",
        "Box–Case", "Amount–Montant",
        "Privacy Act", "Loi sur la protection",
        "Report these amounts", "Veuillez déclarer",
    ]

    company_markers = re.compile(
        r"(Corporation|Corp\.?|Company|Co\.?|Limited|Ltd\.?|Incorporated|Inc\.?|LLC|LP|Partners|Partnership)",
        re.IGNORECASE
    )

    # Score each line; pick the best-scoring employer-like line.
    best: Tuple[int, Optional[str]] = (0, None)

    for i, ln in enumerate(lines):
        low = ln.lower()

        if any(b.lower() in low for b in bad_fragments):
            continue

        # Must contain letters
        if not re.search(r"[A-Za-z]", ln):
            continue

        # Avoid lines that are mostly numeric or look like addresses alone
        if re.fullmatch(r"[0-9 .,\-]+", ln):
            continue

        score = 0

        # Company marker gets strong weight
        if company_markers.search(ln):
            score += 10
