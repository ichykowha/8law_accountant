import streamlit as st
import os

# --- BYPASS DIAGNOSTIC TOOL ---
st.title("8law System Diagnostic 🛠️")

# 1. CHECK SECRETS
st.write("### 1. Checking Keys...")
if "GEMINI_KEY" in st.secrets:
    key_status = "✅ Found GEMINI_KEY"
    api_key = st.secrets["GEMINI_KEY"]
else:
    key_status = "❌ GEMINI_KEY Missing"
    api_key = None

st.write(key_status)

# 2. CHECK LIBRARY
st.write("### 2. Checking Google Library...")
try:
    from google import genai
    st.write("✅ google-genai library installed (New 2026 Version)")
except ImportError:
    st.write("❌ Library missing. Update requirements.txt to include: google-genai")
    st.stop()

# 3. TEST CONNECTION
st.write("### 3. Testing Brain Connection...")
if st.button("Test Connection Now"):
    if not api_key:
        st.error("Cannot test without a Key.")
    else:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents="Reply with exactly three words: System is operational."
            )
            st.success(f"🎉 SUCCESS! The Brain Replied: '{response.text}'")
            st.balloons()
        except Exception as e:
            st.error(f"💀 CONNECTION DIED: {e}")
            st.write("Common fixes:")
            st.write("- If error is '404', the model name might be wrong.")
            st.write("- If error is 'Auth', the Key is wrong.")
