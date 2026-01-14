import streamlit as st
from backend.query_engine import DataQueryAssistant
from backend.rag_manager import DocumentLibrarian

class PowerhouseAccountant:
    def __init__(self):
        self.query_engine = DataQueryAssistant()
        self.librarian = DocumentLibrarian()

    # The fix is here: We added 'username="admin"' so it accepts the name
    def process_document(self, file_path, username="admin"):
        # 1. Get filename
        import os
        file_name = os.path.basename(file_path)
        
        # 2. Hand to Librarian (Pass the username along!)
        status = self.librarian.upload_document(file_path, file_name, username)
        return status

    def process_input(self, user_text, history=[]):
        # 1. Search Memory
        clues = self.librarian.search_memory(user_text)
        
        # 2. Ask Brain
        return self.query_engine.ask(user_text, history_context=history, document_clues=clues)
