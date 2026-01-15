import streamlit as st
import os
import json
from pinecone import Pinecone
from google import genai
import pypdf
from supabase import create_client
import re
from bs4 import BeautifulSoup

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
    def read_xml_file(self, file_path):
    """Reads a massive XML file safely."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # We use 'lxml' because it is fast enough for big files
            soup = BeautifulSoup(f, "xml")

            # Extract all text, separating tags with spaces
            text = soup.get_text(separator="\n")
            return text
    except Exception as e:
        return None
            return result.embeddings[0].values
        except Exception:
            return None

    # --- 1. SPENDING EXTRACTOR (Bank Statements) ---
    def extract_transactions_ai(self, text, doc_id, username):
        prompt = f"""
        You are a Data Extraction Engine.
        Analyze the text below and extract every financial transaction.
        RETURN ONLY A RAW JSON LIST.
        Format: [{{"transaction_date": "YYYY-MM-DD", "vendor": "Name", "amount": 0.00, "category": "Type", "description": "Details"}}]
        
        TEXT: {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            transactions = json.loads(clean_json)
            valid_rows = []
            for t in transactions:
                t['username'] = username
                t['source_doc_id'] = doc_id
                valid_rows.append(t)
            return valid_rows
        except Exception as e:
            print(f"Transaction Error: {e}")
            return []

    # --- 2. T-SLIP EXTRACTOR (T4, T5, etc) ---
    def extract_tax_slip_ai(self, text, doc_id, username):
        prompt = f"""
        You are a Canadian Tax Expert. Identify if this is a Tax Slip (T4, T5, T2202, etc).
        If NO, return [].
        If YES, return JSON:
        [{{ "slip_type": "T4", "tax_year": 2025, "issuer": "Name", "box_data": {{ "14": 500.00 }} }}]
        
        TEXT: {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            slips = json.loads(clean_json)
            valid_rows = []
            for slip in slips:
                slip['username'] = username
                slip['source_doc_id'] = doc_id
                valid_rows.append(slip)
            return valid_rows
        except Exception as e:
            print(f"T-Slip Error: {e}")
            return []

    # --- 3. NOA EXTRACTOR (History/Limits) ---
    def extract_noa_ai(self, text, doc_id, username):
        prompt = f"""
        You are a Canadian Tax Expert. Analyze if this is a 'Notice of Assessment' (NOA).
        If NOT NOA, return {{}}.
        If YES, return JSON:
        {{
            "is_noa": true, "tax_year": 2023, "rrsp_deduction_limit": 0.00, 
            "unused_rrsp_contrib": 0.00, "tuition_federal": 0.00, 
            "tuition_provincial": 0.00, "capital_losses": 0.00
        }}
        TEXT: {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            if data.get("is_noa"):
                return {
                    "username": username, "source_doc_id": doc_id,
                    "tax_year": data.get("tax_year"),
                    "rrsp_deduction_limit": data.get("rrsp_deduction_limit", 0),
                    "unused_rrsp_contrib": data.get("unused_rrsp_contrib", 0),
                    "tuition_federal": data.get("tuition_federal", 0),
                    "tuition_provincial": data.get("tuition_provincial", 0),
                    "capital_losses": data.get("capital_losses", 0)
                }
            return None
        except Exception as e:
            print(f"NOA Error: {e}")
            return None

    # --- MASTER UPLOAD FUNCTION ---
    def upload_document(self, file_path, file_name, username, doc_type="financial"):
        if not self.is_ready: return "❌ Librarian offline."
        
        # 1. Register Document
        try:
            target_namespace = "tax_library" if doc_type == "library" else "user_data"
            doc_data = {"username": username, "file_name": file_name, "status": "processing", "doc_type": doc_type}
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

        # --- INTELLIGENT ROUTING ---
        if doc_type == "financial":
            # A. Check for NOA
            noa_data = self.extract_noa_ai(text_content, doc_id, username)
            if noa_data:
                self.supabase.table("tax_history").insert(noa_data).execute()
                print("✅ NOA Logged")
            
            # B. Check for T-Slips (only if not NOA)
            t_slips_found = False
            if not noa_data:
                try:
                    slips = self.extract_tax_slip_ai(text_content, doc_id, username)
                    if slips:
                        self.supabase.table("tax_slips").insert(slips).execute()
                        t_slips_found = True
                except Exception: pass

            # C. Check for Transactions (only if neither NOA nor Slip)
            if not noa_data and not t_slips_found:
                try:
                    txns = self.extract_transactions_ai(text_content, doc_id, username)
                    if txns:
                        self.supabase.table("transactions").insert(txns).execute()
                except Exception: pass

        # 3. Chunk & Embed (For Chat Memory)
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        vectors = []
        
        for i, chunk in enumerate(chunks):
            v = self.embed_text(chunk)
            if v:
                vectors.append({
                    "id": f"{doc_id}_chunk_{i}",
                    "values": v,
                    "metadata": {"text": chunk, "source": file_name, "doc_id": doc_id, "type": doc_type}
                })

        if vectors:
            try:
                self.index.upsert(vectors=vectors, namespace=target_namespace)
                self.supabase.table("documents").update({"status": "processed"}).eq("id", doc_id).execute()
                return f"✅ Ingested {file_name}."
            except Exception as e:
                return f"❌ Index Error: {e}"
        return "⚠️ No text found."

    def search_memory(self, query):
        if not self.is_ready: return []
        q_vec = self.embed_text(query)
        if not q_vec: return []

        snippets = []
        # Search Library
        try:
            res = self.index.query(vector=q_vec, top_k=3, include_metadata=True, namespace="tax_library")
            for m in res['matches']:
                if m['score'] > 0.3: snippets.append(f"[LAW] {m['metadata']['text']}")
        except: pass
        
        # Search User Data
        try:
            res = self.index.query(vector=q_vec, top_k=5, include_metadata=True, namespace="user_data")
            for m in res['matches']:
                if m['score'] > 0.3: snippets.append(f"[USER DATA] {m['metadata']['text']}")
        except: pass
        
        return snippets
