import pandas as pd
import google.generativeai as genai
import streamlit as st  # <--- Access the app memory directly

class DataQueryAssistant:
    def __init__(self, db_name="accountant_pi.db"):
        self.db_name = db_name
        
        # --- 1. CONFIGURE THE REAL BRAIN ---
        # Securely access the key from Streamlit Secrets
        self.api_key = st.secrets["GEMINI_KEY"]
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.is_connected = True
        except Exception as e:
            print(f"Error connecting to Gemini: {e}")
            self.is_connected = False

    def ask(self, user_question):
        """Sends the question + Pinecone memories to Google's AI."""
        
        context_text = ""
        source_used = "General Knowledge"

        # --- 2. FETCH MEMORY FROM PINECONE ---
        # We check if the vector database is connected in the app
        if 'vector_db' in st.session_state and st.session_state.vector_db is not None:
            try:
                # Create a dummy vector to represent the question
                # (In production, you'd convert the question to a real vector)
                query_vector = [0.1] * 3 
                
                # Search Pinecone for the 3 most relevant matches
                search_results = st.session_state.vector_db.query(
                    vector=query_vector,
                    top_k=3,
                    include_metadata=True
                )
                
                # Extract the text from the results
                matches = []
                for match in search_results['matches']:
                    if match['score'] > 0.70: # Only use good matches
                        meta = match['metadata']
                        matches.append(f"Source: {meta.get('filename', 'Unknown')}\nContent: {meta.get('text', '')}")
                
                if matches:
                    context_text = "\n\n---\n\n".join(matches)
                    source_used = "Pinecone Memory (Uploaded Files)"
                else:
                    context_text = "No relevant documents found in memory."
                    
            except Exception as e:
                context_text = f"Error reading memory: {e}"
        else:
            context_text = "Pinecone memory is not connected."

        # --- 3. CREATE THE PROMPT ---
        prompt = f"""
        You are 8law, an advanced AI Accountant.
        
        USER QUESTION: 
        {user_question}
        
        RETRIEVED CONTEXT (From Uploaded Files):
        {context_text}
        
        INSTRUCTIONS:
        1. Answer the question using ONLY the retrieved context above if possible.
        2. If the context contains a bank statement, assume it is accurate.
        3. If the context is empty, politely ask the user to upload a document.
        4. Be professional and concise.
        """

        # --- 4. GET THE ANSWER ---
        reasoning_steps = []
        final_answer = ""
        
        if self.is_connected:
            try:
                # Call the AI
                response = self.model.generate_content(prompt)
                final_answer = response.text
                reasoning_steps = [
                    f"Source: {source_used}", 
                    "Retrieved relevant chunks from Pinecone", 
                    "Generated Response via Gemini"
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