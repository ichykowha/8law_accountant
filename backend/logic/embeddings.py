import os
import time
from typing import List, Optional

from openai import OpenAI


def _require_value(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required configuration value: {name}")
    return value


def _get_api_key() -> str:
    """
    Prefer environment variable; optionally support Streamlit Secrets without importing streamlit at module import time.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    # Optional: if running in Streamlit, allow st.secrets["OPENAI_API_KEY"]
    try:
        import streamlit as st  # lazy import
        api_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
        if api_key:
            return api_key
    except Exception:
        pass

    return _require_value("OPENAI_API_KEY", None)


def _get_client() -> OpenAI:
    return OpenAI(api_key=_get_api_key())


def embed_texts(
    texts: List[str],
    model: Optional[str] = None,
    batch_size: int = 96,
    max_retries: int = 4,
) -> List[List[float]]:
    """
    Generate embeddings for a list of strings using OpenAI embeddings.

    - Returns embeddings in the same order as input texts.
    - Uses conservative batching to reduce request-size / token-limit risk.
    """
    if not texts:
        return []

    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    if max_retries <= 0:
        raise ValueError("max_retries must be > 0")

    # Default model is 3-small; allow override via env or function param.
    emb_model = model or os.getenv("OPENAI_EMBED_MODEL") or "text-embedding-3-small"

    # Embedding inputs should not be empty strings.
    cleaned: List[str] = []
    for t in texts:
        t2 = (t or "").strip()
        cleaned.append(t2 if t2 else " ")  # single space avoids empty-string rejection

    client = _get_client()
    all_vectors: List[List[float]] = []

    def call_batch(batch: List[str]) -> List[List[float]]:
        backoff = 1.0
        last_err: Optional[Exception] = None

        for _ in range(max_retries):
            try:
                resp = client.embeddings.create(
                    model=emb_model,
                    input=batch,
                )

                # Defensive ordering: if indices exist, sort by them.
                data = list(resp.data)
                if data and hasattr(data[0], "index"):
                    data.sort(key=lambda x: x.index)

                return [item.embedding for item in data]

            except Exception as e:
                last_err = e
                time.sleep(backoff)
                backoff = min(backoff * 2, 16.0)

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
