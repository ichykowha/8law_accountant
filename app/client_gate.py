# app/client_gate.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import streamlit as st

from app.auth_supabase import supabase_for_user


def _as_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    return getattr(row, "__dict__", {}) or {}


def _fetch_clients() -> Tuple[bool, str, list[dict]]:
    """
    Returns (ok, error_message, client_rows)

    Relies on RLS to filter to the authenticated user's rows.
    """
    try:
        sb = supabase_for_user()
        resp = (
            sb.table("clients")
            .select("id, display_name, entity_type, currency, created_at")
            .order("display_name")
            .execute()
        )
        rows = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None) or []
        return True, "", [dict(r) for r in rows]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", []


def _insert_client(display_name: str, entity_type: str, currency: str) -> Tuple[bool, str]:
    """
    Inserts a client row.

    - created_by is omitted and will default to auth.uid()
    - handles unique constraint (created_by, display_name)
    """
    display_name = (display_name or "").strip()
    if not display_name:
        return False, "Client display name is required."

    entity_type = (entity_type or "Individual").strip() or "Individual"
    currency = (currency or "CAD").strip() or "CAD"

    try:
        sb = supabase_for_user()
        payload = {
            "display_name": display_name,
            "entity_type": entity_type,
            "currency": currency,
        }
        sb.table("clients").insert(payload).execute()
        return True, ""
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        # Best-effort detection for Postgres unique violation
        if "clients_unique_display_name_per_user" in msg or "duplicate key value violates unique constraint" in msg:
            return False, "A client with that display name already exists for your account."
        return False, msg


def require_client_selected(user: dict) -> Optional[dict]:
    """
    Gate: user must select (or create) a client before proceeding.

    Session keys:
      - selected_client_id
      - selected_client_display_name
    """
    st.session_state.setdefault("selected_client_id", None)
    st.session_state.setdefault("selected_client_display_name", None)

    # Already selected
    if st.session_state.get("selected_client_id"):
        return {
            "id": st.session_state["selected_client_id"],
            "display_name": st.session_state.get("selected_client_display_name"),
        }

    st.title("Select Client")

    ok, err, clients = _fetch_clients()
    if not ok:
        st.error("Unable to load clients from Supabase (RLS + JWT required).")
        st.code(err)
        st.stop()

    # Create new client panel
    with st.expander("Create new client", expanded=(len(clients) == 0)):
        new_display_name = st.text_input("Client display name", key="client_create_display_name")
        entity_type = st.selectbox("Entity type", ["Individual", "Corporation", "Sole Proprietor", "Partnership"], index=0)
        currency = st.selectbox("Currency", ["CAD", "USD"], index=0)

        if st.button("Create Client", type="primary", key="client_create_btn"):
            ok2, err2 = _insert_client(new_display_name, entity_type, currency)
            if not ok2:
                st.error("Create client failed.")
                st.write(err2)
            else:
                st.success("Client created.")
                st.rerun()

    if not clients:
        st.info("No clients exist yet. Create one above to proceed.")
        st.stop()

    # Select existing client
    options = {f"{c['display_name']} ({c['id']})": c for c in clients}
    pick = st.selectbox("Existing clients", list(options.keys()), key="client_select_existing")

    if st.button("Continue", type="primary", key="client_continue_btn"):
        chosen = options.get(pick)
        if not chosen:
            st.error("Select a client to continue.")
        else:
            st.session_state["selected_client_id"] = chosen["id"]
            st.session_state["selected_client_display_name"] = chosen["display_name"]
            st.rerun()

    st.stop()
    return None
