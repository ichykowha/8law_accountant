import streamlit as st
from google import genai

class DataQueryAssistant:
    def __init__(self):
        # --- 1. SETUP CONNECTION ---
        self.is_connected = False
        self.api_key = None
        
        # Try to find the key
        if "GEMINI_KEY" in st.secrets:
            self.api_key = st.secrets["GEMINI_KEY"]
        elif "google_api_key" in st.secrets:
             self.api_key = st.secrets["google_api_key"]
             
        if self.api_key:
            try:
                # NEW 2026 SYNTAX
                self.client = genai.Client(api_key=self.api_key)
                self.is_connected = True
            except Exception as e:
                print(f"CRITICAL: Client init failed: {e}")
        else:
            print("CRITICAL: No API Key found in secrets.")

    def ask(self, user_question):
        # --- 2. FAIL FAST IF DISCONNECTED ---
        if not self.is_connected:
            return {
                "answer": "⚠️ **SYSTEM ERROR:** I cannot connect to Google. Please check that 'GEMINI_KEY' is in your Streamlit Secrets.",
                "reasoning": ["Connection Failed", "No API Key"]
            }

        # --- 3. THE PROMPT ---
        prompt = f"""
        You are 8law, an elite AI Accountant.
        User Question: {user_question}
        """

        # --- 4. CALL THE BRAIN (NEW SYNTAX) ---
        try:
            # This is the specific line that was 404-ing. 
            # We now use the 'client.models' path which is the new standard.
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            
            if response.text:
                return {
                    "answer": response.text,
                    "reasoning": ["Success", "Model: Gemini 1.5 Flash"]
                }
            else:
                return {
                    "answer": "I heard you, but my brain came up empty.",
                    "reasoning": ["Empty Response from Google"]
                }

        except Exception as e:
            # This will show you exactly WHY it failed on the screen
            return {
                "answer": f"⚠️ **API ERROR:** {str(e)}",
                "reasoning": ["Crash during generation"]
            }
            
