import streamlit as st
from google import genai

class DataQueryAssistant:
    def __init__(self):
        self.is_connected = False
        self.api_key = None
        
        # Security Check
        if "GEMINI_KEY" in st.secrets:
            self.api_key = st.secrets["GEMINI_KEY"]
             
        if self.api_key:
            try:
                # Initialize Gemini Client
                self.client = genai.Client(api_key=self.api_key)
                self.is_connected = True
            except Exception as e:
                print(f"Init Error: {e}")
        else:
            print("Config Error: GEMINI_KEY missing.")

    def ask(self, user_question):
        """
        STRICT CONTRACT: Must ALWAYS return a Dictionary { "answer": str, "reasoning": list }
        """
        # 1. Handle Disconnection
        if not self.is_connected:
            return {
                "answer": "⚠️ System Error: API Key missing or invalid.",
                "reasoning": ["Connection Check Failed"]
            }

        # 2. Prepare Prompt
        prompt = f"""
        You are 8law, an elite AI Accountant.
        User Question: {user_question}
        """

        # 3. Execute with Error Handling
        try:
            # SWITCHING TO THE STABLE WORKHORSE
            # This model has a generous free tier (15 requests/minute)
            response = self.client.models.generate_content(
                model="gemini-1.5-flash", 
                contents=prompt
            )
            
            # 4. Validate Response
            if response.text:
                return {
                    "answer": response.text,
                    "reasoning": ["Model: Gemini 1.5 Flash", "Status: Success"]
                }
            else:
                return {
                    "answer": "I thought about it, but couldn't generate a response.",
                    "reasoning": ["Empty Response Object"]
                }

        except Exception as e:
            # 5. Catch-All for API Errors
            return {
                "answer": f"⚠️ AI Provider Error: {str(e)}",
                "reasoning": ["Crash during API Call"]
            }
