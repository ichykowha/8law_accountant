import streamlit as st
from backend.query_engine import DataQueryAssistant
from backend.rag_manager import DocumentLibrarian

class PowerhouseAccountant:
    def __init__(self):
        self.query_engine = DataQueryAssistant()
        self.librarian = DocumentLibrarian()

    def process_document(self, file_path):
        # 1. Get the filename
        import os
        file_name = os.path.basename(file_path)
        
        # 2. Hand it to the Librarian
        status = self.librarian.upload_document(file_path, file_name)
        return status

    def process_input(self, user_text, history=[]):
        """
        Full RAG Pipeline:
        1. Search Memory (Pinecone) for clues.
        2. Pass Clues + History + Question to Brain (Gemini).
        """
        
        # 1. Search for relevant facts in the documents
        clues = self.librarian.search_memory(user_text)
        
        # 2. Hand everything to the Brain
        return self.query_engine.ask(user_text, history_context=history, document_clues=clues)
