import math
from collections import defaultdict
from typing import Any, Dict, List


RELATION_PRIOR = {
    "has_revenue": 0.9,
    "owns": 0.85,
    "employs": 0.8,
    "located_in": 0.78,
    "occurred_at": 0.75,
    "related_to": 0.6,
    "cross_source_related": 0.8,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def score_entities(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    freq = defaultdict(int)
    for ent in entities:
        freq[str(ent.get("text") or "").strip().lower()] += 1

    scored: List[Dict[str, Any]] = []
    low_confidence = 0
    for ent in entities:
        text = str(ent.get("text") or "").strip()
        norm = text.lower()
        label = str(ent.get("label") or "ENTITY")
        occurrences = ent.get("chunk_occurrences", []) or []
        mention_count = 1 + len(occurrences)
        length_signal = 0.0
        if len(text) >= 4:
            length_signal = 1.0
        elif len(text) >= 2:
            length_signal = 0.6
        elif text:
            length_signal = 0.3

        frequency_signal = min(1.0, mention_count / 4.0)
        duplicate_penalty = 0.0
        if freq.get(norm, 0) > 1:
            duplicate_penalty = min(0.35, (freq[norm] - 1) * 0.1)

        noisy_penalty = 0.0
        if text and sum(1 for c in text if not c.isalnum() and c not in {" ", "-", "_"}) > max(1, len(text) // 3):
            noisy_penalty = 0.25

        label_signal = 0.65 if label == "ENTITY" else 0.85
        confidence = _clamp01((0.35 * frequency_signal) + (0.35 * length_signal) + (0.3 * label_signal) - duplicate_penalty - noisy_penalty)

        if confidence < 0.5:
            low_confidence += 1
        scored.append(
            {
                **ent,
                "eda_confidence": round(confidence, 4),
                "eda_signals": {
                    "frequency_signal": round(frequency_signal, 4),
                    "length_signal": round(length_signal, 4),
                    "label_signal": round(label_signal, 4),
                    "duplicate_penalty": round(duplicate_penalty, 4),
                    "noisy_penalty": round(noisy_penalty, 4),
                },
            }
        )

    values = [_safe_float(e.get("eda_confidence"), 0.0) for e in scored]
    mean_conf = sum(values) / max(1, len(values))
    return {
        "entities": scored,
        "summary": {
            "entity_count": len(scored),
            "low_confidence_count": low_confidence,
            "mean_confidence": round(mean_conf, 4),
            "min_confidence": round(min(values), 4) if values else 0.0,
            "max_confidence": round(max(values), 4) if values else 0.0,
        },
    }


def score_relationships(
    relationships: List[Dict[str, Any]],
    entity_confidence_by_label: Dict[str, float],
) -> Dict[str, Any]:
    seen = defaultdict(int)
    scored: List[Dict[str, Any]] = []
    low_confidence = 0

    for rel in relationships:
        source = str(rel.get("source") or "").strip()
        target = str(rel.get("target") or "").strip()
        relation = str(rel.get("relation") or "related_to").strip()
        context = str(rel.get("context") or "").strip()
        key = (source.lower(), relation.lower(), target.lower())
        seen[key] += 1

        prior = RELATION_PRIOR.get(relation, 0.55)
        context_signal = min(1.0, len(context) / 90.0)
        source_conf = _safe_float(entity_confidence_by_label.get(source.lower(), 0.55), 0.55)
        target_conf = _safe_float(entity_confidence_by_label.get(target.lower(), 0.55), 0.55)
        duplicate_penalty = min(0.3, (seen[key] - 1) * 0.12) if seen[key] > 1 else 0.0
        weak_pair_penalty = 0.2 if source.lower() == target.lower() else 0.0

        confidence = _clamp01(
            (0.32 * prior)
            + (0.28 * context_signal)
            + (0.2 * source_conf)
            + (0.2 * target_conf)
            - duplicate_penalty
            - weak_pair_penalty
        )

        if confidence < 0.5:
            low_confidence += 1
        scored.append(
            {
                **rel,
                "eda_confidence": round(confidence, 4),
                "eda_signals": {
                    "prior": round(prior, 4),
                    "context_signal": round(context_signal, 4),
                    "source_confidence": round(source_conf, 4),
                    "target_confidence": round(target_conf, 4),
                    "duplicate_penalty": round(duplicate_penalty, 4),
                    "weak_pair_penalty": round(weak_pair_penalty, 4),
                },
            }
        )

    values = [_safe_float(r.get("eda_confidence"), 0.0) for r in scored]
    mean_conf = sum(values) / max(1, len(values))
    return {
        "relationships": scored,
        "summary": {
            "relationship_count": len(scored),
            "low_confidence_count": low_confidence,
            "mean_confidence": round(mean_conf, 4),
            "min_confidence": round(min(values), 4) if values else 0.0,
            "max_confidence": round(max(values), 4) if values else 0.0,
        },
    }


def quality_scorecard(
    entity_mean: float,
    relation_mean: float,
    graph_density: float,
    consistency_score: float,
    completeness_score: float,
    extraction_reliability: float,
) -> Dict[str, float]:
    confidence_score = _clamp01((entity_mean + relation_mean) / 2.0)
    trust_score = _clamp01((0.35 * confidence_score) + (0.2 * consistency_score) + (0.2 * completeness_score) + (0.15 * extraction_reliability) + (0.1 * min(1.0, graph_density * 3.0)))
    retrieval_readiness = _clamp01((0.4 * confidence_score) + (0.25 * consistency_score) + (0.2 * completeness_score) + (0.15 * min(1.0, graph_density * 2.0)))
    overall = _clamp01((0.45 * trust_score) + (0.3 * consistency_score) + (0.25 * completeness_score))

    return {
        "overall_kg_quality_score": round(overall, 4),
        "completeness_score": round(_clamp01(completeness_score), 4),
        "consistency_score": round(_clamp01(consistency_score), 4),
        "confidence_score": round(confidence_score, 4),
        "graph_trust_score": round(trust_score, 4),
        "retrieval_readiness_score": round(retrieval_readiness, 4),
        "semantic_coherence_score": round(_clamp01((consistency_score + confidence_score) / 2.0), 4),
        "canonical_resolution_score": round(_clamp01((confidence_score * 0.6) + (consistency_score * 0.4)), 4),
        "extraction_reliability_score": round(_clamp01(extraction_reliability), 4),
    }


def confidence_histogram(values: List[float], bins: int = 10) -> List[Dict[str, Any]]:
    if bins <= 0:
        bins = 10
    clamped = [_clamp01(v) for v in values]
    bucket = [0 for _ in range(bins)]
    for v in clamped:
        idx = min(bins - 1, int(math.floor(v * bins)))
        bucket[idx] += 1

    out: List[Dict[str, Any]] = []
    for i, count in enumerate(bucket):
        start = i / bins
        end = (i + 1) / bins
        out.append({"bin_start": round(start, 2), "bin_end": round(end, 2), "count": count})
    return out
