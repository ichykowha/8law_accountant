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
        """
        Arguments:
        - user_question: The new question
        - history_context: Previous chat messages
        - document_clues: A list of text snippets from PDF files
        """
        if not self.is_connected:
            return {"answer": "⚠️ System Error: API Key missing.", "reasoning": ["Connection Check Failed"]}

        # 1. Format History
        history_text = ""
        if history_context:
            for msg in history_context[-5:]:
                role = "User" if msg["role"] == "user" else "AI"
                history_text += f"{role}: {msg['content']}\n"

        # 2. Format Document Clues
        context_text = ""
        if document_clues:
            context_text = "RELEVANT FACTS FROM FILES:\n"
            for i, clue in enumerate(document_clues):
                context_text += f"Fact {i+1}: {clue}\n"

        # 3. Construct Prompt
        prompt = f"""
        You are 8law, an elite AI Accountant.
        
        {context_text}
        
        PREVIOUS CONVERSATION:
        {history_text}
        
        CURRENT USER QUESTION:
        {user_question}
        
        INSTRUCTIONS:
        - If the 'RELEVANT FACTS' contain the answer, use them explicitly.
        - Cite the facts if you use them (e.g., "According to your documents...").
        - If the answer is not in the facts, rely on general knowledge or the conversation history.
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-pro", 
                contents=prompt
            )
            
            # Show reasoning in the UI
            reasoning_steps = ["Checked Memory Context", "Model: Gemini 2.5 Pro"]
            if document_clues:
                reasoning_steps.append(f"Found {len(document_clues)} relevant document snippets.")
            else:
                reasoning_steps.append("No relevant documents found.")
            
            if response.text:
                return {
                    "answer": response.text,
                    "reasoning": reasoning_steps
                }
            else:
                return {"answer": "I couldn't generate a response.", "reasoning": ["Empty Response"]}

        except Exception as e:
            return {"answer": f"⚠️ AI Provider Error: {str(e)}", "reasoning": ["Crash during API Call"]}
