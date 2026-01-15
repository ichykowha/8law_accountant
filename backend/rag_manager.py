import streamlit as st
import os
import json
from pinecone import Pinecone
from google import genai
import pypdf
from supabase import create_client
from bs4 import BeautifulSoup  # <--- NEW: XML Tool

class DocumentLibrarian:
    def __init__(self):
        self.is_ready = False
        try:
            self.pinecone_api_key = st.secrets["PINECONE_KEY"]
            self.google_api_key = st.secrets["GEMINI_KEY"]
            self.supabase_url = st.secrets["SUPABASE_URL"]
            self.supabase_key = st.secrets["SUPABASE_KEY"]
            self.index_name = "8law-memory"
            
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

    # --- XML READER (New!) ---
    def read_xml_file(self, file_path):
        """Reads the Tax Act XML safely."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # Use lxml for speed
                soup = BeautifulSoup(f, "xml")
                # Get text, separating tags with newlines so we don't merge words
                text = soup.get_text(separator="\n")
                return text
        except Exception as e:
            print(f"XML Error: {e}")
            return None

    # --- EXTRACTORS ---
  # --- SMART AUDITOR (Context Aware) 🧠 ---
    def extract_transactions_ai(self, text, doc_id, username, entity_type="Personal"):
        
        # 1. Define the Auditor Persona based on Selection
        audit_instructions = ""
        if entity_type == "Personal":
            audit_instructions = """
            MODE: PERSONAL TAX (T1)
            - Most expenses are NOT deductible (Groceries, Clothing, Personal Rent = 0%).
            - Look for: Medical Expenses, Charitable Donations, Moving Expenses, Child Care.
            - If uncertain, assume 0% deductible.
            """
        elif entity_type == "Small Business (Sole Prop)":
            audit_instructions = """
            MODE: SOLE PROPRIETORSHIP (T2125)
            - You are auditing for Business Expenses.
            - MEALS: 50% Deductible (if business related).
            - GOLF/CLUB DUES: 0% Deductible (Strictly prohibited).
            - OFFICE/RENT/SOFTWARE: 100% Deductible.
            - PERSONAL ITEMS: 0% Deductible.
            """
        elif "Corporation" in entity_type:
            audit_instructions = """
            MODE: CORPORATION (T2)
            - Aggressively categorize for Business Expenses.
            - MEALS: 50% Deductible.
            - SALARIES/WAGES: 100% Deductible.
            - INSURANCE/ RENT: 100% Deductible.
            - Life Insurance: Generally 0% unless specific conditions met.
            """
        elif "Non-Profit" in entity_type:
            audit_instructions = """
            MODE: NON-PROFIT / CHARITY (T1044/T3010)
            - Focus on 'Program Expenses' vs 'Management/Admin'.
            - GST/HST Rebates might apply.
            - STRICTLY separate personal benefit (0%) from organizational cost (100%).
            """

        # 2. The Prompt
        prompt = f"""
        You are an elite Canadian Tax Auditor. 
        Analyze the text below (Bank Statement or Receipt).
        
        {audit_instructions}
        
        CRITICAL: For each transaction, apply CRA Tax Rules to determine deductibility based on the MODE above.
        
        RETURN A RAW JSON LIST:
        [
            {{
                "transaction_date": "YYYY-MM-DD", 
                "vendor": "Name", 
                "amount": 100.00, 
                "category": "Office Supplies", 
                "description": "Details",
                "deductible_percent": 100,
                "tax_category": "Stationery",
                "audit_reasoning": "Valid business expense under T2125 rules."
            }}
        ]
        
        TEXT TO ANALYZE:
        {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            transactions = json.loads(clean_json)
            
            valid_rows = []
            for t in transactions:
                t['username'] = username
                t['source_doc_id'] = doc_id
                if 'deductible_percent' not in t: t['deductible_percent'] = 0
                valid_rows.append(t)
                
            return valid_rows
            
        except Exception as e:
            print(f"Transaction Audit Error: {e}")
            return []

    def extract_tax_slip_ai(self, text, doc_id, username):
        prompt = f"""
        Identify Tax Slips (T4, T5, etc). Return JSON list:
        [{{ "slip_type": "T4", "tax_year": 2025, "issuer": "Name", "box_data": {{ "14": 500.00 }} }}]
        TEXT: {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean = response.text.replace("```json", "").replace("```", "").strip()
            return [dict(s, username=username, source_doc_id=doc_id) for s in json.loads(clean)]
        except: return []

    def extract_noa_ai(self, text, doc_id, username):
        prompt = f"""
        Analyze if this is a CRA Notice of Assessment. If yes, return JSON:
        {{ "is_noa": true, "tax_year": 2023, "rrsp_deduction_limit": 0.00, "unused_rrsp_contrib": 0.00, "tuition_federal": 0.00, "tuition_provincial": 0.00, "capital_losses": 0.00 }}
        TEXT: {text[:30000]}
        """
        try:
            response = self.client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            if data.get("is_noa"):
                data['username'] = username
                data['source_doc_id'] = doc_id
                del data['is_noa'] # Remove flag before DB insert
                return data
            return None
        except: return None

    # --- MAIN UPLOAD ---
    def upload_document(self, file_path, file_name, username, doc_type="financial", entity_type="Personal"):
        if not self.is_ready: return "❌ Librarian offline."
        
        # 1. Register Document
        try:
            target_namespace = "tax_library" if doc_type == "library" else "user_data"
            doc_data = {"username": username, "file_name": file_name, "status": "processing", "doc_type": doc_type}
            response = self.supabase.table("documents").insert(doc_data).execute()
            doc_id = response.data[0]['id']
        except Exception as e:
            return f"❌ DB Register Error: {e}"

        # 2. Read File (XML or PDF)
        text_content = ""
        try:
            if file_name.lower().endswith(".xml"):
                text_content = self.read_xml_file(file_path)
                if not text_content: raise Exception("XML Empty")
            else:
                reader = pypdf.PdfReader(file_path)
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
            
            # Safety Truncate (20MB Limit) to prevent timeout
            if len(text_content) > 20000000:
                text_content = text_content[:20000000]

        except Exception as e:
            self.supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
            return f"❌ File Read Error: {e}"

        # --- ROUTING (Financial Only) ---
        if doc_type == "financial":
            # Check NOA
            noa = self.extract_noa_ai(text_content, doc_id, username)
            if noa: 
                self.supabase.table("tax_history").insert(noa).execute()
            # Check Slips
            elif not noa:
                slips = self.extract_tax_slip_ai(text_content, doc_id, username)
                if slips: self.supabase.table("tax_slips").insert(slips).execute()
                # Check Txns
                elif not slips:
                   # Pass the user's choice to the extraction engine
                    txns = self.extract_transactions_ai(text_content, doc_id, username, entity_type)
                    if txns: self.supabase.table("transactions").insert(txns).execute()

        # 3. Chunk & Embed
        chunk_size = 1000
        # If text is huge, take first 500 chunks only for MVP speed (Optional safety)
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        vectors = []
        vector_refs = []
        
        # BATCHING: Send to Pinecone in groups of 100 to avoid timeouts
        batch_size = 100
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch = chunks[i:i + batch_size]
            batch_vectors = []
            
            for j, chunk in enumerate(batch):
                real_index = i + j
                v = self.embed_text(chunk)
                if v:
                    pid = f"{doc_id}_{real_index}"
                    meta = {"text": chunk, "source": file_name, "doc_id": doc_id, "type": doc_type}
                    batch_vectors.append({"id": pid, "values": v, "metadata": meta})
                    vector_refs.append({"username": username, "document_id": doc_id, "chunk_index": real_index, "pinecone_id": pid})
            
            if batch_vectors:
                try:
                    self.index.upsert(vectors=batch_vectors, namespace=target_namespace)
                    # We skip inserting vector_refs to Supabase for the Library to save time/space
                    if doc_type == "financial":
                         self.supabase.table("vector_refs").insert(vector_refs).execute()
                except Exception as e:
                    print(f"Batch Error: {e}")
            
            # Reset for next batch
            vector_refs = []

        self.supabase.table("documents").update({"status": "processed"}).eq("id", doc_id).execute()
        return f"✅ Ingested {file_name} into {target_namespace}."

    def search_memory(self, query):
        if not self.is_ready: return []
        q_vec = self.embed_text(query)
        if not q_vec: return []

        snippets = []
        try:
            res = self.index.query(vector=q_vec, top_k=3, include_metadata=True, namespace="tax_library")
            for m in res['matches']:
                if m['score'] > 0.3: snippets.append(f"[LAW] {m['metadata']['text']}")
        except: pass
        try:
            res = self.index.query(vector=q_vec, top_k=5, include_metadata=True, namespace="user_data")
            for m in res['matches']:
                if m['score'] > 0.3: snippets.append(f"[USER DATA] {m['metadata']['text']}")
        except: pass
        return snippets
