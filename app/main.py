import streamlit as st
from google import genai

st.title("8law Model Finder 🕵️‍♂️")

# 1. SETUP
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
    st.success("✅ API Key found.")
else:
    st.error("❌ No API Key.")
    st.stop()

# 2. ASK GOOGLE FOR THE LIST
if st.button("List Available Models"):
    try:
        client = genai.Client(api_key=api_key)
        
        # This command asks Google: "What models can I use?"
        st.write("Contacting Google...")
        all_models = list(client.models.list())
        
        st.write("### 📋 Models Available to You:")
        found_flash = False
        
        for m in all_models:
            # We only care about models that generate content (chat)
            if "generateContent" in m.supported_generation_methods:
                st.code(m.name)  # This prints the EXACT name we need
                if "flash" in m.name:
                    found_flash = True

        if found_flash:
            st.success("✨ Good news! We found a Flash model in the list above. Copy that name exactly!")
        else:
            st.warning("No 'Flash' model found. Try using 'gemini-pro' or 'gemini-1.5-pro-latest'.")
            
    except Exception as e:
        st.error(f"Error listing models: {e}")
        
