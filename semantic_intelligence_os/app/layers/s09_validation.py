"""Step 9 — ML Validation & Accuracy Engine.

WHY: trust must be measured statistically, not asserted.
PRODUCES: extraction/relationship precision-recall-F1 vs an optional gold set,
          calibration error, retrieval metrics (Recall@K / MRR), hallucination risk,
          and an aggregate graph-trust score.
ORDERING: after EDA; before governance so governance can prioritize by risk.
ENABLES: the AI Trust Command Center and confidence-driven governance thresholds.

If no gold set exists it bootstraps one from high-confidence extractions so metrics
are always computable (clearly flagged as bootstrapped).
"""
from __future__ import annotations

from ..config import settings


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _calibration_error(entities: list[dict]) -> float:
    """ECE proxy: |mean_confidence - empirical_high_band_rate|."""
    if not entities:
        return 0.0
    confs = [e["audit"]["confidence"]["score"] for e in entities]
    mean_conf = sum(confs) / len(confs)
    high_rate = sum(1 for e in entities if e["audit"]["confidence"]["band"] == "high") / len(entities)
    return round(abs(mean_conf - high_rate), 4)


def validate(extraction: dict, eda: dict, gold: dict | None = None) -> dict:
    entities = extraction["entities"]
    rels = extraction["relationships"]

    # Bootstrap gold from high-confidence items when none supplied.
    bootstrapped = gold is None
    if bootstrapped:
        gold = {
            "entities": {e["text"].lower() for e in entities if e["audit"]["confidence"]["band"] == "high"},
            "relations": {
                (r["source"].lower(), r["relation"], r["target"].lower())
                for r in rels
                if r["relation"] != "related_to"
            },
        }

    pred_ents = {e["text"].lower() for e in entities}
    gold_ents = set(gold["entities"])
    ent_prf = _prf(len(pred_ents & gold_ents), len(pred_ents - gold_ents), len(gold_ents - pred_ents))

    pred_rels = {(r["source"].lower(), r["relation"], r["target"].lower()) for r in rels}
    gold_rels = set(gold["relations"])
    rel_prf = _prf(len(pred_rels & gold_rels), len(pred_rels - gold_rels), len(gold_rels - pred_rels))

    # Retrieval proxy metrics: rank entities by confidence, measure how quickly
    # gold entities surface (Recall@5 / MRR).
    ranked = sorted(entities, key=lambda e: -e["audit"]["confidence"]["score"])
    recall_at_5 = (
        sum(1 for e in ranked[:5] if e["text"].lower() in gold_ents) / min(5, len(gold_ents))
        if gold_ents
        else 0.0
    )
    mrr = 0.0
    for i, e in enumerate(ranked, 1):
        if e["text"].lower() in gold_ents:
            mrr = 1.0 / i
            break

    # Hallucination risk: share of generic / unsupported relations + drift signal.
    generic = sum(1 for r in rels if r["relation"] == "related_to")
    halluc_risk = round(
        0.6 * (generic / max(1, len(rels))) + 0.4 * min(1.0, eda["semantic_drift"]["count"] / 10.0), 4
    )

    ece = _calibration_error(entities)
    # Aggregate graph-trust score (higher is better).
    trust = round(
        0.30 * ent_prf["f1"]
        + 0.30 * rel_prf["f1"]
        + 0.20 * (1 - halluc_risk)
        + 0.20 * (1 - ece),
        4,
    )
    return {
        "source_id": extraction["source_id"],
        "gold_bootstrapped": bootstrapped,
        "entity_metrics": ent_prf,
        "relationship_metrics": rel_prf,
        "retrieval_metrics": {"recall_at_5": round(recall_at_5, 4), "mrr": round(mrr, 4)},
        "calibration_error": ece,
        "hallucination_risk": halluc_risk,
        "graph_trust_score": trust,
        "trust_band": "high" if trust >= settings.band_high else "medium" if trust >= settings.band_low else "low",
    }
