"""Platform configuration and the observe/enforce governance flag.

Every gate in the platform (ontology validation, graph consistency) ships behind
``GovernanceMode``. In ``observe_only`` (default) gates annotate verdicts but never
drop data; in ``enforce`` rejected candidates are routed to review instead of inserted.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class GovernanceMode(str, Enum):
    OBSERVE_ONLY = "observe_only"
    ENFORCE = "enforce"


# Repo-relative data root (semantic_intelligence_os/data).
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Settings:
    data_root: Path = DATA_ROOT
    governance_mode: GovernanceMode = GovernanceMode(
        os.getenv("SIO_GOVERNANCE_MODE", GovernanceMode.OBSERVE_ONLY.value)
    )
    # Chunking defaults (word-window fallback strategy).
    chunk_size_words: int = 400
    chunk_overlap_words: int = 60
    # Confidence bands shared across audit objects.
    band_high: float = 0.75
    band_low: float = 0.45
    # Canonicalization thresholds (mirrors proven values from the source platform).
    merge_threshold: float = 0.72
    review_threshold: float = 0.58
    # Embedding model; falls back to a deterministic hash embedder if unavailable.
    embedding_model: str = os.getenv("SIO_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    embedding_dim: int = 384
    formula_version: str = "v1"

    subdirs: tuple = field(
        default=(
            "sources",
            "lineage",
            "corpus",
            "chunks",
            "metadata",
            "entities",
            "eda",
            "validation",
            "governance",
            "canonical",
            "graph",
            "wiki",
            "semantic_memory",
        )
    )

    def ensure_dirs(self) -> None:
        for sub in self.subdirs:
            (self.data_root / sub).mkdir(parents=True, exist_ok=True)

    def dir(self, name: str) -> Path:
        p = self.data_root / name
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
settings.ensure_dirs()
