"""
app/services/embedding_service.py

Semantic embeddings via DashScope text-embedding-v3.

Used to make memory retrieval semantically aware — the coach finds
memories that are *relevant to the current session context*, not just
the most recently updated ones.

Model: text-embedding-v3 (1024 dimensions)
       Same API key as the rest of the Qwen/DashScope services.
       Zero additional credential setup required.

Design decision: embeddings are stored as JSON-serialised float lists
in the `embedding` TEXT column. This works on both SQLite (dev) and
PostgreSQL (production) without a vector extension. Cosine similarity
is computed in Python with numpy — fast enough for any realistic number
of memories per learner (typically 20–200).
"""

import json
import os
from typing import Optional

import numpy as np

from app.utils.logger import get_logger

logger = get_logger("embedding_service")

EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIMS  = 1024


def _get_client():
    """Lazy import so the app starts even if dashscope isn't installed."""
    from dashscope import TextEmbedding
    return TextEmbedding


def embed_text(text: str) -> Optional[list[float]]:
    """
    Embeds a single text string using DashScope text-embedding-v3.
    Returns a float list of length EMBEDDING_DIMS, or None on failure.

    Failures are non-fatal — the memory is still saved, just without
    an embedding. Retrieval falls back to the spaced-repetition scorer.
    """
    try:
        TextEmbedding = _get_client()
        response = TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=text,
            dimension=EMBEDDING_DIMS,
        )
        if response.status_code == 200:
            return response.output["embeddings"][0]["embedding"]
        logger.warning(f"Embedding API returned {response.status_code}: {response.message}")
    except Exception as e:
        logger.warning(f"Embedding failed (non-fatal): {e}")
    return None


def serialise(embedding: list[float]) -> str:
    return json.dumps(embedding)


def deserialise(text: str) -> Optional[list[float]]:
    try:
        return json.loads(text)
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity in [0, 1].
    Returns 0.0 on zero-vector or dimension mismatch.
    """
    try:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom < 1e-9:
            return 0.0
        return float(np.dot(va, vb) / denom)
    except Exception:
        return 0.0
