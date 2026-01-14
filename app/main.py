import streamlit as st
import streamlit_authenticator as stauth
import os
import sys
import pandas as pd  # <--- NEW: For Excel/CSV
from supabase import create_client, Client

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import Controller
try:
    from controller import PowerhouseAccountant
except ImportError as e:
    st.error(f"⚠️ Critical System Error: Could not import Controller. {e}")
    st.stop()

# --- 1. CONFIG ---
st.set_page_config(page_title="8law Accountant", page_icon="💰", layout="wide")

# --- 2. SETUP DATABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

supabase = init_connection()

# Helper: Load History
def load_history(username):
    if not supabase: return []
    try:
        response = supabase.table("chat_history") \
            .select("*") \
            .eq("username", username) \
            .order("created_at") \
            .execute()
        return response.data
    except Exception:
        return []

# Helper: Save Message
def save_message(username, role, content):
    if not supabase: return
    try:
        data = {"username": username, "role": role, "content": content}
        supabase.table("chat_history").insert(data).execute()
    except Exception:
        pass

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
    
    # --- SIDEBAR ---
    with st.sidebar:
        user_real_name = config['credentials']['usernames'][current_user]['name']
        st.write(f"Welcome, *{user_real_name}*")
        authenticator.logout('Logout', 'main')
        st.divider()
        
        # Initialize Logic
        if 'accountant' not in st.session_state:
            try:
                st.session_state.accountant = PowerhouseAccountant()
            except Exception as e:
                st.error(f"⚠️ Brain Error: {e}")
            
        # 1. DOCUMENT UPLOAD
        st.header("📂 Document Upload")
        uploaded_file = st.file_uploader("Drop Bank Statements (PDF)", type="pdf")
        
        if uploaded_file and 'accountant' in st.session_state:
            with st.spinner("Processing..."):
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Call Librarian
                status = st.session_state.accountant.process_document(temp_path, current_user)
                st.success(status)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        st.divider()

        # 2. DATA EXPORT (NEW!) 📉
        st.header("📊 Reports")
        if st.button("🔄 Refresh Data"):
            st.rerun()

        # Fetch data from Supabase for the download button
        try:
            response = supabase.table("transactions").select("*").eq("username", current_user).execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                st.caption(f"Found {len(df)} transactions.")
                csv = df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv,
                    file_name="8law_transactions.csv",
                    mime="text/csv",
                )
            else:
                st.caption("No transactions found yet.")
        except Exception as e:
            st.error("DB Error")

        st.divider()
        st.caption("System Online | Encrypted")

    # --- MAIN CHAT AREA ---
    st.title("8law Super Accountant")

    # Load History (Once)
    if "messages" not in st.session_state:
        st.session_state.messages = load_history(current_user)

    # Display History
    for message in st.session_state.messages:
        if "role" in message and "content" in message:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Handle Input
    if prompt := st.chat_input("Ask about your finances..."):
        # User Message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(current_user, "user", prompt)

        # AI Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history = st.session_state.messages[:-1]
                
                if 'accountant' in st.session_state:
                    response_data = st.session_state.accountant.process_input(prompt, history)
                    
                    answer = response_data.get("answer", "⚠️ No answer provided.")
                    reasoning = response_data.get("reasoning", [])
                    
                    st.markdown(answer)
                    with st.expander("View Logic"):
                        st.write(reasoning)
                else:
                    st.error("⚠️ AI is offline.")
        
        # Save AI Message
        if 'answer' in locals():
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_message(current_user, "assistant", answer)
