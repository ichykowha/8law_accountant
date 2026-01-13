import streamlit as st
import os
from pinecone import Pinecone
from google import genai
import pypdf

class DocumentLibrarian:
    def __init__(self):
        # 1. Setup Keys
        try:
            self.pinecone_api_key = st.secrets["PINECONE_KEY"]
            self.google_api_key = st.secrets["GEMINI_KEY"]
            self.index_name = "8law-memory"
            
            # 2. Connect to Pinecone
            self.pc = Pinecone(api_key=self.pinecone_api_key)
            self.index = self.pc.Index(self.index_name)
            
            # 3. Connect to Google
            self.client = genai.Client(api_key=self.google_api_key)
            self.is_ready = True
        except Exception as e:
            print(f"Librarian Init Error: {e}")
            self.is_ready = False

    def embed_text(self, text):
        """Turns text into a list of 768 numbers using Google."""
        try:
            # We use the standard 768-dimension model
            result = self.client.models.embed_content(
                model="models/text-embedding-004",
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def upload_document(self, file_path, file_name):
        """Reads a PDF and saves it to the Brain."""
        if not self.is_ready: return "❌ Librarian not initialized (Check API Keys)."
        
        # 1. Read PDF
        text_content = ""
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            return f"❌ Error reading PDF: {e}"

        # 2. Chunking (Cut into manageable pieces)
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        # 3. Embed & Upload
        vectors = []
        for i, chunk in enumerate(chunks):
            vector_values = self.embed_text(chunk)
            if vector_values:
                vector_id = f"{file_name}_chunk_{i}"
                metadata = {
                    "text": chunk,
                    "source": file_name,
                    "chunk_index": i
                }
                vectors.append({
                    "id": vector_id,
                    "values": vector_values,
                    "metadata": metadata
                })

        # 4. Push to Pinecone
        if vectors:
            try:
                self.index.upsert(vectors=vectors)
                return f"✅ Successfully memorized {len(vectors)} snippets from {file_name}."
            except Exception as e:
                return f"❌ Pinecone Upload Error: {e}"
        else:
            return "⚠️ No readable text found in document."

    def search_memory(self, query):
        """Asks Pinecone for relevant snippets."""
        if not self.is_ready: return []
        
        # 1. Convert question to numbers
        query_vector = self.embed_text(query)
        if not query_vector:
            return []

        # 2. Search Index
        try:
            results = self.index.query(
                vector=query_vector,
                top_k=5, # Get top 5 matches
                include_metadata=True
            )
            
            # 3. Extract just the text
            knowledge_snippets = []
            for match in results['matches']:
                if match['score'] > 0.3: # Only keep good matches
                    knowledge_snippets.append(match['metadata']['text'])
            
            return knowledge_snippets
            
        except Exception as e:
            print(f"Search Error: {e}")
            return []
