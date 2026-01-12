import streamlit as st
from google import genai

st.title("🔑 API Key Inspector")

# 1. Check for Key
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
    st.write(f"✅ Key found: ends in ...{api_key[-4:]}")
else:
    st.error("❌ No API Key found in secrets.")
    st.stop()

# 2. Ask Google what this Key can do
if st.button("List My Available Models"):
    try:
        client = genai.Client(api_key=api_key)
        st.info("Contacting Google's servers...")
        
        # Get the full list
        all_models = list(client.models.list())
        
        st.write("### 📋 Models You Are Allowed To Use:")
        
        count = 0
        for m in all_models:
            # We check if the model supports "generateContent" (Chatting)
            # We use a safe check to prevent crashing if attributes change
            actions = getattr(m, "supported_actions", [])
            
            if "generateContent" in actions:
                # Clean up the name (remove 'models/' prefix)
                clean_name = m.name.replace("models/", "")
                st.code(clean_name)
                count += 1
                
        if count == 0:
            st.warning("Your Key connects, but has access to 0 chat models. This usually means you need to enable the 'Generative Language API' in Google Cloud Console.")
        else:
            st.success(f"Found {count} usable models! Copy one of the names above.")

    except Exception as e:
        st.error(f"❌ Connection Failed: {str(e)}")
        st.write("If this fails, your API Key might be invalid or revoked.")
