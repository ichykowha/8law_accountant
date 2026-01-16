# ------------------------------------------------------------------------------
# 8law - OCR Engine
# Module: PDF Text Extractor
# File: backend/logic/ocr_engine.py
# ------------------------------------------------------------------------------
import pdfplumber
import io

def scan_pdf(file_bytes: bytes) -> dict:
    """
    Scans a PDF and returns the raw text found on every page.
    """
    full_text = ""
    page_count = 0
    
    # We wrap the bytes in a virtual file so pdfplumber can read it
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            # Extract text and add a newline to separate blocks
            extracted = page.extract_text()
            if extracted:
                full_text += extracted + "\n"
                
    return {
        "status": "success",
        "pages_scanned": page_count,
        "raw_text": full_text
    }