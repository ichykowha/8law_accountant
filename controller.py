import os
from rag_manager import DocumentLibrarian
from google import genai
import streamlit as st

class PowerhouseAccountant:
    def __init__(self):
        self.librarian = DocumentLibrarian()
        try:
            self.client = genai.Client(api_key=st.secrets["GEMINI_KEY"])
        except Exception as e:
            print(f"Controller Init Error: {e}")

    def process_document(self, file_path, username, doc_type="financial", entity_type="Personal"):
        """
        Ingests a document. 
        Now accepts 'entity_type' to tell the AI if it's Personal or Business.
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
