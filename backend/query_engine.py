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

    def ask(self, user_question, history_context=None, document_clues=None):
        if not self.is_connected:
            return {"answer": "⚠️ System Error: API Key missing.", "reasoning": ["Connection Check Failed"]}

        # 1. Format History
        history_text = ""
        if history_context:
            for msg in history_context[-5:]:
                role = "User" if msg["role"] == "user" else "AI"
                history_text += f"{role}: {msg['content']}\n"

        # 2. Format Document Clues (Separating Law from Data)
        laws_found = []
        user_data_found = []
        
        if document_clues:
            for clue in document_clues:
                if "[LAW]" in clue:
                    laws_found.append(clue.replace("[LAW]", "").strip())
                elif "[USER DATA]" in clue:
                    user_data_found.append(clue.replace("[USER DATA]", "").strip())
                else:
                    user_data_found.append(clue) # Default to data if unsure

        # Build the Context Section
        context_text = ""
        if laws_found:
            context_text += "📚 RELEVANT TAX LAWS & RULES:\n"
            for i, law in enumerate(laws_found):
                context_text += f"{i+1}. {law}\n"
            context_text += "\n"
            
        if user_data_found:
            context_text += "💰 USER FINANCIAL RECORDS:\n"
            for i, data in enumerate(user_data_found):
                context_text += f"{i+1}. {data}\n"

        # 3. Construct the "Consultant" Prompt
        # We check the user's entity type from the session (passed via arguments ideally, but we can instruct the AI to ask)
        prompt = f"""
        You are 8law, an elite AI Accountant and Tax Consultant.
        
        YOUR KNOWLEDGE BASE:
        {context_text}
        
        PREVIOUS CONVERSATION:
        {history_text}
        
        CURRENT QUESTION:
        {user_question}
        
        INSTRUCTIONS:
        1. **Analyze the User's Data:** Look at the 'USER FINANCIAL RECORDS' to see what they actually spent or earned.
        2. **Apply the Law:** Look at the 'RELEVANT TAX LAWS' to determine tax treatment (deductible, taxable, etc.).
        3. **Cite Your Sources:** When you use a rule, say "According to the Tax Act..." or "Based on the guide...".
        4. **Be Conservative:** If the law is unclear or missing, advise the user to consult a human CPA. Do not invent laws.
        5. **Context:** If the user is a Corporation vs Sole Proprietor, apply the rules differently if the text distinguishes them.
        
        Answer professionally but clearly.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-pro", 
                contents=prompt
            )
            
            # Show reasoning in the UI
            reasoning_steps = ["Model: Gemini 2.5 Pro"]
            if laws_found:
                reasoning_steps.append(f"📚 Cited {len(laws_found)} Legal Snippets")
            if user_data_found:
                reasoning_steps.append(f"💰 Analyzed {len(user_data_found)} Financial Records")
            
            if response.text:
                return {
                    "answer": response.text,
                    "reasoning": reasoning_steps
                }
            else:
                return {"answer": "I couldn't generate a response.", "reasoning": ["Empty Response"]}

        except Exception as e:
            return {"answer": f"⚠️ AI Provider Error: {str(e)}", "reasoning": ["Crash during API Call"]}
