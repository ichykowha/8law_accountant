import os
import time
from typing import List, Optional

try:
    # OpenAI Python SDK v1.x
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    OpenAI = None  # type: ignore
    _OPENAI_IMPORT_ERROR = e
else:
    _OPENAI_IMPORT_ERROR = None


def _get_secret(name: str) -> Optional[str]:
    """
    Read from env first; then Streamlit secrets if available.
    Safe to import even when Streamlit isn't installed.
    """
    v = os.getenv(name)
    if v:
        return v

    try:
        import streamlit as st  # local import to avoid hard dependency
        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return None


def _require_secret(name: str) -> str:
    v = _get_secret(name)
    if not v:
        raise RuntimeError(
            f"Missing required secret '{name}'. "
            f"Set it in Streamlit Secrets or as an environment variable."
        )
    return v


def _get_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError(
            "Python package 'openai' is not installed (or failed to import). "
            "Add `openai>=1.40.0,<2` to requirements.txt and redeploy. "
            f"Import error: {type(_OPENAI_IMPORT_ERROR).__name__}: {_OPENAI_IMPORT_ERROR}"
        )

    api_key = _require_secret("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def embed_texts(
    texts: List[str],
    model: Optional[str] = None,
    batch_size: int = 96,
    max_retries: int = 4,
) -> List[List[float]]:
    """
    Generate embeddings for a list of strings using OpenAI embeddings.

    - Preserves input order.
    - Avoids empty strings (OpenAI rejects them).
    - Retries transient failures with exponential backoff.
    """
    if not texts:
        return []

    emb_model = model or _get_secret("OPENAI_EMBED_MODEL") or "text-embedding-3-small"

    cleaned: List[str] = []
    for t in texts:
        t2 = (t or "").strip()
        cleaned.append(t2 if t2 else " ")

    client = _get_client()
    all_vectors: List[List[float]] = []

    def call_batch(batch: List[str]) -> List[List[float]]:
        backoff = 1.0
        last_err: Exception | None = None

        for _ in range(max_retries):
            try:
                resp = client.embeddings.create(model=emb_model, input=batch)
                return [item.embedding for item in resp.data]
            except Exception as e:
                last_err = e
                time.sleep(backoff)
                backoff *= 2

        raise RuntimeError(
            f"OpenAI embeddings failed after retries: {type(last_err).__name__}: {last_err}"
        )

    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i : i + batch_size]
        vecs = call_batch(batch)

        if len(vecs) != len(batch):
            raise RuntimeError(
                f"Embedding response size mismatch: got {len(vecs)} vectors for {len(batch)} inputs"
            )

        all_vectors.extend(vecs)

    return all_vectors
