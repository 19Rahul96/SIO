"""The single audit contract reused across every layer.

Every produced artifact (entity, relation, chunk, metadata field, graph edge) can
carry an ``audit`` block so confidence, evidence, citations, trace and policy
decisions are explainable end-to-end. This is the backbone of the platform's
"progressively increase semantic trust" principle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def band_for(score: float) -> str:
    if score >= settings.band_high:
        return "high"
    if score >= settings.band_low:
        return "medium"
    return "low"


@dataclass
class Confidence:
    score: float
    band: str = ""
    formula_version: str = settings.formula_version

    def __post_init__(self) -> None:
        self.score = max(0.0, min(1.0, float(self.score)))
        if not self.band:
            self.band = band_for(self.score)


@dataclass
class Citation:
    source_id: str
    chunk_idx: Optional[int] = None
    excerpt: str = ""
    provenance: str = ""


@dataclass
class Trace:
    scorer: str
    stage: str
    version: str = settings.formula_version
    timestamp: str = field(default_factory=_now)
    decision_path: list = field(default_factory=list)


@dataclass
class Policy:
    action: str  # auto_accept | review_required | reject
    reason: str = ""
    mode: str = settings.governance_mode.value


@dataclass
class Audit:
    confidence: Confidence
    trace: Trace
    policy: Policy
    evidence: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": asdict(self.confidence),
            "evidence": self.evidence,
            "citations": [asdict(c) if not isinstance(c, dict) else c for c in self.citations],
            "trace": asdict(self.trace),
            "policy": asdict(self.policy),
        }


def make_audit(
    *,
    score: float,
    scorer: str,
    stage: str,
    action: str = "auto_accept",
    reason: str = "",
    evidence: Optional[dict] = None,
    citations: Optional[list] = None,
    decision_path: Optional[list] = None,
) -> dict[str, Any]:
    """Convenience builder returning a plain dict ready for JSON serialization."""
    return Audit(
        confidence=Confidence(score=score),
        trace=Trace(scorer=scorer, stage=stage, decision_path=decision_path or []),
        policy=Policy(action=action, reason=reason),
        evidence=evidence or {},
        citations=citations or [],
    ).to_dict()
