import os
import sys

# --- FIX IMPORTS ---
# This block ensures we can find 'rag_manager' whether it is in 'backend' or root.
try:
    # Try finding it in the backend folder first (Most likely)
    from backend.rag_manager import DocumentLibrarian
except ImportError:
    try:
        # Try finding it in the same folder (Fallback)
        from rag_manager import DocumentLibrarian
    except ImportError:
        # If both fail, we manually add the backend folder to the path
        sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
        from rag_manager import DocumentLibrarian

from google import genai
import streamlit as st

class PowerhouseAccountant:
    def __init__(self):
        # Initialize the Librarian
        self.librarian = DocumentLibrarian()
        try:
            # Initialize Gemini
            self.client = genai.Client(api_key=st.secrets["GEMINI_KEY"])
        except Exception as e:
            print(f"Controller Init Error: {e}")

    def process_document(self, file_path, username, doc_type="financial", entity_type="Personal"):
        """
        Ingests a document. 
        Passes 'entity_type' (Personal vs Business) to the Librarian.
        """
        if not self.librarian.is_ready:
            return "⚠️ AI Librarian is offline."
            
        # Pass the new 'entity_type' wire down to the Librarian
        return self.librarian.upload_document(
            file_path, 
            os.path.basename(file_path), 
            username, 
            doc_type, 
            entity_type
        )

    def process_input(self, user_input, history):
        """
        Main Chat Logic
        """
        # 1. Search Memory (RAG)
        context_snippets = self.librarian.search_memory(user_input)
        context_str = "\n".join(context_snippets)

        # 2. Build Prompt
        system_prompt = f"""
        You are 8law, an elite AI Accountant.
        
        USER CONTEXT:
        {context_str}
        
        INSTRUCTIONS:
        - Use the context provided (Tax Law or User Data) to answer.
        - If the user asks about tax rules, cite the specific section from the context if available.
        - Be professional, concise, and accurate.
        """

        # 3. Call Gemini
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[system_prompt, user_input]
            )
            return {"answer": response.text, "reasoning": ["Checked Database", "Applied Tax Logic"]}
        except Exception as e:
            return {"answer": f"I encountered an error: {e}", "reasoning": []}
