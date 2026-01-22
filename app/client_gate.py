# app/client_gate.py
from __future__ import annotations

import uuid
from typing import Optional, Dict, Any, List

import streamlit as st
from supabase import Client

from app.auth_supabase import AuthUser


def _get_supabase_from_frontend() -> Client:
    """
    Uses the same secrets as auth_supabase, but we keep this import local to avoid circular imports.
    """
    from app.auth_supabase import _supabase  # type: ignore
    return _supabase()


def _fetch_clients(sb: Client, user_id: str) -> List[Dict[str, Any]]:
    # You must create the `clients` table in Supabase later (Part 2 SQL).
    # For now, we assume columns: id (uuid), created_by (uuid), display_name (text), created_at (timestamptz)
    resp = sb.table("clients").select("id, display_name, created_at").eq("created_by", user_id).order("created_at", desc=True).execute()
    data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
    return data or []


def _create_client(sb: Client, user_id: str, display_name: str) -> Optional[str]:
    new_id = str(uuid.uuid4())
    payload = {"id": new_id, "created_by": user_id, "display_name": display_name}
    resp = sb.table("clients").insert(payload).execute()
    data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
    if data and isinstance(data, list) and data[0].get("id"):
        return str(data[0]["id"])
    return new_id


def require_client_selected(user: AuthUser) -> str:
    """
    Hard gate: blocks all non-client pages until a client is selected.
    Returns current_client_id.
    """
    if st.session_state.get("current_client_id"):
        return str(st.session_state["current_client_id"])

    st.title("Client Dashboard")
    st.info("Select an accounting file (client) to continue. Uploading and posting are disabled until a client is active.")

    sb = _get_supabase_from_frontend()

    # List clients
    try:
        clients = _fetch_clients(sb, user.user_id)
    except Exception as e:
        st.error(f"Unable to load clients: {type(e).__name__}: {e}")
        st.stop()
        raise

    if clients:
        options = {c["display_name"]: c["id"] for c in clients if c.get("display_name") and c.get("id")}
        chosen = st.selectbox("Select client", ["— Select —"] + list(options.keys()))
        if chosen != "— Select —":
            st.session_state["current_client_id"] = str(options[chosen])
            st.success(f"Active client set: {chosen}")
            st.rerun()
    else:
        st.warning("No clients found for this account yet.")

    st.markdown("---")
    st.subheader("Create a new client file")
    new_name = st.text_input("Client display name", placeholder="e.g., Matt Grapko Consulting Inc.")
    if st.button("Create Client", type="primary"):
        if not new_name.strip():
            st.error("Client name is required.")
        else:
            try:
                new_id = _create_client(sb, user.user_id, new_name.strip())
                st.session_state["current_client_id"] = str(new_id)
                st.success("Client created and selected.")
                st.rerun()
            except Exception as e:
                st.error(f"Create client failed: {type(e).__name__}: {e}")

    st.stop()
