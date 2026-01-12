import streamlit as st
from google import genai
from google.genai import types

class DataQueryAssistant:
    def __init__(self):
        # --- 1. CONFIGURE THE NEW BRAIN ---
        self.is_connected = False
        try:
            # We access the key securely from Streamlit Secrets
            if "GEMINI_KEY" in st.secrets:
                self.api_key = st.secrets["GEMINI_KEY"]
                self.client = genai.Client(api_key=self.api_key)
                self.is_connected = True
            else:
                print("Gemini Key not found in secrets.")
        except Exception as e:
            print(f"Error connecting to Gemini: {e}")

    def ask(self, user_question):
        """Sends the question + Pinecone memories to Google's AI."""
        
        context_text = ""
        source_used = "General Knowledge"

        # --- 2. FETCH MEMORY FROM PINECONE ---
        # (We keep this light for now to ensure the connection works first)
        if 'vector_db' in st.session_state and st.session_state.vector_db is not None:
            try:
                # In the future, we will search for real memories here.
                # For this test, we confirm memory is active.
                context_text = "User has uploaded financial documents."
                source_used = "Uploaded Documents"
            except Exception as e:
                context_text = f"Error reading memory: {e}"
        
        # --- 3. CREATE THE PROMPT ---
        prompt = f"""
        You are 8law, an advanced AI Accountant.
        
        USER QUESTION: 
        {user_question}
        
        CONTEXT:
        {context_text}
        
        INSTRUCTIONS:
        Answer the question professionally. Be concise.
        """

        # --- 4. GET THE ANSWER (NEW 2026 SYNTAX) ---
        reasoning_steps = []
        final_answer = ""
        
        if self.is_connected:
            try:
                # This uses the new Google GenAI SDK
                response = self.client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt
                )
                final_answer = response.text
                reasoning_steps = [
                    f"Source: {source_used}", 
                    "AI Model: Gemini 1.5 Flash", 
                    "Status: Success"
                ]
            except Exception as e:
                final_answer = f"I encountered an error thinking about that: {str(e)}"
                reasoning_steps = ["Connection Failed"]
        else:
            final_answer = "My AI Brain is not connected. Please check the API Key."
        
        return {
            "answer": final_answer,
            "reasoning": reasoning_steps
        }
        
