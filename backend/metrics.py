"""
metrics.py
Metric contract and schemas for ML-style evaluation and hallucination control.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

# ---- Classification Metrics ----
class ClassificationMetrics(BaseModel):
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    confusion_matrix: Optional[Dict[str, int]] = None  # e.g., {'TP': 10, 'FP': 2, ...}
    auroc: Optional[float] = None
    support: Optional[int] = None
    notes: Optional[str] = None

# ---- Retrieval Metrics ----
class RetrievalMetrics(BaseModel):
    recall_at_k: Optional[float] = Field(None, alias="recall@k")
    precision_at_k: Optional[float] = Field(None, alias="precision@k")
    mrr: Optional[float] = None
    ndcg: Optional[float] = None
    k: Optional[int] = None
    notes: Optional[str] = None

# ---- Calibration Metrics ----
class CalibrationMetrics(BaseModel):
    ece: Optional[float] = None  # Expected Calibration Error
    brier_score: Optional[float] = None
    reliability_bins: Optional[List[Dict[str, Any]]] = None  # e.g., [{"bin": 0.1, "accuracy": 0.8}, ...]
    notes: Optional[str] = None

# ---- Hallucination-Specific Metrics ----
class HallucinationMetrics(BaseModel):
    unsupported_claim_rate: Optional[float] = None
    grounded_answer_rate: Optional[float] = None
    citation_coverage: Optional[float] = None
    notes: Optional[str] = None

# ---- Per-Run and Aggregate Metrics Artifact ----
class RunMetrics(BaseModel):
    run_id: str
    stage: str  # e.g., 'retrieval', 'entity_resolution', 'generation', etc.
    timestamp: Optional[str] = None
    classification: Optional[ClassificationMetrics] = None
    retrieval: Optional[RetrievalMetrics] = None
    calibration: Optional[CalibrationMetrics] = None
    hallucination: Optional[HallucinationMetrics] = None
    extra: Optional[Dict[str, Any]] = None
    version: str = "1.0"

class AggregateMetrics(BaseModel):
    metric_family: str  # e.g., 'classification', 'retrieval', etc.
    stage: str
    metrics: Dict[str, Any]
    run_ids: List[str]
    version: str = "1.0"

# ---- JSON Schema Export ----
if __name__ == "__main__":
    import json
    print(json.dumps(RunMetrics.schema(), indent=2))
    print(json.dumps(AggregateMetrics.schema(), indent=2))
