import streamlit as st
import streamlit_authenticator as stauth
import os
import sys
from supabase import create_client, Client

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from controller import PowerhouseAccountant

# --- 1. CONFIG ---
st.set_page_config(page_title="8law Accountant", page_icon="💰", layout="wide")

# --- 2. SETUP DATABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Database Init Error: {e}")
        return None

supabase = init_connection()

# Helper: Load History with Diagnostics
def load_history(username):
    if not supabase: return []
    try:
        response = supabase.table("chat_history") \
            .select("*") \
            .eq("username", username) \
            .order("created_at") \
            .execute()
        return response.data
    except Exception as e:
        st.error(f"❌ Load History Error: {e}")
        return []

# Helper: Save Message
def save_message(username, role, content):
    if not supabase: return
    try:
        data = {"username": username, "role": role, "content": content}
        supabase.table("chat_history").insert(data).execute()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 3. AUTH CONFIG ---
def get_mutable_config():
    secrets = st.secrets
    return {
        "credentials": {
            "usernames": {
                u: dict(d) for u, d in secrets["credentials"]["usernames"].items()
            }
        },
        "cookie": dict(secrets["cookie"]),
        "preauthorized": dict(secrets["preauthorized"])
    }

try:
    config = get_mutable_config()
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
except Exception as e:
    st.error(f"Auth Error: {e}")
    st.stop()

# --- 4. APP INTERFACE ---

# Login Screen
if st.session_state.get("authentication_status") is None or st.session_state["authentication_status"] is False:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.header("🔐 8law Secure Login")
        authenticator.login()
        if st.session_state["authentication_status"] is False:
            st.error('❌ Username/password is incorrect')

# Main App (Logged In)
elif st.session_state["authentication_status"]:
    current_user = st.session_state["username"]
    
    # --- DIAGNOSTIC SIDEBAR ---
    with st.sidebar:
        st.write(f"User: **{current_user}**")
        authenticator.logout('Logout', 'main')
        st.divider()
        
        # Test Database Connection visibly
        st.subheader("🔍 Diagnostics")
        if supabase:
            st.success("✅ Database Connected")
            # Count rows for this user
            test_rows = load_history(current_user)
            st.info(f"📂 Memories found: {len(test_rows)}")
        else:
            st.error("❌ Database Disconnected")

        # Initialize Logic
        if 'accountant' not in st.session_state:
            st.session_state.accountant = PowerhouseAccountant()

    # --- MAIN CHAT AREA ---
    st.title("8law Super Accountant")

    # LOAD HISTORY (The fix for missing bubbles)
    if "messages" not in st.session_state:
        st.session_state.messages = load_history(current_user)

    # DISPLAY HISTORY
    for message in st.session_state.messages:
        if "role" in message and "content" in message:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # HANDLE INPUT
    if prompt := st.chat_input("Ask about your finances..."):
        # User Message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(current_user, "user", prompt)

        # AI Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Grab history for context
                history = st.session_state.messages[:-1]
                
                # --- VISUAL PROOF OF MEMORY ---
                st.info(f"🧠 I am reading {len(history)} previous messages as context.")
                # ------------------------------

                response_data = st.session_state.accountant.process_input(prompt, history)
                
                answer = response_data.get("answer", "⚠️ No answer provided.")
                reasoning = response_data.get("reasoning", [])
                
                st.markdown(answer)
                with st.expander("View Logic"):
                    st.write(reasoning)
        
        # Save AI Message
        st.session_state.messages.append({"role": "assistant", "content": answer})
        save_message(current_user, "assistant", answer)
