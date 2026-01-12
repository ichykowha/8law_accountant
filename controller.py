import streamlit as st
from backend.query_engine import DataQueryAssistant

class PowerhouseAccountant:
    def __init__(self):
        # Initialize the Brain
        self.query_engine = DataQueryAssistant()

    def process_document(self, file_path):
        return "Document processed."

    def process_input(self, user_text):
        """
        Passes input to the brain and returns the structured response.
        """
        # 1. Get the package from the Brain
        response_package = self.query_engine.ask(user_text)

        # 2. Strict Type Check (The Contract)
        if isinstance(response_package, dict) and "answer" in response_package:
            return response_package
        else:
            # This should mathematically never happen now.
            # If it does, it reveals a critical architecture failure.
            return {
                "answer": "⚠️ CRITICAL ARCHITECTURE FAILURE: Backend violated Data Contract.",
                "reasoning": [f"Received Invalid Type: {type(response_package)}"]
            }
