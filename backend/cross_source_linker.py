import json
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

# ML metrics contract import
from metrics import RunMetrics
import time
import json

from graph_builder import GraphBuilder

PROCESSED_DIR = "data/processed"
REVIEWS_PATH = f"{PROCESSED_DIR}/cross_link_reviews.json"

# Conservative defaults to keep precision high.
LEXICAL_GATE_THRESHOLD = 0.55
EMBEDDING_GATE_THRESHOLD = 0.68
ACCEPT_THRESHOLD = 0.84
REVIEW_THRESHOLD = 0.72


def _normalize(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _tokenize(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9_]+", (text or "").lower()))


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _status_files() -> List[str]:
    if not os.path.exists(PROCESSED_DIR):
        return []
    return [
        os.path.join(PROCESSED_DIR, name)
        for name in os.listdir(PROCESSED_DIR)
        if name.endswith("_status.json")
    ]


def _source_type_index() -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for status_path in _status_files():
        try:
            with open(status_path, encoding="utf-8") as f:
                status = json.load(f)
            file_id = str(status.get("file_id") or "")
            ext = str(status.get("ext") or "").upper()
            if not file_id:
                continue
            idx[file_id] = "db" if ext == "DB" else "corpus"
        except Exception:
            continue
    return idx


def _read_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return default


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    # ---- ML Metrics Artifact (observe-only, stub) ----
    try:
        metrics_artifact = RunMetrics(
            run_id=f"cross_link_{int(time.time()*1000)}",
            stage="cross_source_link_decision",
            timestamp=str(time.time()),
            classification=None,
            retrieval=None,
            calibration=None,
            hallucination=None,
            extra={
                "json_path": path,
                "payload_keys": list(payload.keys()),
            },
            version="1.0",
        )
        with open(f"data/processed/crosslink_metrics_{int(time.time()*1000)}.json", "w") as f:
            f.write(metrics_artifact.json(indent=2))
    except Exception as e:
        pass


def _node_semantic_labels(node: Dict[str, Any], semantic_hints: Optional[Dict[str, List[str]]]) -> Set[str]:
    labels: Set[str] = set()
    cid = str(node.get("canonical_id") or "")
    if semantic_hints and cid in semantic_hints:
        labels.update(str(v).strip().lower() for v in semantic_hints[cid] if str(v).strip())

    entity_type = str(node.get("entity_type") or "").strip().lower()
    if entity_type:
        labels.add(entity_type)

    norm_label = _normalize(str(node.get("label") or ""))
    if any(k in norm_label for k in ("id", "key", "identifier")):
        labels.add("identifier")
    if any(k in norm_label for k in ("date", "time", "timestamp")):
        labels.add("time")
    if any(k in norm_label for k in ("price", "amount", "cost", "revenue", "total")):
        labels.add("measure")
    if any(k in norm_label for k in ("name", "title", "description", "category", "type", "status")):
        labels.add("descriptor")

    return labels


def _semantic_compatibility(
    source_node: Dict[str, Any],
    target_node: Dict[str, Any],
    source_semantic_hints: Optional[Dict[str, List[str]]] = None,
    target_semantic_hints: Optional[Dict[str, List[str]]] = None,
) -> Tuple[float, Dict[str, Any]]:
    left = _node_semantic_labels(source_node, source_semantic_hints)
    right = _node_semantic_labels(target_node, target_semantic_hints)
    if not left or not right:
        return 0.6, {"left": sorted(left), "right": sorted(right), "reason": "missing_semantics"}

    overlap = left & right
    if overlap:
        return 1.0, {"left": sorted(left), "right": sorted(right), "overlap": sorted(overlap), "reason": "semantic_overlap"}

    if "unknown" in left or "unknown" in right:
        return 0.65, {"left": sorted(left), "right": sorted(right), "reason": "unknown_semantics"}

    return 0.25, {"left": sorted(left), "right": sorted(right), "reason": "semantic_mismatch"}


def _candidate_text(node: Dict[str, Any]) -> str:
    label = str(node.get("label") or "")
    aliases = [str(a) for a in node.get("aliases", []) if str(a).strip()]
    return " ".join([label] + aliases)


def _lexical_score(source_node: Dict[str, Any], target_node: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    source_norm = _normalize(str(source_node.get("label") or ""))
    target_norm = _normalize(str(target_node.get("label") or ""))
    exact = 1.0 if source_norm and source_norm == target_norm else 0.0

    source_tokens = _tokenize(_candidate_text(source_node))
    target_tokens = _tokenize(_candidate_text(target_node))
    jaccard = _jaccard(source_tokens, target_tokens)
    containment = 0.0
    if source_norm and target_norm and (source_norm in target_norm or target_norm in source_norm):
        containment = 1.0

    score = max(exact, containment, jaccard)
    return score, {
        "exact_norm": round(exact, 4),
        "containment": round(containment, 4),
        "token_jaccard": round(jaccard, 4),
    }


def _embedding_score(embed_fn: Callable[[str], np.ndarray], source_node: Dict[str, Any], target_node: Dict[str, Any]) -> float:
    source_text = _candidate_text(source_node)
    target_text = _candidate_text(target_node)
    try:
        source_vec = np.asarray(embed_fn(source_text), dtype=np.float32)
        target_vec = np.asarray(embed_fn(target_text), dtype=np.float32)
        return _clamp01((_cosine(source_vec, target_vec) + 1.0) / 2.0)
    except Exception:
        return 0.0


def _cross_link_artifact_path(source_id: str) -> str:
    return f"{PROCESSED_DIR}/{source_id}_cross_links.json"


def _eda_evidence_boost(
    source_node: Dict[str, Any],
    relationship_evidence: Optional[Dict[str, Any]],
) -> float:
    if not relationship_evidence:
        return 0.0
    label = _normalize(str(source_node.get("label") or ""))
    if not label:
        return 0.0

    # Match by source-side table/column mention in evidence keys: table.col->table.col
    matched: List[float] = []
    for key, payload in relationship_evidence.items():
        if label not in _normalize(str(key)):
            continue
        overlap = float((payload or {}).get("overlap_pct", 0.0) or 0.0)
        matched.append(_clamp01(overlap))

    if not matched:
        return 0.0
    # Bounded confidence boost, capped to avoid overriding semantic/embedding gates.
    return min(0.08, (sum(matched) / len(matched)) * 0.08)


def _load_reviews() -> Dict[str, Any]:
    return _read_json(REVIEWS_PATH, {"reviews": [], "updated_at": None})


def _save_reviews(payload: Dict[str, Any]) -> None:
    payload["updated_at"] = time.time()
    _write_json(REVIEWS_PATH, payload)


def _edge_key(source_id: str, relation: str, target_id: str) -> str:
    return f"{source_id}|{relation}|{target_id}"


def _existing_edge_keys(canonical_graph: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    for edge in canonical_graph.get("edges", []):
        src = edge.get("source_canonical_id") or edge.get("source")
        tgt = edge.get("target_canonical_id") or edge.get("target")
        relation = edge.get("relation", "related_to")
        if not src or not tgt:
            continue
        keys.add(_edge_key(str(src), str(relation), str(tgt)))
    return keys


def build_db_semantic_hints(profile: Optional[Dict[str, Any]], mapped_nodes: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    hints: Dict[str, List[str]] = {}
    if not profile:
        return hints

    table_label_map: Dict[str, List[str]] = {}
    column_label_map: Dict[str, List[str]] = {}

    for table in profile.get("tables", []):
        tname = str(table.get("table_name") or "").strip().lower()
        if tname:
            table_label_map[tname] = [
                str(table.get("table_semantic_label") or "unknown").strip().lower(),
                "table",
            ]
        for col in table.get("columns", []):
            cname = str(col.get("column") or col.get("name") or "").strip().lower()
            if not cname:
                continue
            key = f"{tname}.{cname}" if tname else cname
            column_label_map[key] = [
                str(col.get("semantic_label") or "unknown").strip().lower(),
                "column",
            ]

    for node in mapped_nodes:
        cid = str(node.get("canonical_id") or "")
        label = str(node.get("label") or "").strip().lower()
        if not cid or not label:
            continue

        if label in table_label_map:
            hints[cid] = table_label_map[label]
            continue

        if label in column_label_map:
            hints[cid] = column_label_map[label]
            continue

        if "." in label and label in column_label_map:
            hints[cid] = column_label_map[label]

    return hints


def link_cross_source(
    source_id: str,
    source_type: str,
    source_nodes: List[Dict[str, Any]],
    embed_fn: Callable[[str], np.ndarray],
    source_semantic_hints: Optional[Dict[str, List[str]]] = None,
    relationship_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source_type_norm = (source_type or "").strip().lower()
    if source_type_norm not in {"db", "corpus"}:
        raise ValueError("source_type must be 'db' or 'corpus'")

    graph_builder = GraphBuilder()
    canonical_graph = graph_builder.get_canonical_graph()
    type_idx = _source_type_index()

    opposite_type = "corpus" if source_type_norm == "db" else "db"
    all_nodes = canonical_graph.get("nodes", [])
    target_nodes = []
    for node in all_nodes:
        source_files = [str(fid) for fid in node.get("source_files", []) if str(fid)]
        node_types = {type_idx.get(fid, "corpus") for fid in source_files}
        if opposite_type in node_types:
            target_nodes.append(node)

    existing_edges = _existing_edge_keys(canonical_graph)

    accepted: List[Dict[str, Any]] = []
    review_candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for source_node in source_nodes:
        source_cid = str(source_node.get("canonical_id") or "")
        if not source_cid:
            continue

        best: Optional[Dict[str, Any]] = None
        for target_node in target_nodes:
            target_cid = str(target_node.get("canonical_id") or "")
            if not target_cid or target_cid == source_cid:
                continue

            lexical, lexical_breakdown = _lexical_score(source_node, target_node)
            if lexical < LEXICAL_GATE_THRESHOLD:
                continue

            semantic_score, semantic_breakdown = _semantic_compatibility(
                source_node,
                target_node,
                source_semantic_hints=source_semantic_hints,
                target_semantic_hints=None,
            )
            if semantic_score < 0.5:
                rejected.append(
                    {
                        "source_canonical_id": source_cid,
                        "target_canonical_id": target_cid,
                        "reason": "semantic_gate_failed",
                        "lexical_score": round(lexical, 4),
                        "semantic_score": round(semantic_score, 4),
                    }
                )
                continue

            embedding = _embedding_score(embed_fn, source_node, target_node)
            if embedding < EMBEDDING_GATE_THRESHOLD:
                rejected.append(
                    {
                        "source_canonical_id": source_cid,
                        "target_canonical_id": target_cid,
                        "reason": "embedding_gate_failed",
                        "lexical_score": round(lexical, 4),
                        "semantic_score": round(semantic_score, 4),
                        "embedding_score": round(embedding, 4),
                    }
                )
                continue

            base_score = _clamp01((0.45 * lexical) + (0.20 * semantic_score) + (0.35 * embedding))
            eda_boost = _eda_evidence_boost(source_node, relationship_evidence)
            final_score = _clamp01(base_score + eda_boost)
            relation = "cross_source_related"
            edge_key = _edge_key(source_cid, relation, target_cid)

            candidate = {
                "source_canonical_id": source_cid,
                "target_canonical_id": target_cid,
                "relation": relation,
                "confidence": round(final_score, 4),
                "edge_type": "CROSS_SOURCE",
                "provenance": [
                    {
                        "file_id": source_id,
                        "chunk_idx": -1,
                        "context": "Cross-source linker (lexical+semantic+embedding)",
                        "extractor": "cross_source_linker",
                    }
                ],
                "score_breakdown": {
                    "lexical": round(lexical, 4),
                    "semantic": round(semantic_score, 4),
                    "embedding": round(embedding, 4),
                    "eda_boost": round(eda_boost, 4),
                    "base_score": round(base_score, 4),
                    "lexical_details": lexical_breakdown,
                    "semantic_details": semantic_breakdown,
                },
                "state": "accepted" if final_score >= ACCEPT_THRESHOLD else "review" if final_score >= REVIEW_THRESHOLD else "rejected",
                "already_exists": edge_key in existing_edges,
            }

            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate

        if not best:
            rejected.append(
                {
                    "source_canonical_id": source_cid,
                    "reason": "no_candidate_passing_gates",
                }
            )
            continue

        if best.get("already_exists"):
            rejected.append(
                {
                    "source_canonical_id": source_cid,
                    "target_canonical_id": best.get("target_canonical_id"),
                    "reason": "edge_already_exists",
                    "score": best.get("confidence"),
                }
            )
            continue

        if best["state"] == "accepted":
            accepted.append(best)
        elif best["state"] == "review":
            review_candidates.append(best)
        else:
            rejected.append(
                {
                    "source_canonical_id": source_cid,
                    "target_canonical_id": best.get("target_canonical_id"),
                    "reason": "score_below_review_threshold",
                    "score": best.get("confidence"),
                }
            )

    artifact = {
        "source_id": source_id,
        "source_type": source_type_norm,
        "generated_at": time.time(),
        "policy": {
            "lexical_gate_threshold": LEXICAL_GATE_THRESHOLD,
            "embedding_gate_threshold": EMBEDDING_GATE_THRESHOLD,
            "accept_threshold": ACCEPT_THRESHOLD,
            "review_threshold": REVIEW_THRESHOLD,
            "eda_boost_max": 0.08,
        },
        "accepted": accepted,
        "review": review_candidates,
        "rejected": rejected,
        "stats": {
            "source_node_count": len(source_nodes),
            "target_node_count": len(target_nodes),
            "accepted_count": len(accepted),
            "review_count": len(review_candidates),
            "rejected_count": len(rejected),
            "linked_source_coverage_pct": round((len(accepted) / max(1, len(source_nodes))) * 100, 2),
        },
    }
    _write_json(_cross_link_artifact_path(source_id), artifact)

    reviews_payload = _load_reviews()
    reviews = reviews_payload.get("reviews", [])
    for item in review_candidates:
        review_id = f"clrvw_{uuid.uuid4().hex[:12]}"
        reviews.append(
            {
                "review_id": review_id,
                "source_id": source_id,
                "status": "pending",
                "created_at": time.time(),
                "decision": None,
                "decided_by": None,
                "edge": item,
            }
        )
        item["review_id"] = review_id

    reviews_payload["reviews"] = reviews
    _save_reviews(reviews_payload)

    return {
        "source_id": source_id,
        "accepted_edges": [
            {
                "source_canonical_id": e["source_canonical_id"],
                "target_canonical_id": e["target_canonical_id"],
                "relation": e["relation"],
                "confidence": e["confidence"],
                "edge_type": e["edge_type"],
                "provenance": e["provenance"],
            }
            for e in accepted
        ],
        "report": {
            "accepted_count": len(accepted),
            "review_count": len(review_candidates),
            "rejected_count": len(rejected),
            "linked_source_coverage_pct": artifact["stats"]["linked_source_coverage_pct"],
        },
    }


def get_cross_links(source_id: str) -> Dict[str, Any]:
    return _read_json(_cross_link_artifact_path(source_id), {})


def list_cross_link_reviews(status: Optional[str] = "pending", limit: int = 100) -> Dict[str, Any]:
    payload = _load_reviews()
    reviews = payload.get("reviews", [])
    if status:
        status_norm = status.strip().lower()
        reviews = [r for r in reviews if str(r.get("status", "")).lower() == status_norm]
    reviews = sorted(reviews, key=lambda r: r.get("created_at", 0), reverse=True)
    reviews = reviews[: max(1, min(limit, 500))]
    return {
        "reviews": reviews,
        "count": len(reviews),
        "updated_at": payload.get("updated_at"),
    }


def apply_cross_link_review(review_id: str, decision: str, decided_by: Optional[str] = None) -> Dict[str, Any]:
    payload = _load_reviews()
    reviews = payload.get("reviews", [])
    review = next((r for r in reviews if r.get("review_id") == review_id), None)
    if not review:
        return {"ok": False, "error": "review_not_found"}

    if review.get("status") != "pending":
        return {"ok": False, "error": "review_already_resolved", "review": review}

    decision_norm = (decision or "").strip().lower()
    if decision_norm not in {"approve", "reject"}:
        return {"ok": False, "error": "invalid_decision"}

    review["status"] = "approved" if decision_norm == "approve" else "rejected"
    review["decision"] = decision_norm
    review["decided_by"] = decided_by or "ui"
    review["decided_at"] = time.time()

    if decision_norm == "approve":
        edge = (review.get("edge") or {}).copy()
        edge.pop("score_breakdown", None)
        edge.pop("state", None)
        edge.pop("already_exists", None)
        edge.pop("review_id", None)
        GraphBuilder().upsert_canonical_graph(
            file_id=str(review.get("source_id") or "review"),
            resolved_nodes=[],
            resolved_edges=[edge],
        )

    _save_reviews(payload)
    return {"ok": True, "review": review}


def cross_link_metrics() -> Dict[str, Any]:
    files = []
    if os.path.exists(PROCESSED_DIR):
        files = [
            os.path.join(PROCESSED_DIR, name)
            for name in os.listdir(PROCESSED_DIR)
            if name.endswith("_cross_links.json")
        ]

    accepted = 0
    pending = 0
    rejected = 0
    source_count = 0

    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            source_count += 1
            accepted += len(payload.get("accepted", []))
            pending += len(payload.get("review", []))
            rejected += len(payload.get("rejected", []))
        except Exception:
            continue

    total = accepted + pending + rejected

    review_payload = _load_reviews()
    all_reviews = review_payload.get("reviews", [])
    pending_reviews = len([r for r in all_reviews if r.get("status") == "pending"])
    approved_reviews = len([r for r in all_reviews if r.get("status") == "approved"])
    rejected_reviews = len([r for r in all_reviews if r.get("status") == "rejected"])

    return {
        "source_artifact_count": source_count,
        "accepted_links": accepted,
        "pending_links": pending,
        "rejected_links": rejected,
        "accepted_ratio_pct": round((accepted / max(1, total)) * 100, 2),
        "pending_ratio_pct": round((pending / max(1, total)) * 100, 2),
        "rejected_ratio_pct": round((rejected / max(1, total)) * 100, 2),
        "review_backlog": {
            "pending": pending_reviews,
            "approved": approved_reviews,
            "rejected": rejected_reviews,
        },
        "updated_at": time.time(),
    }
