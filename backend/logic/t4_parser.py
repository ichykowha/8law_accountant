import re
from typing import Any, Dict, Optional, List, Tuple

__all__ = ["parse_t4_text"]


def _clean_text(raw: str) -> str:
    if not raw:
        return ""

    txt = raw

    txt = re.sub(r"\(cid:\d+\)", " ", txt)
    txt = txt.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[ \t]+", " ", txt)

    # Convert OCR "space-decimals" even across newlines: 705\n26 -> 705.26
    txt = re.sub(r"\b(\d{3,})[ \t\n]+(\d{2})\b", r"\1.\2", txt)

    return txt


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "").strip())
    except Exception:
        return None


def _split_into_blocks(txt: str) -> List[str]:
    if not txt:
        return []

    cut_markers = [
        "Report these amounts",
        "Veuillez déclarer ces montants",
        "For Canada Revenue Agency use only",
        "À l'usage de l'Agence du revenu du Canada seulement",
    ]

    cut = len(txt)
    for m in cut_markers:
        idx = txt.find(m)
        if idx != -1:
            cut = min(cut, idx)
    txt = txt[:cut]

    parts = re.split(r"\n\s*T4\s*\n", txt, flags=re.IGNORECASE)
    blocks = []
    for p in parts:
        p = p.strip()
        if len(p) >= 200:
            blocks.append(p)

    return blocks if blocks else [txt.strip()]


def _extract_year(txt: str) -> Optional[int]:
    m = re.search(r"\b(20\d{2})\b", txt)
    if not m:
        return None
    y = int(m.group(1))
    return y if 2000 <= y <= 2100 else None


def _extract_employer(txt: str) -> Optional[str]:
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

    best_score = -1
    best_line = None

    for i, ln in enumerate(lines):
        low = ln.lower()

        if any(b.lower() in low for b in bad_fragments):
            continue
        if not re.search(r"[A-Za-z]", ln):
            continue
        if re.fullmatch(r"[0-9 .,\-]+", ln):
            continue

        score = 0
        if company_markers.search(ln):
            score += 10
        if len(ln) >= 6:
            score += 2

        window = "\n".join(lines[i:i + 7])
        if re.search(r"\b20\d{2}\b", window):
            score += 4

        if re.search(r"\b(PO BOX|BOX|ST|AVE|RD|BLVD|BC|AB|ON|QC|MB|SK|NS|NB|NL|NT|NU|YT)\b", window, re.IGNORECASE):
            score += 2

        if score > best_score:
            best_score = score
            best_line = ln

    return best_line


def _extract_amounts(txt: str) -> List[float]:
    if not txt:
        return []
    matches = re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b", txt)
    out: List[float] = []
    for m in matches:
        v = _to_float(m)
        if v is not None:
            out.append(v)
    return out


def _choose_best_block(blocks: List[str]) -> str:
    best_score = -1
    best_block = blocks[0] if blocks else ""

    for b in blocks:
        year = _extract_year(b)
        employer = _extract_employer(b)
        amounts = _extract_amounts(b)

        score = 0
        if year:
            score += 5
        score += min(len(amounts), 20)
        if employer:
            score += 8

        if score > best_score:
            best_score = score
            best_block = b

    return best_block


def _extract_core_boxes_from_amounts(amounts: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    if not amounts:
        return None, None, None, None

    uniq = sorted(set(round(a, 2) for a in amounts))
    if not uniq:
        return None, None, None, None

    box14 = max(uniq)

    below_income = [a for a in uniq if a < box14 - 0.009]
    box22 = max(below_income) if below_income else None

    small = [a for a in uniq if 0 < a <= 2000.00]
    box18 = min(small) if small else None

    candidates = [a for a in uniq if a > 0]
    if box22 is not None:
        candidates = [a for a in candidates if a < box22 - 0.009]
    if box18 is not None:
        candidates = [a for a in candidates if a > box18 + 0.009]

    box16 = max(candidates) if candidates else None

    return box14, box22, box16, box18


def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    txt = _clean_text(raw_text)
    blocks = _split_into_blocks(txt)
    best = _choose_best_block(blocks)

    year = _extract_year(best)
    employer = _extract_employer(best)

    amounts = _extract_amounts(best)
    box14, box22, box16, box18 = _extract_core_boxes_from_amounts(amounts)

    return {
        "doc_type": "T4 Statement of Remuneration",
        "employer": employer,
        "year": year,
        "box_14_income": box14,
        "box_22_tax_deducted": box22,
        "box_16_cpp": box16,
        "box_18_ei": box18,
    }
