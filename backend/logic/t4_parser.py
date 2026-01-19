# ------------------------------------------------------------------------------
# 8law - T4 Parser (Advanced)
# Module: T4 Tax Slip Extraction Logic
# File: backend/logic/t4_parser.py
# ------------------------------------------------------------------------------
import re
from typing import Dict, Any, Optional

def clean_money_space_aware(value: str) -> Optional[float]:
    """
    Converts '43266 67' -> 43266.67
    Converts '5,884.76' -> 5884.76
    """
    if not value:
        return None
    
    # 1. Standardize: Remove $ and commas
    clean = re.sub(r'[$,]', '', value.strip())
    
    # 2. Check for "Space Decimal" format (Digits SPACE TwoDigits)
    # e.g. "43266 67" -> "43266.67"
    space_decimal_match = re.match(r'^(\d+)\s(\d{2})$', clean)
    if space_decimal_match:
        whole = space_decimal_match.group(1)
        cents = space_decimal_match.group(2)
        return float(f"{whole}.{cents}")
        
    # 3. Standard Float conversion
    try:
        return float(clean)
    except ValueError:
        return None

def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    """
    Analyzes raw text from a T4 PDF (Space-Separated Format).
    """
    data = {
        "doc_type": "T4 Statement of Remuneration",
        "employer": "Unknown Employer",
        "box_14_income": None,
        "box_22_tax_deducted": None,
        "box_16_cpp": None,
        "year": None
    }

    # --- 1. Find Employer (First non-empty line usually) ---
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    for line in lines:
        # Ignore form labels
        if "T4" not in line and "Statement" not in line and "Employer" not in line:
            # If it looks like a name (LAZ Fishing...), take it
            if len(line) > 3:
                data["employer"] = line
                break
    
    # --- 2. Find Year ---
    year_match = re.search(r'\b(20\d{2})\b', raw_text)
    if year_match:
        data["year"] = int(year_match.group(1))

    # --- 3. The "Collapsed Line" Strategy ---
    # Look for the pattern: "Zip Code" followed by "Amount 1" and "Amount 2"
    # Pattern: Postal Code (L#L #L#) + Space + Digits Space Digits + Space + Digits Space Digits
    # Matches: "V0R 2Z0 43266 67 5884 76"
    collapsed_regex = r'[A-Z]\d[A-Z]\s?\d[A-Z]\d\s+(\d+\s\d{2})\s+(\d+\s\d{2})'
    
    match_collapsed = re.search(collapsed_regex, raw_text)
    if match_collapsed:
        # We found the magic line!
        inc_str = match_collapsed.group(1) # 43266 67
        tax_str = match_collapsed.group(2) # 5884 76
        
        data["box_14_income"] = clean_money_space_aware(inc_str)
        data["box_22_tax_deducted"] = clean_money_space_aware(tax_str)

    # --- 4. Fallback: Search for CPP (Box 16) ---
    # CPP usually appears as a standalone number like "2366 12"
    # We look for a line with exactly that format near "CPP" or just isolated
    # In your dump, "2366 12" is on its own line after a "1".
    cpp_candidates = re.findall(r'\n(\d{3,4}\s\d{2})\n', raw_text)
    if cpp_candidates:
        # The first small-ish number is usually CPP or EI. 
        # CPP (Box 16) is usually larger than EI (Box 18).
        # We'll take the first candidate as CPP for now.
        data["box_16_cpp"] = clean_money_space_aware(cpp_candidates[0])

    return data