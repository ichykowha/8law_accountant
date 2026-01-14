import streamlit as st
import os
import json
from pinecone import Pinecone
from google import genai
import pypdf
from supabase import create_client

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

    def upload_document(self, file_path, file_name, username, doc_type="financial"):
        """
        doc_type: 'financial' (User Data) OR 'library' (Tax Law/Textbooks)
        """
        if not self.is_ready: return "❌ Librarian offline."
        
        # 1. Determine Namespace (The 'Room' in the Brain)
        # If it's library data, we put it in 'tax_library'. 
        # If it's user data, we put it in 'user_data' (or specifically for that user).
        target_namespace = "tax_library" if doc_type == "library" else "user_data"
        
        # 2. Register Document in Supabase
        try:
            doc_data = {
                "username": username,
                "file_name": file_name,
                "status": "processing",
                "doc_type": doc_type  # Track if this is financial or library
            }
            response = self.supabase.table("documents").insert(doc_data).execute()
            doc_id = response.data[0]['id']
        except Exception as e:
            return f"❌ Database Register Error: {e}"

        # 3. Read PDF
        text_content = ""
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            self.supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
            return f"❌ PDF Read Error: {e}"

        # 4. Chunking (Standard)
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        vectors = []
        
        for i, chunk in enumerate(chunks):
            vector_values = self.embed_text(chunk)
            if vector_values:
                pinecone_id = f"{doc_id}_chunk_{i}"
                metadata = {
                    "text": chunk, 
                    "source": file_name, 
                    "doc_id": doc_id,
                    "type": doc_type
                }
                
                vectors.append({
                    "id": pinecone_id, 
                    "values": vector_values, 
                    "metadata": metadata
                })

        # 5. Upload to Specific Namespace
        if vectors:
            try:
                # *** CRITICAL CHANGE: We use the namespace parameter ***
                self.index.upsert(vectors=vectors, namespace=target_namespace)
                
                self.supabase.table("documents").update({"status": "processed"}).eq("id", doc_id).execute()
                return f"✅ Ingested '{file_name}' into the {target_namespace.upper()}."
            except Exception as e:
                return f"❌ Upload Error: {e}"
        else:
            return "⚠️ No readable text found."

    def search_memory(self, query):
        """Searches BOTH the User Vault and the Tax Library."""
        if not self.is_ready: return []
        
        query_vector = self.embed_text(query)
        if not query_vector: return []

        knowledge_snippets = []

        # Search 1: The Tax Library (Laws & Rules)
        try:
            lib_results = self.index.query(
                vector=query_vector, 
                top_k=3, 
                include_metadata=True, 
                namespace="tax_library"
            )
            for match in lib_results['matches']:
                if match['score'] > 0.3:
                    knowledge_snippets.append(f"[LAW] {match['metadata']['text']}")
        except Exception:
            pass # Library might be empty

        # Search 2: The User Vault (Your Receipts)
        try:
            user_results = self.index.query(
                vector=query_vector, 
                top_k=5, 
                include_metadata=True, 
                namespace="user_data"
            )
            for match in user_results['matches']:
                if match['score'] > 0.3:
                    knowledge_snippets.append(f"[USER DATA] {match['metadata']['text']}")
        except Exception:
            pass

        return knowledge_snippets
