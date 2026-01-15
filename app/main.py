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
        
        if 'accountant' not in st.session_state:
            try:
                st.session_state.accountant = PowerhouseAccountant()
            except Exception:
                pass
        
        # --- TABS FOR UPLOAD ---
        st.header("📂 Data Ingestion")
        tab1, tab2 = st.tabs(["My Files", "Tax Library"])
        
        # TAB 1: USER DATA (Bank Statements / NOA / Slips)
        with tab1:
            # UPDATED: Added XML and CSV support
            uploaded_file = st.file_uploader("Upload Financials", type=["pdf", "xml", "csv"], key="user_upload")
            if uploaded_file and 'accountant' in st.session_state:
                with st.spinner("Reading Financials..."):
                    temp_path = f"temp_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Upload as "financial"
                    status = st.session_state.accountant.process_document(temp_path, current_user, doc_type="financial")
                    st.success(status)
                    if os.path.exists(temp_path): os.remove(temp_path)

        # TAB 2: TAX LIBRARY (Textbooks/Law)
        with tab2:
            st.info("Upload Tax Acts (XML/PDF) here.")
            # UPDATED: Added XML support for the Tax Act
            lib_file = st.file_uploader("Upload Knowledge", type=["pdf", "xml"], key="lib_upload")
            if lib_file and 'accountant' in st.session_state:
                with st.spinner("Ingesting Knowledge Base..."):
                    temp_path = f"temp_{lib_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(lib_file.getbuffer())
                    
                    # Upload as "library"
                    status = st.session_state.accountant.process_document(temp_path, current_user, doc_type="library")
                    st.success(status)
                    if os.path.exists(temp_path): os.remove(temp_path)

        st.divider()

        # --- IDENTITY SELECTOR 👔 ---
        st.header("🏢 Tax Profile")
        # UPDATED: Added Non-Profit
        entity_type = st.radio(
            "I am acting as:",
            ["Personal", "Small Business (Sole Prop)", "Corporation", "Non-Profit / Charity"],
            index=0,
            help="This tells 8law which CRA Tax Rules apply (e.g., T2 vs T1044)."
        )
        st.session_state["entity_type"] = entity_type
        
        st.divider()

        # --- REPORTS & HISTORY ---
        st.header("📊 Tax Data")
        if st.button("🔄 Refresh Data"):
            st.rerun()

        # 1. TAX HISTORY CARD (NOA) - NEW! 📜
        try:
            h_response = supabase.table("tax_history") \
                .select("*") \
                .eq("username", current_user) \
                .order("tax_year", desc=True) \
                .limit(1) \
                .execute()
            
            if h_response.data:
                history = h_response.data[0]
                st.subheader(f"📜 NOA ({history['tax_year']})")
                st.metric("RRSP Room", f"${history['rrsp_deduction_limit']:,.0f}")
                st.metric("Unused Tuition", f"${history['tuition_federal']:,.0f}")
                if history['capital_losses'] > 0:
                    st.warning(f"Loss Carryforward: ${history['capital_losses']:,.0f}")
                st.divider()
        except Exception:
            pass

        # 2. TAX SLIPS (T4s, etc) - NEW! 📑
        try:
            t_response = supabase.table("tax_slips").select("*").eq("username", current_user).execute()
            df_tax = pd.DataFrame(t_response.data)
            if not df_tax.empty:
                st.caption(f"📑 {len(df_tax)} Official Tax Slips")
                csv_tax = df_tax.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download T-Slips", csv_tax, "8law_tax_slips.csv", "text/csv")
        except Exception:
            pass

        # 3. TRANSACTIONS (Auto-Audited) 💳
        try:
            response = supabase.table("transactions").select("*").eq("username", current_user).execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
                st.write("---")
                st.caption(f"💳 {len(df)} Transactions Processed")
                
                # Calculate the "Real" Tax Write-off
                if 'deductible_percent' in df.columns:
                    # Logic: Amount * (Percent / 100)
                    df['write_off_value'] = df['amount'] * (df['deductible_percent'] / 100)
                    total_write_off = df['write_off_value'].sum()
                    
                    st.metric("💰 Total Tax Write-off", f"${total_write_off:,.2f}", help="Calculated based on CRA rules (e.g., 50% for meals)")
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Audited CSV", csv, "8law_audited.csv", "text/csv")
            else:
                st.caption("No financial data found.")
        except Exception:
            pass
            
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

