import streamlit as st
from google import genai

class DataQueryAssistant:
    def __init__(self):
        self.is_connected = False
        self.api_key = None
        
        if "GEMINI_KEY" in st.secrets:
            self.api_key = st.secrets["GEMINI_KEY"]
             
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.is_connected = True
            except Exception as e:
                print(f"Init Error: {e}")

    def ask(self, user_question, history_context=None):
        """
        Arguments:
        - user_question: The new question
        - history_context: A list of previous messages [{"role": "user", "content": "..."}]
        """
        if not self.is_connected:
            return {"answer": "⚠️ System Error: API Key missing.", "reasoning": ["Connection Check Failed"]}

        # 1. Format History into a script
        history_text = ""
        if history_context:
            for msg in history_context[-5:]: # Keep last 5 messages to save tokens
                role = "User" if msg["role"] == "user" else "AI"
                history_text += f"{role}: {msg['content']}\n"

        # 2. Inject History into Prompt
        prompt = f"""
        You are 8law, an elite AI Accountant.
        
        CONTEXT (Previous Conversation):
        {history_text}
        
        CURRENT USER QUESTION:
        {user_question}
        
        INSTRUCTIONS:
        - Use the CONTEXT to answer if relevant.
        - If the user asks about a past number/fact, use the CONTEXT to find it.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-pro", 
                contents=prompt
            )
            
            if response.text:
                return {
                    "answer": response.text,
                    "reasoning": ["Checked Memory Context", "Model: Gemini 2.5 Pro"]
                }
            else:
                return {"answer": "I couldn't generate a response.", "reasoning": ["Empty Response"]}

        except Exception as e:
            return {"answer": f"⚠️ AI Provider Error: {str(e)}", "reasoning": ["Crash during API Call"]}
