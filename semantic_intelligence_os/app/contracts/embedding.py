"""Embedding utility with deterministic offline fallback.

Tries SentenceTransformers; if unavailable (offline / not installed) falls back to a
deterministic hashed bag-of-tokens vector so the whole pipeline still runs and all
similarity-based layers (semantic learning, canonicalization) remain functional.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Iterable

from ..config import settings

_TOKEN = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _model():
    try:  # pragma: no cover - depends on environment
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(settings.embedding_model)
    except Exception:
        return None


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    for tok in _TOKEN.findall((text or "").lower()):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(text: str) -> list[float]:
    model = _model()
    if model is not None:  # pragma: no cover
        v = model.encode([text or ""], normalize_embeddings=True)[0]
        return [float(x) for x in v]
    return _hash_embed(text or "", settings.embedding_dim)


def embed_many(texts: Iterable[str]) -> list[list[float]]:
    return [embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))
