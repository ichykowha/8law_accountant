import streamlit as st
from backend.query_engine import DataQueryAssistant

class PowerhouseAccountant:
    def __init__(self):
        self.query_engine = DataQueryAssistant()

    def process_document(self, file_path):
        # Placeholder for RAG logic (Phase 3)
        return "Document processed."

    def process_input(self, user_text, history=[]):
        """
        Now accepts 'history' and passes it to the brain.
        """
        return self.query_engine.ask(user_text, history_context=history)
