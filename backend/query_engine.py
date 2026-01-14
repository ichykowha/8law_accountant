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

        # 3. Construct the "Context-Aware" Prompt
        prompt = f"""
        You are 8law, an elite AI Accountant and Tax Consultant.
        
        CURRENT ENTITY PROFILE: {st.session_state.get('entity_type', 'Unknown')}
        
        YOUR KNOWLEDGE BASE:
        {context_text}
        
        PREVIOUS CONVERSATION:
        {history_text}
        
        CURRENT QUESTION:
        {user_question}
        
        INSTRUCTIONS:
        1. **Check the Entity Type:**
           - If 'Personal': Focus on T1 General, T4s, and personal credits.
           - If 'Corporation': Focus on T2 returns, shareholder loans, and dividends.
           - If 'Non-Profit / Charity': Focus on NPO rules (T1044), non-taxable status, and fund restrictions. Do NOT give advice on 'maximizing profit'.
           
        2. **Analyze the Data:** Look at 'USER FINANCIAL RECORDS' for facts.
        3. **Apply the Law:** Look at 'RELEVANT TAX LAWS' for the rules.
        4. **Cite Sources:** explicitly mention specific Tax Act sections or Guides found in the library.
        
        Answer professionally.
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

