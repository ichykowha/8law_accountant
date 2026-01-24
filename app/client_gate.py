# app/client_gate.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import streamlit as st

from app.auth_supabase import supabase_for_user

__all__ = [
    "require_client_selected",
    "clear_selected_client",
    "get_selected_client",
]

# -----------------------------------------------------------------------------
# Session keys (single source of truth)
# -----------------------------------------------------------------------------
_SELECTED_CLIENT_ID_KEY = "selected_client_id"
_SELECTED_CLIENT_NAME_KEY = "selected_client_name"


def _as_dict(row: Any) -> Dict[str, Any]:
    """
    Normalize PostgREST rows into plain dicts.
    The supabase-py client may return dicts already; keep deterministic behavior.
    """
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    # Fallback for objects with __dict__
    try:
        return dict(row.__dict__)
    except Exception:
        return {"value": row}


def get_selected_client() -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (client_id, client_name) from session state, if set.
    """
    return (
        st.session_state.get(_SELECTED_CLIENT_ID_KEY),
        st.session_state.get(_SELECTED_CLIENT_NAME_KEY),
    )


def clear_selected_client() -> None:
    """
    Clears client selection from session_state.

    This must exist because app/frontend.py calls it when user clicks 'Switch Client'
    or on logout.
    """
    st.session_state.pop(_SELECTED_CLIENT_ID_KEY, None)
    st.session_state.pop(_SELECTED_CLIENT_NAME_KEY, None)


def require_client_selected() -> Tuple[str, str]:
    """
    HARD gate: forces the user to select a client before accessing the rest of the app.

    Returns:
        (client_id, client_name) – always non-empty once selected.

    Data access is performed via supabase_for_user() so RLS is enforced.
    """
    client_id, client_name = get_selected_client()
    if client_id and client_name:
        return str(client_id), str(client_name)

    st.title("Select Client")

    sb = supabase_for_user()

    # Pull available clients (RLS should scope to created_by = auth.uid())
    try:
        resp = (
            sb.table("clients")
            .select("id, display_name")
            .order("display_name", desc=False)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        st.error(f"Failed to load clients: {type(e).__name__}: {e}")
        st.stop()
        raise

    if not rows:
        st.warning("No clients found for this account yet.")
        st.info("Go to 'Client Management' after login (or seed one row in public.clients).")
        st.stop()
        raise RuntimeError("No clients available")

    # Deterministic mapping for selectbox
    rows = [_as_dict(r) for r in rows]
    options = [(str(r["id"]), str(r.get("display_name") or "—")) for r in rows]

    labels = [name for (_id, name) in options]
    selected_label = st.selectbox("Client", labels, index=0)

    # Resolve selection back to id (first match is deterministic due to unique constraint)
    selected_id = None
    for cid, name in options:
        if name == selected_label:
            selected_id = cid
            break

    if st.button("Continue", type="primary"):
        if not selected_id:
            st.error("Select a client.")
            st.stop()
            raise RuntimeError("Client selection missing")

        st.session_state[_SELECTED_CLIENT_ID_KEY] = selected_id
        st.session_state[_SELECTED_CLIENT_NAME_KEY] = selected_label
        st.rerun()

    st.stop()
    raise RuntimeError("Client not selected yet")
