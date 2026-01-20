import re
from typing import Any, Dict, Optional, List, Tuple

__all__ = ["parse_t4_text"]

T4_BOX_NUMBERS = {
    10, 12, 14, 16, 17, 18, 20, 22, 24, 26, 28, 29,
    44, 45, 46, 50, 52, 54, 55, 56,
    57, 58, 59, 60,
    66, 67, 69, 71, 74, 75, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87, 88
}

COVID_PERIOD_BOXES = {57, 58, 59, 60}


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


def _extract_employer(region: str) -> Optional[str]:
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
    for ln in lines[:30]:
        low = ln.lower()
        if any(b.lower() in low for b in bad):
            continue
        if not re.search(r"[A-Za-z]", ln):
            continue
        if re.fullmatch(r"[0-9 .,\-]+", ln):
            continue
        return ln
    return None


def _tokenize_numbers(region: str) -> List[str]:
    if not region:
        return []
    return re.findall(r"\d+\.\d{2}|\d+", region)


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
    s = str(n)
    if len(s) < 5:
        return None
    return _as_float(f"{s[:-2]}.{s[-2:]}")


def _scan_box_amounts(tokens: List[str]) -> Tuple[Dict[int, float], List[float]]:
    """
    Produces:
      - box_map: explicit mapping when box numbers are present
      - all_amounts: reconstructed amounts found in order
    """
    box_map: Dict[int, float] = {}
    all_amounts: List[float] = []

    i = 0
    while i < len(tokens):
        t = tokens[i]
        ti = _as_int(t)

        # ---- Box-directed parse ----
        if ti is not None and ti in T4_BOX_NUMBERS:
            box = ti

            if i + 1 < len(tokens):
                nxt = tokens[i + 1]

                # Decimal already
                if re.fullmatch(r"\d+\.\d{2}", nxt):
                    v = _as_float(nxt)
                    if v is not None:
                        box_map[box] = v
                        all_amounts.append(v)
                        i += 2
                        continue

                # dollars + cents (only when dollars >= 100)
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

                # squeezed int >= 5 digits
                if n2 is not None:
                    v = _split_squeezed_int(n2)
                    if v is not None:
                        box_map[box] = v
                        all_amounts.append(v)
                        i += 2
                        continue

            i += 1
            continue

        # ---- Free-stream parse (no explicit box number) ----
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
                # Block only the specific "squeezed + next box" bug (>=5 digits + box number)
                if len(str(n)) >= 5 and nxt_int in T4_BOX_NUMBERS:
                    v = _split_squeezed_int(n)
                    if v is not None:
                        all_amounts.append(v)
                    i += 1
                    continue

                # Allow EI like 776 75
                v = _join_int_and_cents(n, nxt)
                if v is not None:
                    all_amounts.append(v)
                    i += 2
                    continue

        # Salvage squeezed ints in free stream
        if n is not None:
            v = _split_squeezed_int(n)
            if v is not None:
                all_amounts.append(v)

        i += 1

    return box_map, all_amounts


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

    # Exclude COVID period amounts from any inference pool
    covid_vals = {box_map[b] for b in COVID_PERIOD_BOXES if b in box_map}
    pool = [a for a in amounts if a not in covid_vals and a is not None]

    # Infer income/tax/cpp/ei only if missing
    if box14 is None and pool:
        box14 = max(pool)

    if box22 is None and box14 is not None:
        below_income = [a for a in pool if a < box14 - 0.009]
        box22 = max(below_income) if below_income else None

    if box18 is None:
        # EI: typically <= 2000; prefer smallest positive
        small = [a for a in pool if 0 < a <= 2000.00]
        box18 = min(small) if small else None

    if box16 is None:
        # CPP: often a few thousand; keep it under ~10k to avoid box22,
        # and above EI if EI found
        cpp_candidates = [a for a in pool if 500.00 <= a <= 10000.00]
        if box18 is not None:
            cpp_candidates = [a for a in cpp_candidates if a > box18 + 0.009]
        if box22 is not None:
            cpp_candidates = [a for a in cpp_candidates if a < box22 - 0.009]

        # Prefer the largest remaining candidate
        if cpp_candidates:
            box16 = max(cpp_candidates)
        else:
            # fallback: original heuristic
            candidates = [a for a in pool if a > 0]
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
