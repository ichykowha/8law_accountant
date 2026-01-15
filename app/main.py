import streamlit as st
import streamlit_authenticator as stauth
import os
import sys
import pandas as pd
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
        
        # Initialize Controller
        if 'accountant' not in st.session_state:
            try:
                st.session_state.accountant = PowerhouseAccountant()
            except Exception:
                pass

        # --- 1. IDENTITY SELECTOR 👔 ---
        st.header("🏢 Tax Profile")
        entity_type = st.radio(
            "I am acting as:",
            ["Personal", "Small Business (Sole Prop)", "Corporation", "Non-Profit / Charity"],
            index=0,
            help="This tells 8law which CRA Tax Rules apply (e.g., T2 vs T1044)."
        )
        st.session_state["entity_type"] = entity_type
        st.divider()
        
        # --- 2. DATA INGESTION ---
        st.header("📂 Data Ingestion")
        tab1, tab2 = st.tabs(["My Files", "Tax Library"])
        
        # TAB 1: USER DATA (Batch Upload)
        with tab1:
            uploaded_files = st.file_uploader(
                "Upload Financials (Batch Supported)", 
                type=["pdf", "xml", "csv"], 
                key="user_upload",
                accept_multiple_files=True  # Bulk Upload Active
            )
            
            if uploaded_files and 'accountant' in st.session_state:
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_files = len(uploaded_files)
                success_count = 0
                
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Processing {i+1}/{total_files}: {uploaded_file.name}...")
                    try:
                        temp_path = f"temp_{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        user_entity = st.session_state.get("entity_type", "Personal")
                        
                        st.session_state.accountant.process_document(
                            temp_path, 
                            current_user, 
                            doc_type="financial",
                            entity_type=user_entity
                        )
                        
                        if os.path.exists(temp_path): os.remove(temp_path)
                        success_count += 1
                    except Exception as e:
                        st.error(f"Error on {uploaded_file.name}: {e}")
                    
                    progress_bar.progress((i + 1) / total_files)
                
                status_text.success(f"✅ Batch Complete! {success_count}/{total_files} processed.")

        # TAB 2: TAX LIBRARY
        with tab2:
            st.info("Upload Tax Acts (XML/PDF) here.")
            lib_file = st.file_uploader("Upload Knowledge", type=["pdf", "xml"], key="lib_upload")
            
            if lib_file and 'accountant' in st.session_state:
                with st.spinner("Ingesting Knowledge Base..."):
                    temp_path = f"temp_{lib_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(lib_file.getbuffer())
                    
                    status = st.session_state.accountant.process_document(
                        temp_path, 
                        current_user, 
                        doc_type="library"
                    )
                    st.success(status)
                    if os.path.exists(temp_path): os.remove(temp_path)

        st.divider()

        # --- 3. REPORTS & AUDIT LOG ---
        st.header("📊 Tax Reports")
        if st.button("🔄 Refresh Ledger"):
            st.rerun()

        # A. AUDIT LOG (General Ledger) 📖
        try:
            response = supabase.table("transactions") \
                .select("*") \
                .eq("username", current_user) \
                .order("transaction_date", desc=True) \
                .execute()
            
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                # Calculate Totals
                if 'deductible_percent' in df.columns:
                    df['write_off_value'] = df['amount'] * (df['deductible_percent'] / 100)
                    total_write_off = df['write_off_value'].sum()
                    st.metric("💰 Total Tax Write-off", f"${total_write_off:,.2f}")

                st.subheader("📖 General Ledger")
                # Show key columns
                display_cols = ['receipt_number', 'transaction_date', 'vendor', 'item_description', 'amount', 'deductible_percent', 'audit_reasoning']
                available_cols = [c for c in display_cols if c in df.columns]
                
                st.dataframe(df[available_cols], hide_index=True, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Audit Pack", csv, "8law_ledger.csv", "text/csv")
            else:
                st.caption("No financial data found.")
        except Exception as e:
            st.error(f"Ledger Error: {e}")

        # --- 4. BRAIN TRAINING 🧠 ---
        st.divider()
        with st.expander("🧠 Teach 8law (Add Rules)"):
            with st.form("learning_form"):
                st.caption("Teach 8law a specific tax rule.")
                k_word = st.text_input("Keyword (Vendor/Item)", placeholder="e.g. Paintbrush")
                cat = st.text_input("Tax Category", placeholder="e.g. Art Supplies")
                deduct = st.number_input("Deductible %", min_value=0, max_value=100, step=50)
                
                if st.form_submit_button("Save Rule"):
                    try:
                        supabase.table("tax_learning_bank").insert({
                            "keyword": k_word,
                            "tax_category": cat,
                            "deductible_percent": deduct
                        }).execute()
                        st.success(f"Learned: {k_word} = {deduct}%")
                    except Exception as e:
                        st.error(f"Error: {e}")

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
