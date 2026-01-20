import os
from typing import Any, Dict, List, Optional, Tuple

from pinecone import Pinecone  # pinecone>=8

# Embeddings strategy:
# For now, assume you already have an embeddings method elsewhere or you will add it next.
# This file expects you to pass vectors in.


def _pc() -> Pinecone:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing PINECONE_API_KEY")
    return Pinecone(api_key=api_key)


def get_index():
    index_name = os.getenv("PINECONE_INDEX")
    if not index_name:
        raise RuntimeError("Missing PINECONE_INDEX")
    return _pc().Index(index_name)


def upsert_chunks(vectors: List[Tuple[str, List[float], Dict[str, Any]]]) -> Dict[str, Any]:
    """
    vectors: list of (id, vector, metadata) where metadata MUST include 'text'
    """
    idx = get_index()
    payload = []
    for _id, vec, meta in vectors:
        payload.append({"id": _id, "values": vec, "metadata": meta})
    return idx.upsert(vectors=payload)


def query_chunks(vector: List[float], top_k: int = 6, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    idx = get_index()
    res = idx.query(vector=vector, top_k=top_k, include_metadata=True, filter=filter)
    matches = getattr(res, "matches", None) or res.get("matches", [])  # defensive
    out = []
    for m in matches:
        md = getattr(m, "metadata", None) or m.get("metadata", {})
        out.append(
            {
                "id": getattr(m, "id", None) or m.get("id"),
                "score": getattr(m, "score", None) or m.get("score"),
                "metadata": md,
            }
        )
    return out
