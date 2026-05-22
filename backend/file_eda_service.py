import json
import os
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from confidence_scoring import confidence_histogram, quality_scorecard, score_entities, score_relationships
from cross_document_linking import cross_file_semantic_linking
from folder_aggregation_analytics import build_folder_analytics
from graph_validation_utils import build_light_graph, graph_metrics, validate_relationship_quality
from pdf_eda_utils import analyze_pdf_quality
from semantic_quality_analyzer import analyze_semantic_consistency


PROCESSED_DIR = "data/processed"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _entity_quality_stats(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    resolution_report: Dict[str, Any],
    semantic_report: Dict[str, Any],
    graph_health: Dict[str, Any],
) -> Dict[str, Any]:
    by_text = Counter(str(e.get("text") or "").strip().lower() for e in entities if str(e.get("text") or "").strip())
    duplicates = [{"entity": key, "count": count} for key, count in by_text.items() if count > 1]

    relation_nodes = set()
    for rel in relationships:
        src = str(rel.get("source") or "").strip().lower()
        tgt = str(rel.get("target") or "").strip().lower()
        if src:
            relation_nodes.add(src)
        if tgt:
            relation_nodes.add(tgt)

    orphans = []
    type_map: Dict[str, set] = defaultdict(set)
    noisy_entities = []
    low_conf = []
    mention_distribution = []

    for ent in entities:
        text = str(ent.get("text") or "").strip()
        if not text:
            continue

        norm = text.lower()
        ent_type = str(ent.get("type") or ent.get("label") or "entity").lower()
        type_map[norm].add(ent_type)

        mention_count = 1 + len(ent.get("chunk_occurrences", []) or [])
        mention_distribution.append(mention_count)

        conf = _safe_float(ent.get("eda_confidence"), 0.0)
        if conf < 0.5:
            low_conf.append({"entity": text, "confidence": round(conf, 4)})

        noisy_penalty = _safe_float((ent.get("eda_signals") or {}).get("noisy_penalty"), 0.0)
        if noisy_penalty > 0:
            noisy_entities.append({"entity": text, "noisy_penalty": round(noisy_penalty, 4)})

        if norm not in relation_nodes:
            orphans.append({"entity": text, "reason": "no_relationships_detected"})

    conflicting_types = [
        {"entity": entity, "types": sorted(list(types))}
        for entity, types in type_map.items()
        if len(types) > 1
    ]
    conflicting_types.extend((semantic_report.get("invalid_entity_type_mappings") or [])[:100])

    ambiguous = []
    for ent in entities:
        text = str(ent.get("text") or "").strip()
        if not text:
            continue
        etype = str(ent.get("type") or ent.get("label") or "entity").lower()
        if etype in {"entity", "unknown"} or len(text) <= 2:
            ambiguous.append({"entity": text, "type": etype, "reason": "weak_entity_specificity"})

    mention_distribution.sort()
    stats = {
        "min": mention_distribution[0] if mention_distribution else 0,
        "median": mention_distribution[len(mention_distribution) // 2] if mention_distribution else 0,
        "max": mention_distribution[-1] if mention_distribution else 0,
    }

    return {
        "duplicate_entities": duplicates[:300],
        "unresolved_canonical_entities": int(resolution_report.get("pending_review_count", 0) or 0),
        "ambiguous_entities": ambiguous[:300],
        "low_confidence_entities": low_conf[:300],
        "noisy_entities": noisy_entities[:300],
        "entity_frequency_distribution": {
            "summary": stats,
            "top_entities": [{"entity": e, "count": c} for e, c in by_text.most_common(50)],
        },
        "orphan_entities": orphans[:300],
        "conflicting_entity_types_across_files": conflicting_types[:300],
        "isolated_node_ids": graph_health.get("isolated_node_ids", []),
    }


def _graph_validation_report(
    relationship_quality: Dict[str, Any],
    entity_quality: Dict[str, Any],
    semantic_report: Dict[str, Any],
    graph_health: Dict[str, Any],
) -> Dict[str, Any]:
    weak_edges = relationship_quality.get("weak_edges", [])
    duplicate_relationships = relationship_quality.get("duplicate_relationships", [])
    semantic_inconsistencies = (
        (semantic_report.get("semantic_contradictions") or [])
        + (semantic_report.get("temporal_inconsistencies") or [])
        + (semantic_report.get("numeric_anomalies") or [])
        + (semantic_report.get("relationship_direction_issues") or [])
    )

    return {
        "weak_edges": weak_edges,
        "duplicate_entities": entity_quality.get("duplicate_entities", []),
        "ontology_violations": semantic_report.get("ontology_violations", []),
        "disconnected_nodes": graph_health.get("isolated_node_ids", []),
        "semantic_inconsistencies": semantic_inconsistencies[:500],
        "invalid_edge_patterns": relationship_quality.get("invalid_edge_patterns", []),
        "duplicate_relationships": duplicate_relationships,
        "missing_inverse_relationships": relationship_quality.get("missing_inverse_relationships", []),
        "cross_document_inconsistencies": relationship_quality.get("cross_document_inconsistencies", []),
    }


def run_file_eda(
    file_id: str,
    ext: str,
    corpus: Dict[str, Any],
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    canonical_nodes: List[Dict[str, Any]],
    canonical_edges: List[Dict[str, Any]],
    resolved_nodes: List[Dict[str, Any]],
    resolution_report: Dict[str, Any],
    chunk_validation_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_at = time.time()

    entity_scores = score_entities(entities)
    scored_entities = entity_scores.get("entities", [])
    entity_conf_map = {
        str(e.get("text") or "").strip().lower(): _safe_float(e.get("eda_confidence"), 0.0)
        for e in scored_entities
        if str(e.get("text") or "").strip()
    }

    relation_scores = score_relationships(relationships, entity_conf_map)
    scored_relationships = relation_scores.get("relationships", [])

    graph = build_light_graph(scored_entities, scored_relationships)
    graph_health = graph_metrics(graph)
    relationship_quality = validate_relationship_quality(graph, scored_relationships)
    semantic_report = analyze_semantic_consistency(scored_entities, scored_relationships)
    cross_file = cross_file_semantic_linking(file_id, resolved_nodes)
    folder_analytics = build_folder_analytics(file_id, scored_entities, cross_file)
    pdf_eda = analyze_pdf_quality(corpus, scored_entities)

    entity_quality = _entity_quality_stats(
        entities=scored_entities,
        relationships=scored_relationships,
        resolution_report=resolution_report,
        semantic_report=semantic_report,
        graph_health=graph_health,
    )

    entity_mean = _safe_float((entity_scores.get("summary") or {}).get("mean_confidence"), 0.0)
    relation_mean = _safe_float((relation_scores.get("summary") or {}).get("mean_confidence"), 0.0)
    consistency_score = _safe_float(semantic_report.get("consistency_score"), 0.0)

    orphan_count = len(entity_quality.get("orphan_entities", []))
    isolated_count = len(graph_health.get("isolated_node_ids", []))
    node_count = max(1, int(graph_health.get("node_count", 0) or 0))
    completeness_score = _clamp01(1.0 - ((0.6 * orphan_count + 0.4 * isolated_count) / float(node_count)))

    coverage_pct = _safe_float((chunk_validation_report or {}).get("coverage_pct"), 0.0) / 100.0
    overlap_pct = _safe_float((chunk_validation_report or {}).get("overlap_correctness_pct"), 0.0) / 100.0
    pdf_page_conf = [
        _safe_float(p.get("confidence"), 0.0) for p in (pdf_eda.get("page_confidence") or [])
    ]
    pdf_signal = (sum(pdf_page_conf) / len(pdf_page_conf)) if pdf_page_conf else 1.0
    extraction_reliability = _clamp01((0.45 * coverage_pct) + (0.35 * overlap_pct) + (0.2 * pdf_signal))

    scorecard = quality_scorecard(
        entity_mean=entity_mean,
        relation_mean=relation_mean,
        graph_density=_safe_float(graph_health.get("graph_density"), 0.0),
        consistency_score=consistency_score,
        completeness_score=completeness_score,
        extraction_reliability=extraction_reliability,
    )

    graph_validation = _graph_validation_report(
        relationship_quality=relationship_quality,
        entity_quality=entity_quality,
        semantic_report=semantic_report,
        graph_health=graph_health,
    )

    relation_types = Counter(str(r.get("relation") or "related_to") for r in scored_relationships)
    entity_types = Counter(str(e.get("type") or e.get("label") or "entity") for e in scored_entities)

    entity_conf_values = [_safe_float(e.get("eda_confidence"), 0.0) for e in scored_entities]
    relation_conf_values = [_safe_float(r.get("eda_confidence"), 0.0) for r in scored_relationships]

    visuals = {
        "graph_density": _safe_float(graph_health.get("graph_density"), 0.0),
        "entity_distribution": [{"type": k, "count": v} for k, v in entity_types.most_common()],
        "confidence_histograms": {
            "entities": confidence_histogram(entity_conf_values, bins=10),
            "relationships": confidence_histogram(relation_conf_values, bins=10),
        },
        "semantic_clusters": folder_analytics.get("document_clusters", []),
        "node_centrality": graph_health.get("central_entities", []),
        "relation_distributions": [{"relation": k, "count": v} for k, v in relation_types.most_common()],
    }

    low_conf_entities = [e for e in scored_entities if _safe_float(e.get("eda_confidence"), 0.0) < 0.45]
    low_conf_rels = [r for r in scored_relationships if _safe_float(r.get("eda_confidence"), 0.0) < 0.45]
    retry_hooks = {
        "retry_mechanisms": {
            "enabled": True,
            "recommended": bool(low_conf_entities or low_conf_rels),
            "reason": "low_confidence_signal_detected" if (low_conf_entities or low_conf_rels) else "not_required",
        },
        "low_confidence_reprocessing": {
            "entity_threshold": 0.45,
            "relationship_threshold": 0.45,
            "low_confidence_entities": len(low_conf_entities),
            "low_confidence_relationships": len(low_conf_rels),
        },
        "graph_correction_workflow": {
            "weak_edge_count": len(graph_validation.get("weak_edges", [])),
            "suggested_actions": [
                "review_weak_edges",
                "suppress_noisy_relations",
                "split_ambiguous_entities",
            ],
        },
        "confidence_audit_pipeline": {
            "audit_required": scorecard.get("confidence_score", 1.0) < 0.6,
            "entity_mean_confidence": round(entity_mean, 4),
            "relationship_mean_confidence": round(relation_mean, 4),
        },
    }

    summary = {
        "file_id": file_id,
        "generated_at": time.time(),
        "runtime_ms": int((time.time() - started_at) * 1000),
        "source": {
            "ext": str(ext or "").lower().lstrip("."),
            "adapter": corpus.get("adapter"),
            "source_type": corpus.get("source_type"),
        },
        "entity_statistics": {
            **(entity_scores.get("summary") or {}),
            **entity_quality,
            "canonical_entities_count": len(canonical_nodes),
            "resolved_entities_count": len(resolved_nodes),
        },
        "relationship_statistics": {
            **(relation_scores.get("summary") or {}),
            **relationship_quality,
            "canonical_relationships_count": len(canonical_edges),
        },
        "graph_metrics": graph_health,
        "semantic_quality_metrics": semantic_report,
        "confidence_scores": {
            "entity_confidence_score": round(entity_mean, 4),
            "relationship_confidence_score": round(relation_mean, 4),
            "graph_trust_score": scorecard.get("graph_trust_score", 0.0),
            "semantic_coherence_score": scorecard.get("semantic_coherence_score", 0.0),
            "canonical_resolution_score": scorecard.get("canonical_resolution_score", 0.0),
            "knowledge_graph_completeness_score": scorecard.get("completeness_score", 0.0),
            "extraction_reliability_score": scorecard.get("extraction_reliability_score", 0.0),
        },
        "cross_file_analytics": cross_file,
        "pdf_specific_eda": pdf_eda,
        "hooks": retry_hooks,
    }

    summary_path = os.path.join(PROCESSED_DIR, f"{file_id}_eda_summary.json")
    graph_validation_path = os.path.join(PROCESSED_DIR, f"{file_id}_graph_validation.json")
    folder_analytics_path = os.path.join(PROCESSED_DIR, f"{file_id}_folder_analytics.json")
    scorecard_path = os.path.join(PROCESSED_DIR, f"{file_id}_kg_scorecard.json")
    visuals_path = os.path.join(PROCESSED_DIR, f"{file_id}_eda_visuals.json")
    bundle_path = os.path.join(PROCESSED_DIR, f"{file_id}_eda_artifacts.json")

    _write_json(summary_path, summary)
    _write_json(graph_validation_path, graph_validation)
    _write_json(folder_analytics_path, folder_analytics)
    _write_json(scorecard_path, scorecard)
    _write_json(visuals_path, visuals)
    _write_json(
        bundle_path,
        {
            "file_id": file_id,
            "generated_at": time.time(),
            "summary_path": summary_path,
            "graph_validation_report_path": graph_validation_path,
            "folder_analytics_report_path": folder_analytics_path,
            "kg_quality_scorecard_path": scorecard_path,
            "visual_metrics_path": visuals_path,
            "hooks": retry_hooks,
        },
    )

    return {
        "summary": summary,
        "graph_validation": graph_validation,
        "folder_analytics": folder_analytics,
        "scorecard": scorecard,
        "visuals": visuals,
        "artifacts": {
            "summary_path": summary_path,
            "graph_validation_report_path": graph_validation_path,
            "folder_analytics_report_path": folder_analytics_path,
            "kg_quality_scorecard_path": scorecard_path,
            "visual_metrics_path": visuals_path,
            "bundle_path": bundle_path,
        },
        "optimized_entities": scored_entities,
        "optimized_relationships": scored_relationships,
        "reprocess_recommended": retry_hooks["retry_mechanisms"]["recommended"],
    }
