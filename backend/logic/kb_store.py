import os
from typing import Any, Dict, List, Optional, Tuple

from pinecone import Pinecone  # pinecone>=8


def _get_setting(name: str) -> str:
    """
    Prefer environment variables; optionally support Streamlit Secrets without importing streamlit at module import time.
    """
    v = os.getenv(name)
    if v:
        return v

    try:
        import streamlit as st  # lazy import
        v = st.secrets.get(name)  # type: ignore[attr-defined]
        if v:
            return str(v)
    except Exception:
        pass

    raise RuntimeError(f"Missing required setting: {name}")


def _pc() -> Pinecone:
    api_key = _get_setting("PINECONE_API_KEY")
    return Pinecone(api_key=api_key)


def get_index():
    index_name = _get_setting("PINECONE_INDEX")
    return _pc().Index(index_name)


def _index_dimension(idx) -> Optional[int]:
    """
    Try to discover index dimension. If unavailable, returns None.
    Pinecone Index objects typically expose describe_index_stats, but dimension can vary by API/version.
    """
    try:
        stats = idx.describe_index_stats()
        # Some versions expose dimension directly; others do not.
        dim = getattr(stats, "dimension", None)
        if isinstance(dim, int) and dim > 0:
            return dim
        # Sometimes dimension is on a dict payload
        if isinstance(stats, dict):
            dim = stats.get("dimension")
            if isinstance(dim, int) and dim > 0:
                return dim
    except Exception:
        pass
    return None


def _ensure_dim(vec: List[float], expected_dim: Optional[int], context: str) -> None:
    if expected_dim is None:
        return
    if len(vec) != expected_dim:
        raise ValueError(
            f"{context}: vector dimension {len(vec)} does not match index dimension {expected_dim}"
        )


def upsert_chunks(
    vectors: List[Tuple[str, List[float], Dict[str, Any]]],
    namespace: Optional[str] = None,
) -> Dict[str, Any]:
    """
    vectors: list of (id, vector, metadata)

    Requirements:
    - metadata MUST include 'text' (so retrieval can show the chunk content)
    """
    if not vectors:
        return {"upserted_count": 0}

    idx = get_index()
    expected_dim = _index_dimension(idx)

    payload = []
    for _id, vec, meta in vectors:
        if not _id or not isinstance(_id, str):
            raise ValueError("upsert_chunks: each id must be a non-empty string")

        if not isinstance(vec, list) or not vec:
            raise ValueError(f"upsert_chunks: vector for id={_id} must be a non-empty list[float]")

        _ensure_dim(vec, expected_dim, context=f"upsert_chunks(id={_id})")

        if not isinstance(meta, dict):
            raise ValueError(f"upsert_chunks: metadata for id={_id} must be a dict")

        if "text" not in meta:
            raise ValueError(f"upsert_chunks: metadata for id={_id} must include 'text'")

        payload.append({"id": _id, "values": vec, "metadata": meta})

    if namespace:
        return idx.upsert(vectors=payload, namespace=namespace)

    return idx.upsert(vectors=payload)


def query_chunks(
    vector: List[float],
    top_k: int = 6,
    filter: Optional[Dict[str, Any]] = None,
    namespace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(vector, list) or not vector:
        raise ValueError("query_chunks: vector must be a non-empty list[float]")

    if top_k <= 0:
        raise ValueError("query_chunks: top_k must be > 0")

    idx = get_index()
    expected_dim = _index_dimension(idx)
    _ensure_dim(vector, expected_dim, context="query_chunks")

    kwargs: Dict[str, Any] = dict(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
    )
    if filter:
        kwargs["filter"] = filter
    if namespace:
        kwargs["namespace"] = namespace

    res = idx.query(**kwargs)

    # Pinecone responses can be objects or dicts depending on version / transport.
    matches = getattr(res, "matches", None)
    if matches is None and isinstance(res, dict):
        matches = res.get("matches", [])
    matches = matches or []

    out: List[Dict[str, Any]] = []
    for m in matches:
        md = getattr(m, "metadata", None)
        if md is None and isinstance(m, dict):
            md = m.get("metadata", {})
        md = md or {}

        out.append(
            {
                "id": getattr(m, "id", None) if not isinstance(m, dict) else m.get("id"),
                "score": getattr(m, "score", None) if not isinstance(m, dict) else m.get("score"),
                "metadata": md,
            }
        )
    return out
