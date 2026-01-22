# app/client_gate.py
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import streamlit as st
from supabase import Client, create_client

SUPABASE_URL_KEY = "SUPABASE_URL"
SUPABASE_ANON_KEY_KEY = "SUPABASE_ANON_KEY"


def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v:
        return v
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _supabase() -> Client:
    url = _get_secret(SUPABASE_URL_KEY)
    anon = _get_secret(SUPABASE_ANON_KEY_KEY)
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY")
    return create_client(url, anon)


def _sb_with_session() -> Client:
    """
    Ensures Supabase requests include the current user session so RLS applies.
    """
    sb = _supabase()
    access = st.session_state.get("auth_access_token")
    refresh = st.session_state.get("auth_refresh_token") or ""
    if access:
        try:
            sb.auth.set_session(access, refresh)
        except Exception:
            # If this fails, RLS-protected calls will likely fail as unauthorized.
            pass
    return sb


def clear_selected_client() -> None:
    st.session_state["current_client_id"] = None
    st.session_state["current_client_name"] = None


def list_clients() -> List[dict]:
    sb = _sb_with_session()
    resp = (
        sb.table("clients")
        .select("client_id, display_name, is_active, created_at")
        .order("created_at", desc=False)
        .execute()
    )
    return resp.data or []


def create_new_client(display_name: str, entity_type: Optional[str] = None) -> dict:
    """
    Inserts a new client row. RLS insert policy must allow authenticated user insert.
    created_by should be filled by DB default (auth.uid()) if you configured it that way,
    but we also pass it if user id is available in session user object elsewhere.
    """
    sb = _sb_with_session()

    payload = {
        "display_name": display_name.strip(),
        "entity_type": entity_type or None,
        "is_active": True,
    }

    resp = sb.table("clients").insert(payload).execute()
    data = resp.data or []
    if not data:
        raise RuntimeError("Insert returned no rows.")
    return data[0]


def require_client_selected() -> Tuple[str, str]:
    """
    Global Session Guard:
    - If no client selected, renders the Client Dashboard and stops execution.
    - Returns (client_id, client_name) once selected.
    """
    st.session_state.setdefault("current_client_id", None)
    st.session_state.setdefault("current_client_name", None)

    if st.session_state["current_client_id"] and st.session_state["current_client_name"]:
        return st.session_state["current_client_id"], st.session_state["current_client_name"]

    st.title("Client Dashboard")
    st.caption("Select an accounting file before you can upload documents or post transactions.")

    try:
        clients = list_clients()
    except Exception as e:
        st.error(f"Unable to load clients. {type(e).__name__}: {e}")
        st.info(
            "This typically means the Supabase auth session is missing/invalid, "
            "or the RLS policy blocked the request."
        )
        st.stop()

    active_clients = [c for c in clients if c.get("is_active") and c.get("display_name") and c.get("client_id")]
    name_to_id = {c["display_name"]: c["client_id"] for c in active_clients}
    options = ["Select a Client..."] + sorted(name_to_id.keys())

    selected = st.selectbox("Active File", options, index=0)

    col1, col2 = st.columns([1, 1])
    with col1:
        if selected != "Select a Client...":
            if st.button("Open Client File", type="primary"):
                st.session_state["current_client_id"] = name_to_id[selected]
                st.session_state["current_client_name"] = selected
                st.rerun()

    with col2:
        if st.button("Refresh"):
            st.rerun()

    st.markdown("---")
    st.subheader("Create New Client File")

    with st.form("create_client_form"):
        new_name = st.text_input("Display name", placeholder="e.g., 5law Industries Inc.")
        entity_type = st.selectbox(
            "Entity type (optional)",
            ["(optional)", "sole_prop", "partnership", "corporation", "trust", "nonprofit", "other"],
            index=0,
        )
        submitted = st.form_submit_button("Create Client", type="primary")

    if submitted:
        if not new_name.strip():
            st.error("Display name is required.")
        else:
            try:
                created = create_new_client(
                    display_name=new_name,
                    entity_type=None if entity_type == "(optional)" else entity_type,
                )
                st.success(f"Created client: {created.get('display_name')}")
                st.session_state["current_client_id"] = created.get("client_id")
                st.session_state["current_client_name"] = created.get("display_name")
                st.rerun()
            except Exception as e:
                st.error(f"Create failed: {type(e).__name__}: {e}")

    st.stop()
