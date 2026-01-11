import pytesseract
import platform
import shutil
import os
from PIL import Image

class UniversalIngestor:
    def __init__(self, memory_module=None):
        self.memory = memory_module
        
        # --- SMART PATH DETECTION ---
        if platform.system() == "Windows":
            # Your Local Laptop Path
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        else:
            # Streamlit Cloud (Linux) Path
            # We look for the command 'tesseract' in the system path
            tesseract_path = shutil.which("tesseract")
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            else:
                # Fallback for some Linux setups
                pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

    def ingest_file(self, file_path):
        """Routes the file to the correct scanner."""
        ext = file_path.split('.')[-1].lower()
        
        if ext in ['jpg', 'jpeg', 'png', 'heic']:
            return self._scan_image(file_path)
        elif ext == 'pdf':
            return "PDF Scanning not yet enabled for mobile."
        else:
            return f"File type {ext} not supported."

    def _scan_image(self, image_path):
        try:
            # Open the image
            img = Image.open(image_path)
            
            # RUN OCR
            text = pytesseract.image_to_string(img)
            
            if not text.strip():
                return "I scanned the image, but found no readable text. Was it blurry?"
                
            return text
            
        except Exception as e:
            # If Tesseract crashes, we show the real error now
            return f"OCR Error: {str(e)}. (Did you add packages.txt?)"
