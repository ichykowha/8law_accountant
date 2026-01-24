# app/client_manager.py
import streamlit as st
from app.supabase_auth import get_authed_client


def _load_clients():
    sb = get_authed_client()
    resp = sb.table("clients").select("id, display_name, entity_type, currency, created_at").order("created_at", desc=True).execute()
    return resp.data or []


def _create_client(display_name: str, entity_type: str, currency: str = "CAD") -> str:
    sb = get_authed_client()
    payload = {
        "display_name": display_name,
        "entity_type": entity_type,
        "currency": currency,
    }
    resp = sb.table("clients").insert(payload).execute()
    row = (resp.data or [None])[0]
    if not row or not row.get("id"):
        raise RuntimeError("Client creation failed (no id returned).")
    return row["id"]


def require_active_client():
    """
    Global Client Guard:
    If no active client is selected, show Client Dashboard and stop.
    """
    st.session_state.setdefault("current_client_id", None)
    st.session_state.setdefault("current_client_name", None)

    if st.session_state.get("current_client_id"):
        return

    render_client_dashboard()
    st.stop()


def render_client_dashboard():
    st.title("Client Dashboard")
    st.caption("Select an accounting file to continue, or create a new one. This prevents uploads to the wrong client.")

    try:
        clients = _load_clients()
    except Exception as e:
        st.error(f"Failed to load clients: {type(e).__name__}: {e}")
        return

    if clients:
        name_to_id = {c["display_name"]: c["id"] for c in clients}
        selected = st.selectbox(
            "Select an existing client file",
            options=["Select a client..."] + list(name_to_id.keys()),
            index=0,
        )

        if selected != "Select a client...":
            if st.button("Open selected client", type="primary"):
                st.session_state["current_client_id"] = name_to_id[selected]
                st.session_state["current_client_name"] = selected
                st.rerun()
    else:
        st.info("No clients yet. Create your first accounting file below.")

    st.markdown("---")
    st.subheader("Create a new accounting file")

    with st.form("create_client_form"):
        display_name = st.text_input("Client name", placeholder="e.g., Matt Grapko (Personal) or ABC Ltd")
        entity_type = st.selectbox("Entity type", ["Individual", "Corporation"], index=0)
        currency = st.selectbox("Currency", ["CAD", "USD"], index=0)
        submitted = st.form_submit_button("Create and open", type="primary")

    if submitted:
        dn = (display_name or "").strip()
        if not dn:
            st.warning("Client name is required.")
            return
        try:
            client_id = _create_client(dn, entity_type, currency=currency)
            st.session_state["current_client_id"] = client_id
            st.session_state["current_client_name"] = dn
            st.success(f"Created and opened: {dn}")
            st.rerun()
        except Exception as e:
            st.error(f"Client creation failed: {type(e).__name__}: {e}")
