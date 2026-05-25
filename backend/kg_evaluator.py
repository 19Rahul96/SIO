"""KG Evaluation Engine.

Manages human-reviewed gold sets (entities + relationships) and evaluates
the generated knowledge graph against them, producing precision/recall/F1
plus false-relationship rate, evidence accuracy, and high-confidence edge accuracy.

Artifacts are persisted to:
  data/processed/{source_id}_kg_gold.json   — the editable gold set
  data/processed/{source_id}_kg_eval.json   — evaluation results

source_id can be a file_id (upload) or db_id (database connection).
"""

import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

PROCESSED_DIR = "data/processed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _gold_path(source_id: str) -> str:
    return os.path.join(PROCESSED_DIR, f"{source_id}_kg_gold.json")


def _eval_path(source_id: str) -> str:
    return os.path.join(PROCESSED_DIR, f"{source_id}_kg_eval.json")


def _read_json(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json(path: str, payload: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _norm(text: str) -> str:
    """Normalise entity/relation text for matching (lowercase, strip)."""
    return " ".join(str(text or "").lower().strip().split())


def _entity_key(e: Dict) -> str:
    """Canonical key for an entity — (normalised text, normalised type)."""
    return f"{_norm(e.get('text', ''))}|{_norm(e.get('type', '') or e.get('label', ''))}"


def _rel_key(r: Dict) -> str:
    """Canonical key for a relationship — (source, relation, target) normalised."""
    return f"{_norm(r.get('source', ''))}|{_norm(r.get('relation', ''))}|{_norm(r.get('target', ''))}"


# ---------------------------------------------------------------------------
# Gold set management
# ---------------------------------------------------------------------------

def get_gold_set(source_id: str) -> Dict:
    """Return the current gold set for a source, creating empty if absent."""
    path = _gold_path(source_id)
    existing = _read_json(path)
    if not existing:
        existing = {
            "source_id": source_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "gold_entities": [],
            "gold_relationships": [],
        }
    return existing


def upsert_gold_entities(source_id: str, entities: List[Dict]) -> Dict:
    """Add or replace gold entities.  Each entity must have 'text' and optionally 'type'."""
    gold = get_gold_set(source_id)
    existing_keys = {_entity_key(e): i for i, e in enumerate(gold["gold_entities"])}
    for ent in entities:
        key = _entity_key(ent)
        record = {
            "text": str(ent.get("text", "")).strip(),
            "type": str(ent.get("type") or ent.get("label") or "ENTITY"),
            "note": str(ent.get("note", "") or ""),
            "added_by": str(ent.get("added_by", "human")),
            "added_at": time.time(),
        }
        if key in existing_keys:
            gold["gold_entities"][existing_keys[key]] = record
        else:
            gold["gold_entities"].append(record)
            existing_keys[key] = len(gold["gold_entities"]) - 1
    gold["updated_at"] = time.time()
    _write_json(_gold_path(source_id), gold)
    return gold


def upsert_gold_relationships(source_id: str, relationships: List[Dict]) -> Dict:
    """Add or replace gold relationships.  Each must have 'source', 'relation', 'target'."""
    gold = get_gold_set(source_id)
    existing_keys = {_rel_key(r): i for i, r in enumerate(gold["gold_relationships"])}
    for rel in relationships:
        key = _rel_key(rel)
        record = {
            "source": str(rel.get("source", "")).strip(),
            "relation": str(rel.get("relation", "")).strip(),
            "target": str(rel.get("target", "")).strip(),
            "expected_confidence_min": _safe_float(rel.get("expected_confidence_min"), 0.0),
            "note": str(rel.get("note", "") or ""),
            "added_by": str(rel.get("added_by", "human")),
            "added_at": time.time(),
        }
        if key in existing_keys:
            gold["gold_relationships"][existing_keys[key]] = record
        else:
            gold["gold_relationships"].append(record)
            existing_keys[key] = len(gold["gold_relationships"]) - 1
    gold["updated_at"] = time.time()
    _write_json(_gold_path(source_id), gold)
    return gold


def delete_gold_entities(source_id: str, texts: List[str]) -> Dict:
    gold = get_gold_set(source_id)
    norm_set = {_norm(t) for t in texts}
    gold["gold_entities"] = [
        e for e in gold["gold_entities"]
        if _norm(e.get("text", "")) not in norm_set
    ]
    gold["updated_at"] = time.time()
    _write_json(_gold_path(source_id), gold)
    return gold


def delete_gold_relationships(source_id: str, keys: List[str]) -> Dict:
    """keys are 'source|relation|target' strings (pre-normalised or raw)."""
    gold = get_gold_set(source_id)
    norm_set = {_norm(k) for k in keys}
    gold["gold_relationships"] = [
        r for r in gold["gold_relationships"]
        if _rel_key(r) not in norm_set
    ]
    gold["updated_at"] = time.time()
    _write_json(_gold_path(source_id), gold)
    return gold


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def evaluate_kg(source_id: str, generated_graph: Dict, high_confidence_threshold: float = 0.7) -> Dict:
    """
    Compare generated_graph (nodes/edges) against the stored gold set.

    generated_graph schema:
        {
            "nodes": [{"id": ..., "label": ..., "entity_type": ...}, ...],
            "edges": [{"source": ..., "target": ..., "relation": ..., "confidence": ...,
                       "evidence": ...}, ...]
        }

    Returns the full evaluation dict and writes it to disk.
    """
    gold = get_gold_set(source_id)
    gold_entities = gold.get("gold_entities", [])
    gold_rels = gold.get("gold_relationships", [])

    gen_nodes = generated_graph.get("nodes", [])
    gen_edges = generated_graph.get("edges", [])

    # --- build node label lookup (id -> label) ---
    id_to_label: Dict[str, str] = {}
    for n in gen_nodes:
        nid = str(n.get("id", ""))
        label = str(n.get("label", "") or n.get("text", ""))
        if nid:
            id_to_label[nid] = label

    # --- Entity evaluation ---
    gold_entity_keys = {_entity_key(e) for e in gold_entities}
    gen_entity_keys: set = set()
    for n in gen_nodes:
        label = str(n.get("label") or n.get("text") or "").strip()
        etype = str(n.get("entity_type") or n.get("type") or "ENTITY")
        if label:
            gen_entity_keys.add(f"{_norm(label)}|{_norm(etype)}")
            # Also try type-agnostic match
            gen_entity_keys.add(f"{_norm(label)}|entity")

    entity_tp = len(gold_entity_keys & gen_entity_keys)
    entity_fp = len(gen_entity_keys - gold_entity_keys)
    entity_fn = len(gold_entity_keys - gen_entity_keys)
    entity_precision, entity_recall, entity_f1 = _prf(entity_tp, entity_fp, entity_fn)

    matched_entities = [
        e for e in gold_entities if _entity_key(e) in gen_entity_keys
    ]
    missed_entities = [
        e for e in gold_entities if _entity_key(e) not in gen_entity_keys
    ]

    # --- Relationship evaluation ---
    # Build generated rel keys, resolving node-id references to labels
    gen_rel_map: Dict[str, Dict] = {}
    for edge in gen_edges:
        src_raw = str(edge.get("source", ""))
        tgt_raw = str(edge.get("target", ""))
        src_label = id_to_label.get(src_raw, src_raw)
        tgt_label = id_to_label.get(tgt_raw, tgt_raw)
        rel = str(edge.get("relation", "related_to"))
        key = f"{_norm(src_label)}|{_norm(rel)}|{_norm(tgt_label)}"
        gen_rel_map[key] = edge

    gold_rel_keys = {_rel_key(r) for r in gold_rels}
    gen_rel_keys = set(gen_rel_map.keys())

    rel_tp = len(gold_rel_keys & gen_rel_keys)
    rel_fp = len(gen_rel_keys - gold_rel_keys)
    rel_fn = len(gold_rel_keys - gen_rel_keys)
    rel_precision, rel_recall, rel_f1 = _prf(rel_tp, rel_fp, rel_fn)

    matched_rels = [r for r in gold_rels if _rel_key(r) in gen_rel_keys]
    missed_rels = [r for r in gold_rels if _rel_key(r) not in gen_rel_keys]
    false_rels = [
        {"source": e.get("source"), "relation": e.get("relation"), "target": e.get("target"),
         "confidence": e.get("confidence", 0.0)}
        for key, e in gen_rel_map.items() if key not in gold_rel_keys
    ]

    # --- False relationship rate ---
    total_gen_rels = len(gen_edges)
    false_rel_rate = round(rel_fp / max(1, total_gen_rels), 4)

    # --- Evidence accuracy ---
    # For matched gold relationships, check if corresponding edge has evidence
    evidence_hits = 0
    evidence_total = 0
    for r in matched_rels:
        key = _rel_key(r)
        edge = gen_rel_map.get(key)
        if edge is not None:
            evidence_total += 1
            ev = edge.get("evidence") or edge.get("context") or edge.get("basis")
            if ev and str(ev).strip():
                evidence_hits += 1
    evidence_accuracy = round(evidence_hits / max(1, evidence_total), 4)

    # --- High-confidence edge accuracy ---
    # Fraction of high-confidence edges that are in the gold set
    high_conf_edges = [
        e for e in gen_edges
        if _safe_float(e.get("confidence", e.get("prior_confidence"))) >= high_confidence_threshold
    ]
    high_conf_total = len(high_conf_edges)
    high_conf_correct = 0
    for edge in high_conf_edges:
        src_raw = str(edge.get("source", ""))
        tgt_raw = str(edge.get("target", ""))
        src_label = id_to_label.get(src_raw, src_raw)
        tgt_label = id_to_label.get(tgt_raw, tgt_raw)
        rel = str(edge.get("relation", "related_to"))
        key = f"{_norm(src_label)}|{_norm(rel)}|{_norm(tgt_label)}"
        if key in gold_rel_keys:
            high_conf_correct += 1
    high_conf_edge_accuracy = round(high_conf_correct / max(1, high_conf_total), 4)

    # --- Confidence calibration for matched rels ---
    calibration_errors: List[float] = []
    for r in matched_rels:
        key = _rel_key(r)
        edge = gen_rel_map.get(key)
        if edge is not None:
            expected_min = _safe_float(r.get("expected_confidence_min"), 0.0)
            actual_conf = _safe_float(edge.get("confidence", edge.get("prior_confidence")))
            if expected_min > 0:
                calibration_errors.append(max(0.0, expected_min - actual_conf))
    avg_calibration_error = round(sum(calibration_errors) / max(1, len(calibration_errors)), 4) if calibration_errors else 0.0

    # --- Overall KG eval score ---
    eval_score = round(
        0.3 * entity_f1
        + 0.3 * rel_f1
        + 0.15 * (1.0 - false_rel_rate)
        + 0.15 * evidence_accuracy
        + 0.1 * high_conf_edge_accuracy,
        4
    )

    result: Dict = {
        "source_id": source_id,
        "evaluated_at": time.time(),
        "high_confidence_threshold": high_confidence_threshold,
        "gold_entity_count": len(gold_entities),
        "gold_relationship_count": len(gold_rels),
        "generated_entity_count": len(gen_nodes),
        "generated_relationship_count": total_gen_rels,
        "entity_metrics": {
            "true_positives": entity_tp,
            "false_positives": entity_fp,
            "false_negatives": entity_fn,
            "precision": entity_precision,
            "recall": entity_recall,
            "f1": entity_f1,
        },
        "relationship_metrics": {
            "true_positives": rel_tp,
            "false_positives": rel_fp,
            "false_negatives": rel_fn,
            "precision": rel_precision,
            "recall": rel_recall,
            "f1": rel_f1,
        },
        "false_relationship_rate": false_rel_rate,
        "evidence_accuracy": evidence_accuracy,
        "high_confidence_edge_accuracy": high_conf_edge_accuracy,
        "avg_confidence_calibration_error": avg_calibration_error,
        "overall_kg_eval_score": eval_score,
        "matched_entities": [e.get("text") for e in matched_entities],
        "missed_entities": [e.get("text") for e in missed_entities],
        "matched_relationships": [
            {"source": r.get("source"), "relation": r.get("relation"), "target": r.get("target")}
            for r in matched_rels
        ],
        "missed_relationships": [
            {"source": r.get("source"), "relation": r.get("relation"), "target": r.get("target")}
            for r in missed_rels
        ],
        "false_relationships_sample": false_rels[:50],
        "has_gold_set": len(gold_entities) > 0 or len(gold_rels) > 0,
    }

    _write_json(_eval_path(source_id), result)
    return result


def get_eval_result(source_id: str) -> Optional[Dict]:
    data = _read_json(_eval_path(source_id))
    return data if data else None


def list_eval_results() -> List[Dict]:
    """Return all eval results across all sources."""
    results = []
    if not os.path.exists(PROCESSED_DIR):
        return results
    for fname in os.listdir(PROCESSED_DIR):
        if fname.endswith("_kg_eval.json"):
            path = os.path.join(PROCESSED_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception:
                continue
    return sorted(results, key=lambda x: x.get("evaluated_at", 0), reverse=True)


def auto_generate_gold_from_graph(source_id: str, graph: Dict, min_confidence: float = 0.75) -> Dict:
    """
    Bootstrap a gold set from high-confidence generated graph elements.
    Only adds entries not already present.  Marks them as 'auto' source.
    """
    gold = get_gold_set(source_id)
    existing_entity_keys = {_entity_key(e) for e in gold["gold_entities"]}
    existing_rel_keys = {_rel_key(r) for r in gold["gold_relationships"]}

    id_to_label: Dict[str, str] = {}
    new_entities: List[Dict] = []
    for n in graph.get("nodes", []):
        label = str(n.get("label") or n.get("text") or "").strip()
        nid = str(n.get("id", ""))
        if nid and label:
            id_to_label[nid] = label
        if not label:
            continue
        etype = str(n.get("entity_type") or n.get("type") or "ENTITY")
        key = f"{_norm(label)}|{_norm(etype)}"
        if key not in existing_entity_keys:
            new_entities.append({"text": label, "type": etype, "added_by": "auto"})
            existing_entity_keys.add(key)

    new_rels: List[Dict] = []
    for edge in graph.get("edges", []):
        conf = _safe_float(edge.get("confidence", edge.get("prior_confidence")))
        if conf < min_confidence:
            continue
        src_raw = str(edge.get("source", ""))
        tgt_raw = str(edge.get("target", ""))
        src_label = id_to_label.get(src_raw, src_raw)
        tgt_label = id_to_label.get(tgt_raw, tgt_raw)
        rel = str(edge.get("relation", "related_to"))
        key = f"{_norm(src_label)}|{_norm(rel)}|{_norm(tgt_label)}"
        if key not in existing_rel_keys:
            new_rels.append({
                "source": src_label,
                "relation": rel,
                "target": tgt_label,
                "expected_confidence_min": round(conf * 0.8, 4),
                "added_by": "auto",
            })
            existing_rel_keys.add(key)

    if new_entities:
        upsert_gold_entities(source_id, new_entities)
    if new_rels:
        upsert_gold_relationships(source_id, new_rels)

    return get_gold_set(source_id)
