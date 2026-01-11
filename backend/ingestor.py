import pytesseract
import platform

# WINDOWS CONFIGURATION
if platform.system() == "Windows":
    # If you installed Tesseract in the default location:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
import pandas as pd
import json
import os
from datetime import datetime
try:
    from PIL import Image
    import pytesseract # Requires Tesseract installed on system
except ImportError:
    Image = None

class UniversalIngestor:
    def __init__(self, memory_module):
        self.memory = memory_module # Connect to the database
        self.supported_exts = ['.csv', '.xlsx', '.json', '.png', '.jpg']

    def ingest_file(self, file_path):
        """Identifies file type and routes to the correct parser."""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == '.json':
            return self._parse_json(file_path)
        elif ext in ['.xlsx', '.csv']:
            return self._parse_spreadsheet(file_path)
        elif ext in ['.png', '.jpg', '.jpeg']:
            return self._parse_image(file_path)
        else:
            return f"Error: Unsupported format {ext}"

    def _parse_spreadsheet(self, file_path):
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Normalize columns
            df.columns = [c.lower() for c in df.columns]
            
            # Save to memory
            count = 0
            for _, row in df.iterrows():
                cat = row.get('category', 'Uncategorized')
                val = row.get('amount', 0)
                self.memory.update_financial(cat, val)
                count += 1
            return f"Success: Ingested {count} rows from spreadsheet."
        except Exception as e:
            return f"Spreadsheet Error: {str(e)}"

    def _parse_json(self, file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Assumes simple {"Revenue": 5000} structure
                for cat, val in data.items():
                    self.memory.update_financial(cat, val)
            return "Success: JSON data merged into ledger."
        except Exception as e:
            return f"JSON Error: {str(e)}"

    def _parse_image(self, file_path):
        if not Image:
            return "OCR Error: Image libraries not installed."
        return "Simulated OCR: Scanned receipt image (Text extraction requires Tesseract setup)."