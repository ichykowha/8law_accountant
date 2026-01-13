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

# --- 2. SETUP DATABASE & AUTH ---

# Initialize Database Connection
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("⚠️ Database Config Missing.")
        return None

supabase = init_connection()

# Helper: Load History from Cloud (DEBUG VERSION)
def load_history(username):
    if not supabase: return []
    try:
        # DEBUG SPY: Print to sidebar what we are looking for
        with st.sidebar:
            st.write(f"🕵️ Searching DB for user: `{username}`")
        
        # 1. Try to get EVERYTHING (easiest check)
        response = supabase.table("chat_history") \
            .select("*") \
            .eq("username", username) \
            .execute()
            
        # DEBUG SPY: Print what we found
        with st.sidebar:
            if response.data:
                st.success(f"✅ Found {len(response.data)} memories!")
                # st.write(response.data) # Uncomment to see raw data
            else:
                st.warning("⚠️ Found 0 memories.")
                
        return response.data
    except Exception as e:
        with st.sidebar:
            st.error(f"🛑 DB ERROR: {str(e)}")
        return []

# Helper: Save Message to Cloud
def save_message(username, role, content):
    if not supabase: return
    try:
        data = {
            "username": username,
            "role": role,
            "content": content
        }
        supabase.table("chat_history").insert(data).execute()
    except Exception as e:
        print(f"Write Error: {e}")

# Helper: Get Editable Config for Auth
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
except Exception as e:
    st.error(f"⚠️ Security Error: Could not load secrets. {e}")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- 3. LOGIN SCREEN ---
if st.session_state.get("authentication_status") is None or st.session_state["authentication_status"] is False:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.header("🔐 8law Secure Login")
        authenticator.login()
        if st.session_state["authentication_status"] is False:
            st.error('❌ Username/password is incorrect')

# --- 4. THE MAIN APP ---
elif st.session_state["authentication_status"]:
    
    current_user = st.session_state["username"]
    
    # Sidebar
    with st.sidebar:
        user_real_name = config['credentials']['usernames'][current_user]['name']
        st.write(f"Welcome, *{user_real_name}*")
        authenticator.logout('Logout', 'main')
        st.divider()

        # Initialize Accountant Logic
        if 'accountant' not in st.session_state:
            st.session_state.accountant = PowerhouseAccountant()
        
        # Document Uploader
        st.header("📂 Document Upload")
        uploaded_file = st.file_uploader("Drop Bank Statements (PDF)", type="pdf")
        
        if uploaded_file:
            with st.spinner("Reading document..."):
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                st.session_state.accountant.process_document(temp_path)
                st.success("Saved to Pinecone Memory 🧠")
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        st.divider()
        st.metric(label="System Status", value="Online", delta="Gemini 2.5 Pro")
        st.metric(label="Database", value="Connected", delta="Supabase")

    # --- CHAT INTERFACE ---
    st.title("8law Super Accountant")
    st.markdown("#### *Industry Grade Financial Intelligence*")

    # LOAD HISTORY (Only once per session)
    if "messages" not in st.session_state:
        # Pull from Database
        with st.spinner("Loading memory..."):
            db_history = load_history(current_user)
            st.session_state.messages = db_history if db_history else []

    # Display History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle New Input
    if prompt := st.chat_input("Ask about your finances..."):
        # 1. Show & Save User Message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(current_user, "user", prompt) # <--- SAVES TO CLOUD

      # 2. Generate AI Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # We pass the existing chat history to the brain
                # [:-1] prevents passing the message we just added (duplication check)
                history = st.session_state.messages[:-1]
                response_data = st.session_state.accountant.process_input(prompt, history)
                
                answer = response_data.get("answer", "⚠️ No answer provided.")
                reasoning = response_data.get("reasoning", [])
                
                st.markdown(answer)
                with st.expander("View Logic & Reasoning"):
                    st.write(reasoning)
        
        # 3. Save AI Message
        st.session_state.messages.append({"role": "assistant", "content": answer})
        save_message(current_user, "assistant", answer) # <--- SAVES TO CLOUD


