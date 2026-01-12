import os
import pandas as pd
import json
import time
from pypdf import PdfReader # New import for PDFs

class UniversalIngestor:
    def __init__(self, memory_system):
        self.memory = memory_system

    def ingest_file(self, file_path, vector_db=None):
        """
        Reads a file and upserts it to Pinecone if a DB is provided.
        """
        try:
            # 1. Determine file type
            filename = os.path.basename(file_path)
            ext = filename.split('.')[-1].lower()
            
            content_summary = ""
            status_msg = ""

            # 2. Extract Text based on type
            if ext == 'csv':
                df = pd.read_csv(file_path)
                content_summary = df.head(5).to_string()
                row_count = len(df)
                status_msg = f"Processed CSV: {filename} ({row_count} rows)"
            
            elif ext == 'json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                content_summary = str(data)[:500] 
                status_msg = f"Processed JSON: {filename}"

            elif ext == 'pdf':
                reader = PdfReader(file_path)
                text = ""
                # Read all pages
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                content_summary = text[:1000] # Grab first 1000 chars for memory
                page_count = len(reader.pages)
                status_msg = f"Processed PDF: {filename} ({page_count} pages)"
                
            else:
                return f"File type .{ext} not supported yet."

            # 3. Send to Pinecone (The AI Memory)
            if vector_db:
                # Create a unique ID for this file
                file_id = f"file_{int(time.time())}_{filename}"
                
                # Dummy Vector (In real life, this would be an OpenAI embedding)
                dummy_vector = [0.1] * 3 
                
                vector_db.upsert(
                    vectors=[
                        (file_id, dummy_vector, {"filename": filename, "text": content_summary})
                    ]
                )
                status_msg += " | Saved to Pinecone Memory 🧠"

            return status_msg

        except Exception as e:
            return f"Error reading file: {str(e)}"