import re
from typing import Any, Dict, Optional, List, Tuple

__all__ = ["parse_t4_text"]

# Known T4 boxes we care about + a broader set for recognition
T4_BOX_NUMBERS = {
    10, 12, 14, 16, 16_0, 16, 16, 17, 18, 20, 22, 24, 26, 28, 29,
    44, 45, 46, 50, 52, 54, 55, 56,
    57, 58, 59, 60,
    66, 67, 69, 71, 74, 75, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87, 88
}
COVID_PERIOD_BOXES = {57, 58, 59, 60}

# Employer header/label phrases to avoid returning as "employer"
EMPLOYER_BAD_PHRASES = [
    "employment income",
    "income tax deducted",
    "employer's name",
    "nom de l'employeur",
    "year statement of remuneration",
    "statement of remuneration",
    "année état de la rémunération",
    "box–case",
    "amount–montant",
    "revenus d'emploi",
    "impôt sur le revenu retenu",
    "cotisations",
    "gains assurables",
    "t4",
]


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    txt = raw
    txt = re.sub(r"\(cid:\d+\)", " ", txt)
    txt = txt.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt


def _find_data_region(txt: str) -> str:
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


def _looks_like_employer(line: str) -> bool:
    if not line:
        return False
    low = line.lower().strip()

    # reject obvious headers
    for bad in EMPLOYER_BAD_PHRASES:
        if bad in low:
            return False

    # reject mostly-numeric
    if not re.search(r"[A-Za-z]", line):
        return False
    if re.fullmatch(r"[0-9 .,\-/*]+", line):
        return False

    # reject lines that are clearly "box" label text
    if re.search(r"\b(box|case|amount|montant)\b", low):
        return False

    # accept if it looks like a business name
    business_markers = r"\b(ltd|limited|inc|incorporated|corp|corporation|company|co\.|group|services|holdings|enterprises|dba)\b"
    if re.search(business_markers, low, re.IGNORECASE):
        return True

    # accept if title-ish and not too long
    if 4 <= len(line) <= 80 and low.count(" ") <= 10:
        return True

    return False


def _extract_employer(region: str) -> Optional[str]:
    """
    Improved employer extraction:
    - Prefer company-like lines near the first year occurrence.
    - Avoid bilingual header phrases that often appear before the actual employer.
    """
    if not region:
        return None

    lines = [ln.strip() for ln in region.splitlines() if ln.strip()]
    if not lines:
        return None

    # Find first year line index
    year_pat = re.compile(r"\b20\d{2}\b")
    year_idxs = [i for i, ln in enumerate(lines) if year_pat.search(ln)]

    # If we have a year, look around it for an employer candidate
    if year_idxs:
        yi = year_idxs[0]
        # look back up to 8 lines and forward up to 3 lines
        candidate_window = list(range(max(0, yi - 8), yi)) + list(range(yi + 1, min(len(lines), yi + 4)))
        candidates = []
        for j in candidate_window:
            ln = lines[j]
            if _looks_like_employer(ln):
                candidates.append((j, ln))

        # Prefer the closest valid employer line *before* the year line
        prior = [c for c in candidates if c[0] < yi]
        if prior:
            return prior[-1][1]

        # Else choose first valid after the year
        after = [c for c in candidates if c[0] > yi]
        if after:
            return after[0][1]

    # Fallback: first plausible employer line anywhere in first 40 lines
    for ln in lines[:40]:
        if _looks_like_employer(ln):
            return ln

    return None


def _tokenize_numbers(region: str) -> List[str]:
    # Keep both integers and decimals
    return re.findall(r"\d+\.\d{2}|\d+", region or "")


def _as_int(tok: str) -> Optional[int]:
    try:
        return int(tok)
    except Exception:
        return None


def _as_float(tok: str) -> Optional[float]:
    try:
        return float(tok)
    except Exception:
        return None


def _join_int_and_cents(dollars_int: int, cents_token: str) -> Optional[float]:
    if dollars_int is None or cents_token is None:
        return None
    if not (len(cents_token) == 2 and cents_token.isdigit()):
        return None
    return _as_float(f"{dollars_int}.{cents_token}")


def _split_squeezed_int(n: int) -> Optional[float]:
    # 4326667 -> 43266.67
    s = str(n)
    if len(s) < 5:
        return None
    return _as_float(f"{s[:-2]}.{s[-2:]}")


def _scan_box_amounts(tokens: List[str]) -> Tuple[Dict[int, float], List[float]]:
    """
    Parse numeric token stream into:
      - box_map: {box_number: amount}
      - all_amounts: all reconstructed amounts in encountered order
    """
    box_map: Dict[int, float] = {}
    all_amounts: List[float] = []

    i = 0
    while i < len(tokens):
        t = tokens[i]
        ti = _as_int(t)

        # ---- Box-directed parse: <box> <amount> ----
        if ti is not None and ti in T4_BOX_NUMBERS:
            box = ti

            if i + 1 < len(tokens):
                nxt = tokens[i + 1]

                # Already decimal
                if re.fullmatch(r"\d+\.\d{2}", nxt):
                    v = _as_float(nxt)
                    if v is not None:
                        box_map[box] = v
                        all_amounts.append(v)
                        i += 2
                        continue

                # dollars + cents (require dollars >= 100 to avoid "20 46" etc.)
                n2 = _as_int(nxt)
                if n2 is not None and i + 2 < len(tokens):
                    nxt2 = tokens[i + 2]
                    if n2 >= 100 and len(nxt2) == 2 and nxt2.isdigit():
                        v = _join_int_and_cents(n2, nxt2)
                        if v is not None:
                            box_map[box] = v
                            all_amounts.append(v)
                            i += 3
                            continue

                # squeezed
                if n2 is not None:
                    v = _split_squeezed_int(n2)
                    if v is not None:
                        box_map[box] = v
                        all_amounts.append(v)
                        i += 2
                        continue

            i += 1
            continue

        # ---- Free-stream parse: join patterns ----
        if re.fullmatch(r"\d+\.\d{2}", t):
            v = _as_float(t)
            if v is not None:
                all_amounts.append(v)
            i += 1
            continue

        n = ti
        if n is not None and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            nxt_int = _as_int(nxt)

            # Join cents if dollars >= 100
            if n >= 100 and nxt_int is not None and len(nxt) == 2 and nxt.isdigit():
                # If this looks like a "squeezed amount followed by a box number", salvage squeezed and do NOT join.
                # Example: 692308 58 ... should become 6923.08 and "58" remains as a box number.
                if len(str(n)) >= 5 and nxt_int in T4_BOX_NUMBERS:
                    v = _split_squeezed_int(n)
                    if v is not None:
                        all_amounts.append(v)
                    i += 1
                    continue

                # Normal join (this covers EI like 776 75)
                v = _join_int_and_cents(n, nxt)
                if v is not None:
                    all_amounts.append(v)
                    i += 2
                    continue

        # salvage squeezed ints
        if n is not None:
            v = _split_squeezed_int(n)
            if v is not None:
                all_amounts.append(v)

        i += 1

    return box_map, all_amounts


def _find_ei_from_context(region: str) -> Optional[float]:
    """
    Context-based EI extraction:
    Look for "18" near "EI premiums / Cotisations ... AE" and capture the next money-ish value.
    Helps when box scanning misses it.
    """
    if not region:
        return None

    # Normalize "776 75" style into "776.75" temporarily for this context scan
    norm = re.sub(r"\b(\d{3,})\s(\d{2})\b", r"\1.\2", region)

    # Look for patterns referencing box 18 / EI premiums (English/French)
    patterns = [
        r"(?:\b18\b.*?\bEI\b.*?\b(?:premiums|premium)\b).*?(\d+\.\d{2})",
        r"(?:\b18\b.*?\bCotisations\b.*?\bAE\b).*?(\d+\.\d{2})",
        r"(?:\bEI\b.*?\b(?:premiums|premium)\b).*?\b18\b.*?(\d+\.\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, norm, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None


def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    txt = _clean_text(raw_text)
    region = _find_data_region(txt)

    year = _extract_year(region)
    employer = _extract_employer(region)

    tokens = _tokenize_numbers(region)
    box_map, amounts = _scan_box_amounts(tokens)

    # Explicit values if present
    box14 = box_map.get(14)
    box22 = box_map.get(22)
    box16 = box_map.get(16)  # CPP
    box18 = box_map.get(18)  # EI

    # Exclude COVID period values from inference pool
    covid_vals = {box_map[b] for b in COVID_PERIOD_BOXES if b in box_map}
    pool = [a for a in amounts if a not in covid_vals and a is not None]

    # If EI isn't explicitly mapped, try context-based extraction
    if box18 is None:
        box18 = _find_ei_from_context(region)

    # If still missing, only do a conservative EI heuristic
    # (Do NOT pick a tiny fraction of income; prefer plausible EI range.)
    if box18 is None:
        # EI premiums are commonly within ~50 to ~1500, often a few hundred.
        candidates = [a for a in pool if 50.00 <= a <= 2000.00]
        # Avoid values that are equal to CPP or tax if those are known
        if box16 is not None:
            candidates = [a for a in candidates if abs(a - box16) > 0.01]
        if box22 is not None:
            candidates = [a for a in candidates if abs(a - box22) > 0.01]
        box18 = min(candidates) if candidates else None

    # Infer income/tax/cpp only if missing (keep conservative)
    if box14 is None and pool:
        box14 = max(pool)

    if box22 is None and box14 is not None:
        below_income = [a for a in pool if a < box14 - 0.009]
        box22 = max(below_income) if below_income else None

    if box16 is None:
        # CPP tends to be a few thousand; exclude EI range and exclude tax
        cpp_candidates = [a for a in pool if 500.00 <= a <= 10000.00]
        if box18 is not None:
            cpp_candidates = [a for a in cpp_candidates if a > box18 + 0.009]
        if box22 is not None:
            cpp_candidates = [a for a in cpp_candidates if a < box22 - 0.009]
        box16 = max(cpp_candidates) if cpp_candidates else None

    return {
        "doc_type": "T4 Statement of Remuneration",
        "employer": employer,
        "year": year,
        "box_14_income": box14,
        "box_22_tax_deducted": box22,
        "box_16_cpp": box16,
        "box_18_ei": box18,
    }
