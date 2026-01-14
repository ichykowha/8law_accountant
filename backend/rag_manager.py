import streamlit as st
import os
from pinecone import Pinecone
from google import genai
import pypdf
from supabase import create_client

class DocumentLibrarian:
    def __init__(self):
        # 1. Setup Keys & Connections
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
        """Turns text into 768 numbers."""
        try:
            result = self.client.models.embed_content(
                model="models/text-embedding-004",
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def upload_document(self, file_path, file_name, username):
        """Reads PDF, Saves to DB, and Memorizes in Pinecone."""
        if not self.is_ready: return "❌ Librarian offline."
        
        # 1. Register Document in Supabase
        try:
            doc_data = {
                "username": username,
                "file_name": file_name,
                "status": "processing"
            }
            response = self.supabase.table("documents").insert(doc_data).execute()
            doc_id = response.data[0]['id'] # Get the new ID
        except Exception as e:
            return f"❌ Database Register Error: {e}"

        # 2. Read PDF Text
        text_content = ""
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            # Mark as failed in DB
            self.supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
            return f"❌ PDF Read Error: {e}"

        # 3. Chunking
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        # 4. Embed & Prepare Vectors
        vectors = []
        vector_refs_data = [] # To save to DB
        
        for i, chunk in enumerate(chunks):
            vector_values = self.embed_text(chunk)
            if vector_values:
                # Create ID: docID_chunkIndex
                pinecone_id = f"{doc_id}_chunk_{i}"
                
                # Metadata for Pinecone (Search)
                metadata = {
                    "text": chunk,
                    "source": file_name,
                    "doc_id": doc_id,
                    "username": username
                }
                
                vectors.append({
                    "id": pinecone_id,
                    "values": vector_values,
                    "metadata": metadata
                })
                
                # Metadata for Supabase (Tracking)
                vector_refs_data.append({
                    "username": username,
                    "document_id": doc_id,
                    "chunk_index": i,
                    "pinecone_id": pinecone_id
                })

        # 5. Upload to Pinecone & Supabase
        if vectors:
            try:
                # A. Send to Pinecone
                self.index.upsert(vectors=vectors)
                
                # B. Send refs to Supabase
                self.supabase.table("vector_refs").insert(vector_refs_data).execute()
                
                # C. Mark Document as Done
                self.supabase.table("documents").update({"status": "processed"}).eq("id", doc_id).execute()
                
                return f"✅ Indexed {len(vectors)} snippets for {file_name}."
            except Exception as e:
                return f"❌ Upload Error: {e}"
        else:
            return "⚠️ No readable text found."

    def search_memory(self, query):
        """Asks Pinecone for relevant snippets."""
        if not self.is_ready: return []
        
        query_vector = self.embed_text(query)
        if not query_vector: return []

        try:
            # Query Pinecone
            results = self.index.query(
                vector=query_vector,
                top_k=5,
                include_metadata=True
            )
            
            snippets = []
            for match in results['matches']:
                if match['score'] > 0.3:
                    snippets.append(match['metadata']['text'])
            return snippets
        except Exception:
            return []
