import pandas as pd
import sqlite3
import google.generativeai as genai

class DataQueryAssistant:
    def __init__(self, db_name="accountant_pi.db"):
        self.db_name = db_name
        
        # --- 1. CONFIGURE THE REAL BRAIN ---
        # We are using the key you provided to unlock Gemini Pro
        self.api_key = "AIzaSyAQlLuWebElC8nwR7-1VLr-Kob6Rsnuw1I"
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.is_connected = True
        except Exception as e:
            print(f"Error connecting to Gemini: {e}")
            self.is_connected = False

    def ask(self, user_question):
        """Sends the ledger + question to Google's AI model."""
        
        # --- 2. FETCH LEDGER CONTEXT ---
        conn = sqlite3.connect(self.db_name)
        try:
            df = pd.read_sql_query("SELECT * FROM financial_records", conn)
            # We convert the last 60 transactions to text so the AI can "read" them
            # (Limit helps keep it fast and within standard token limits)
            ledger_context = df.tail(60).to_string(index=False)
        except:
            ledger_context = "The ledger is currently empty."
        conn.close()

        # --- 3. CREATE THE PROMPT ---
        prompt = f"""
        You are 8law, an advanced AI Accountant.
        
        CONTEXT (Your Ledger):
        {ledger_context}
        
        USER QUESTION: 
        {user_question}
        
        INSTRUCTIONS:
        1. Answer the question based strictly on the ledger data provided above.
        2. If the user asks for a total, sum the values accurately.
        3. If the user asks for tax advice, apply general accounting principles (focusing on Canadian/BC rules if applicable).
        4. If the ledger is empty, tell the user to upload a file first.
        5. Provide a concise, professional answer.
        """

        # --- 4. GET THE ANSWER ---
        reasoning_steps = []
        final_answer = ""
        
        if self.is_connected:
            try:
                # Call the AI
                response = self.model.generate_content(prompt)
                final_answer = response.text
                reasoning_steps = ["Connected to Gemini Pro", "Analyzed Ledger Context", "Generated Response"]
            except Exception as e:
                final_answer = f"I encountered an error thinking about that: {str(e)}"
                reasoning_steps = ["Connection Failed"]
        else:
            final_answer = "My AI Brain is not connected. Please check the API Key."
        
        return {
            "answer": final_answer,
            "reasoning": reasoning_steps
        }