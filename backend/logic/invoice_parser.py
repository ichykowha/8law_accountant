import re
from typing import Any, Dict, Optional

def _find(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None

def parse_invoice_text(text: str) -> Dict[str, Any]:
    t = text or ""

    invoice_no = _find(r"Invoice\s*#\s*/\s*#\s*de\s*facture:\s*([A-Z0-9\-]+)", t) or _find(r"Invoice\s*#\s*[:#]?\s*([A-Z0-9\-]+)", t)
    invoice_date = _find(r"Invoice\s*date.*?:\s*([0-9]{2}\s+[A-Za-z]+\s+[0-9]{4})", t)
    order_no = _find(r"Order\s*#.*?:\s*([0-9\-]+)", t)
    total_payable = _find(r"Total\s*payable.*?:\s*\$([0-9]+\.[0-9]{2})", t)

    gst = _find(r"\[GST/HST.*?\]\s*\$([0-9]+\.[0-9]{2})", t)
    pst = _find(r"\[PST/RST/QST.*?\]\s*\$([0-9]+\.[0-9]{2})", t)

    vendor = _find(r"Sold\s+by\s*/\s*Vendu\s+par:\s*(.+)", t)

    return {
        "doc_type": "invoice",
        "vendor": vendor,
        "invoice_number": invoice_no,
        "invoice_date": invoice_date,
        "order_number": order_no,
        "total_payable": total_payable,
        "gst_hst": gst,
        "pst": pst,
        "raw_excerpt": t[:1000],  # optional debugging
    }
