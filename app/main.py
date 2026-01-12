import streamlit as st
from google import genai

st.title("8law Model Finder v2 🕵️‍♂️")

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
        
        st.write("Contacting Google...")
        # Get the raw list
        all_models = list(client.models.list())
        
        st.write("### 📋 Models You Can Use:")
        
        found_flash = False
        
        for m in all_models:
            # CHECK FOR THE NEW LABEL: "supported_actions"
            # We only want models that can "generateContent" (chat)
            if hasattr(m, 'supported_actions') and "generateContent" in m.supported_actions:
                # Print the CLEAN name (e.g., "gemini-1.5-flash")
                # We strip the "models/" part if it's there to make it easy to copy
                clean_name = m.name.replace("models/", "")
                st.code(clean_name)
                
                if "flash" in clean_name:
                    found_flash = True

        if found_flash:
            st.success("✨ Success! Copy one of the 'flash' names above.")
        else:
            st.warning("No 'Flash' model found. Try 'gemini-pro'.")
            
    except Exception as e:
        st.error(f"Error listing models: {e}")

