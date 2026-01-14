import streamlit as st
import os
import json
from pinecone import Pinecone
from google import genai
import pypdf
from supabase import create_client
import re

class DocumentLibrarian:
    def __init__(self):
        self.is_ready = False
        try:
            # Keys
            self.pinecone_api_key = st.secrets["PINECONE_KEY"]
            self.google_api_key = st.secrets["GEMINI_KEY"]
            self.supabase_url = st.secrets["SUPABASE_URL"]
            self.supabase_key = st.secrets["SUPABASE_KEY"]
            self.index_name = "8law-memory"
            
            # Clients
            self.pc = Pinecone(api_key=self.pinecone_api_key)
            self.index = self.pc.Index(self.index_name)
            self.client = genai.Client(api_key=self.google_api_key)
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            
            self.is_ready = True
        except Exception as e:
            print(f"Librarian Init Error: {e}")

    def embed_text(self, text):
        try:
            result = self.client.models.embed_content(
                model="models/text-embedding-004",
                contents=text
            )
            return result.embeddings[0].values
        except Exception:
            return None

    def extract_transactions_ai(self, text, doc_id, username):
        """Uses Gemini to find money in the text."""
        prompt = f"""
        You are a Data Extraction Engine.
        Analyze the text below and extract every financial transaction.
        
        RETURN ONLY A RAW JSON LIST. Do not use Markdown codes.
        Format:
        [
          {{"transaction_date": "YYYY-MM-DD", "vendor": "Starbucks", "amount": 5.40, "category": "Food", "description": "Coffee purchase"}},
          ...
        ]
        
        - If a date is missing the year, assume 2025.
        - Convert all amounts to positive numbers.
        - If no transactions are found, return [].

        TEXT TO ANALYZE:
        {text[:30000]} 
        """
        
        try:
            # Ask Gemini to do the hard work
            response = self.client.models.generate_content(
                model="gemini-2.5-pro", 
                contents=prompt
            )
            
            # Clean up the answer (remove markdown ```json ... ``` if it exists)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            transactions = json.loads(clean_json)
            
            # Add database IDs to the rows
            valid_rows = []
            for t in transactions:
                t['username'] = username
                t['source_doc_id'] = doc_id
                valid_rows.append(t)
                
            return valid_rows
            
        except Exception as e:
            print(f"AI Extraction Error: {e}")
            return []

    def upload_document(self, file_path, file_name, username):
        if not self.is_ready: return "❌ Librarian offline."
        
        # 1. Register Document
        try:
            doc_data = {"username": username, "file_name": file_name, "status": "processing"}
            response = self.supabase.table("documents").insert(doc_data).execute()
            doc_id = response.data[0]['id']
        except Exception as e:
            return f"❌ Database Register Error: {e}"

        # 2. Read PDF
        text_content = ""
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            self.supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
            return f"❌ PDF Read Error: {e}"

        # --- NEW: EXTRACT TRANSACTIONS ---
        try:
            extracted_rows = self.extract_transactions_ai(text_content, doc_id, username)
            if extracted_rows:
                self.supabase.table("transactions").insert(extracted_rows).execute()
        except Exception as e:
            print(f"Transaction Insert Error: {e}")
        # ---------------------------------

        # 3. Chunking & Indexing (The Old Part)
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        vectors = []
        vector_refs_data = []
        
        for i, chunk in enumerate(chunks):
            vector_values = self.embed_text(chunk)
            if vector_values:
                pinecone_id = f"{doc_id}_chunk_{i}"
                metadata = {
                    "text": chunk, 
                    "source": file_name, 
                    "doc_id": doc_id, 
                    "username": username
                }
                
                vectors.append({"id": pinecone_id, "values": vector_values, "metadata": metadata})
                vector_refs_data.append({
                    "username": username,
                    "document_id": doc_id, 
                    "chunk_index": i, 
                    "pinecone_id": pinecone_id
                })

        # 4. Upload & Finish
        if vectors:
            try:
                self.index.upsert(vectors=vectors)
                self.supabase.table("vector_refs").insert(vector_refs_data).execute()
                self.supabase.table("documents").update({"status": "processed"}).eq("id", doc_id).execute()
                
                # Report back success
                msg = f"✅ Processed {file_name}."
                if extracted_rows:
                    msg += f" Found {len(extracted_rows)} transactions! 💰"
                return msg
            except Exception as e:
                return f"❌ Upload Error: {e}"
        else:
            return "⚠️ No readable text found."

    def search_memory(self, query):
        if not self.is_ready: return []
        query_vector = self.embed_text(query)
        if not query_vector: return []

        try:
            results = self.index.query(vector=query_vector, top_k=5, include_metadata=True)
            snippets = []
            for match in results['matches']:
                if match['score'] > 0.3:
                    snippets.append(match['metadata']['text'])
            return snippets
        except Exception:
            return []
