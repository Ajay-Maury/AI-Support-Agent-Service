"""
Local embedding service using sentence-transformers (all-MiniLM-L6-v2).
Free, no API key needed, 384-dimensional vectors.
Model is downloaded once and cached in /tmp/hf_cache.
"""

import os
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.core.config import settings

os.environ["TRANSFORMERS_CACHE"] = "/tmp/hf_cache"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load model once and keep in memory."""
    print(f"📦  Loading embedding model: {settings.embedding_model}")
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts.
    Returns a list of 384-dimensional float vectors.
    """
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Embed a single string — convenience wrapper."""
    return embed_texts([text])[0]
