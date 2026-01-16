# ------------------------------------------------------------------------------
# 8law - T4 Parser
# Module: T4 Tax Slip Extraction Logic
# File: backend/logic/t4_parser.py
# ------------------------------------------------------------------------------
import re
from decimal import Decimal
from typing import Dict, Any, Optional

def clean_money(value: str) -> Optional[float]:
    """
    Removes symbols ($, commas) and converts '50,000.00' to a float number.
    Returns None if the value isn't a valid number.
    """
    if not value:
        return None
    # Remove $ and , and whitespace
    clean = re.sub(r'[^\d.]', '', value)
    try:
        return float(clean)
    except ValueError:
        return None

def parse_t4_text(raw_text: str) -> Dict[str, Any]:
    """
    Analyzes raw text from a T4 PDF and extracts key financial fields.
    """
    data = {
        "doc_type": "T4 Statement of Remuneration",
        "employer": None,
        "box_14_income": None,
        "box_22_tax_deducted": None,
        "box_16_cpp": None,
        "box_18_ei": None
    }

    # --- 1. Find Box 14 (Employment Income) ---
    # Regex looks for "14" followed by a number, potentially with $ or commas
    # This pattern catches: "14 65,000.00" or "Box 14 $65000.50"
    match_14 = re.search(r'(?:Box|Case)?\s*14\s+.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', raw_text, re.IGNORECASE)
    if match_14:
        data["box_14_income"] = clean_money(match_14.group(1))

    # --- 2. Find Box 22 (Income Tax Deducted) ---
    match_22 = re.search(r'(?:Box|Case)?\s*22\s+.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', raw_text, re.IGNORECASE)
    if match_22:
        data["box_22_tax_deducted"] = clean_money(match_22.group(1))

    # --- 3. Find Box 16 (CPP Contributions) ---
    match_16 = re.search(r'(?:Box|Case)?\s*16\s+.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', raw_text, re.IGNORECASE)
    if match_16:
        data["box_16_cpp"] = clean_money(match_16.group(1))
        
    # --- 4. Find Box 18 (EI Premiums) ---
    match_18 = re.search(r'(?:Box|Case)?\s*18\s+.*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', raw_text, re.IGNORECASE)
    if match_18:
        data["box_18_ei"] = clean_money(match_18.group(1))

    # --- 5. Guess Employer Name (Experimental) ---
    # Usually the first line that isn't a form label
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    for line in lines[:5]: # Check first 5 lines
        if "T4" not in line and "Statement" not in line and len(line) > 3:
            data["employer"] = line
            break
            
    return data