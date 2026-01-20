import os
import time
from typing import List, Optional

from openai import OpenAI


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _get_client() -> OpenAI:
    # Uses standard OPENAI_API_KEY convention.
    api_key = _require_env("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def embed_texts(
    texts: List[str],
    model: Optional[str] = None,
    batch_size: int = 96,
    max_retries: int = 4,
) -> List[List[float]]:
    """
    Generate embeddings for a list of strings using OpenAI embeddings.

    Notes:
    - The OpenAI embeddings endpoint accepts a string or a list of strings as input. :contentReference[oaicite:2]{index=2}
    - Keep batching conservative to avoid hitting request-size limits.
    - Returns embeddings in the same order as input texts.
    """
    if not texts:
        return []

    # Default model is 3-small; allow override via env or function param.
    emb_model = model or os.getenv("OPENAI_EMBED_MODEL") or "text-embedding-3-small"

    # Basic sanitation: embeddings input must not contain empty strings.
    cleaned: List[str] = []
    for t in texts:
        t2 = (t or "").strip()
        cleaned.append(t2 if t2 else " ")  # single space avoids empty-string rejection

    client = _get_client()

    all_vectors: List[List[float]] = []

    def call_batch(batch: List[str]) -> List[List[float]]:
        # Retry on transient failures (rate limit / network).
        backoff = 1.0
        last_err: Exception | None = None

        for _ in range(max_retries):
            try:
                resp = client.embeddings.create(
                    model=emb_model,
                    input=batch,
                )
                # Response objects are structured; embeddings are in resp.data[i].embedding. :contentReference[oaicite:3]{index=3}
                return [item.embedding for item in resp.data]
            except Exception as e:
                last_err = e
                time.sleep(backoff)
                backoff *= 2

        raise RuntimeError(f"OpenAI embeddings failed after retries: {type(last_err).__name__}: {last_err}")

    # Batch through the input list
    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i : i + batch_size]
        vecs = call_batch(batch)
        if len(vecs) != len(batch):
            raise RuntimeError(f"Embedding response size mismatch: got {len(vecs)} vectors for {len(batch)} inputs")
        all_vectors.extend(vecs)

    return all_vectors
