import json
import os
import re
import hashlib
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

REGISTRY_PATH = "data/canonical_registry.json"
MERGE_THRESHOLD = 0.72
REVIEW_THRESHOLD = 0.58


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _canonical_entity_id(entity_type: str, label: str) -> str:
    norm = (label or "").strip().lower()
    etype = (entity_type or "entity").strip().lower()
    return _stable_id("ce", f"{etype}:{norm}")


def _default_registry() -> Dict:
    return {
        "canonical_nodes": [],
        "merge_history": [],
        "pending_reviews": [],
        "updated_at": time.time(),
    }


def _load_registry() -> Dict:
    if not os.path.exists(REGISTRY_PATH):
        return _default_registry()
    try:
        with open(REGISTRY_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_registry()
        data.setdefault("canonical_nodes", [])
        data.setdefault("merge_history", [])
        data.setdefault("pending_reviews", [])
        data.setdefault("updated_at", time.time())
        return data
    except Exception:
        return _default_registry()


def _save_registry(registry: Dict):
    registry["updated_at"] = time.time()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f)


def _normalize_label(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9_]+", (text or "").lower()))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _type_compatible(left_type: str, right_type: str) -> bool:
    lt = (left_type or "entity").lower()
    rt = (right_type or "entity").lower()
    if lt == rt:
        return True
    return lt == "entity" or rt == "entity"


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _embedding_score(embed_fn: Optional[Callable[[str], np.ndarray]], left: str, right: str) -> float:
    if embed_fn is None:
        return 0.0
    try:
        lvec = np.asarray(embed_fn(left), dtype=np.float32)
        rvec = np.asarray(embed_fn(right), dtype=np.float32)
        score = _cosine(lvec, rvec)
        return max(0.0, min(1.0, (score + 1.0) / 2.0))
    except Exception:
        return 0.0


def _node_strings(node: Dict) -> Tuple[str, List[str]]:
    label = (node.get("label") or "").strip()
    aliases = [str(a).strip() for a in node.get("aliases", []) if str(a).strip()]
    if label and label not in aliases:
        aliases.append(label)
    return label, aliases


def _candidate_score(node: Dict, existing: Dict, embed_fn: Optional[Callable[[str], np.ndarray]]) -> Tuple[float, Dict]:
    label, aliases = _node_strings(node)
    existing_label, existing_aliases = _node_strings(existing)

    norm_label = _normalize_label(label)
    existing_norms = {_normalize_label(existing_label)} | {_normalize_label(a) for a in existing_aliases}
    exact_norm = 1.0 if norm_label and norm_label in existing_norms else 0.0

    lexical = 0.0
    node_tokens = _tokenize(label)
    for candidate_alias in existing_aliases:
        lexical = max(lexical, _jaccard(node_tokens, _tokenize(candidate_alias)))

    emb = _embedding_score(embed_fn, label, existing_label)
    compatibility = 1.0 if _type_compatible(node.get("entity_type", "entity"), existing.get("entity_type", "entity")) else 0.0

    score = (0.45 * emb) + (0.35 * lexical) + (0.2 * exact_norm)
    score = score * compatibility

    return score, {
        "exact_norm": round(exact_norm, 4),
        "lexical": round(lexical, 4),
        "embedding": round(emb, 4),
        "type_compatible": bool(compatibility),
    }


def _merge_node(existing: Dict, incoming: Dict):
    existing_aliases = set(existing.get("aliases", []))
    for alias in incoming.get("aliases", []):
        if alias and alias not in existing_aliases:
            existing.setdefault("aliases", []).append(alias)
            existing_aliases.add(alias)

    existing.setdefault("provenance", [])
    existing["provenance"].extend(incoming.get("provenance", []))

    prev_conf = float(existing.get("confidence", 0.6))
    inc_conf = float(incoming.get("confidence", 0.6))
    existing["confidence"] = round(min(0.98, (prev_conf * 0.8) + (inc_conf * 0.2)), 4)


def _append_pending_review(
    registry: Dict,
    file_id: str,
    node: Dict,
    candidate: Optional[Dict],
    score: float,
    breakdown: Dict,
):
    registry.setdefault("pending_reviews", []).append(
        {
            "review_id": f"rvw_{int(time.time() * 1000)}_{len(registry.get('pending_reviews', []))}",
            "file_id": file_id,
            "node_canonical_id": node.get("canonical_id"),
            "node_label": node.get("label"),
            "candidate_canonical_id": candidate.get("canonical_id") if candidate else None,
            "candidate_label": candidate.get("label") if candidate else None,
            "score": round(score, 4),
            "score_breakdown": breakdown,
            "status": "pending",
            "created_at": time.time(),
        }
    )


def resolve_canonical_graph(
    file_id: str,
    nodes: List[Dict],
    edges: List[Dict],
    embed_fn: Optional[Callable[[str], np.ndarray]] = None,
) -> Dict:
    registry = _load_registry()
    global_nodes = registry.get("canonical_nodes", [])
    global_idx = {n.get("canonical_id"): n for n in global_nodes if n.get("canonical_id")}

    canonical_id_map: Dict[str, str] = {}
    decisions: List[Dict] = []
    merged_count = 0
    created_count = 0
    review_count = 0

    for node in nodes:
        source_id = node.get("canonical_id")
        if not source_id:
            continue

        existing_same_id = global_idx.get(source_id)
        if existing_same_id:
            _merge_node(existing_same_id, node)
            canonical_id_map[source_id] = source_id
            decisions.append(
                {
                    "source_id": source_id,
                    "target_id": source_id,
                    "decision": "merge_id",
                    "score": 1.0,
                }
            )
            merged_count += 1
            continue

        best_score = 0.0
        best_candidate = None
        best_breakdown = {}
        for existing in global_nodes:
            score, breakdown = _candidate_score(node, existing, embed_fn)
            if score > best_score:
                best_score = score
                best_candidate = existing
                best_breakdown = breakdown

        if best_candidate and best_score >= MERGE_THRESHOLD:
            target_id = best_candidate.get("canonical_id")
            if target_id:
                _merge_node(best_candidate, node)
                canonical_id_map[source_id] = target_id
                registry.setdefault("merge_history", []).append(
                    {
                        "file_id": file_id,
                        "source_id": source_id,
                        "target_id": target_id,
                        "score": round(best_score, 4),
                        "score_breakdown": best_breakdown,
                        "merged_at": time.time(),
                    }
                )
                decisions.append(
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "decision": "merge_similarity",
                        "score": round(best_score, 4),
                        "score_breakdown": best_breakdown,
                    }
                )
                merged_count += 1
                continue

        global_nodes.append(node)
        global_idx[source_id] = node
        canonical_id_map[source_id] = source_id
        created_count += 1

        if best_candidate and best_score >= REVIEW_THRESHOLD:
            _append_pending_review(registry, file_id, node, best_candidate, best_score, best_breakdown)
            decisions.append(
                {
                    "source_id": source_id,
                    "target_id": source_id,
                    "decision": "new_pending_review",
                    "score": round(best_score, 4),
                    "score_breakdown": best_breakdown,
                    "candidate_id": best_candidate.get("canonical_id"),
                }
            )
            review_count += 1
        else:
            decisions.append(
                {
                    "source_id": source_id,
                    "target_id": source_id,
                    "decision": "new_entity",
                    "score": round(best_score, 4),
                    "score_breakdown": best_breakdown,
                }
            )

    remapped_nodes: List[Dict] = []
    for node in nodes:
        source_id = node.get("canonical_id")
        target_id = canonical_id_map.get(source_id, source_id)
        remapped_nodes.append({**node, "canonical_id": target_id})

    remapped_edges: List[Dict] = []
    for edge in edges:
        src = edge.get("source_canonical_id")
        tgt = edge.get("target_canonical_id")
        remapped_edges.append(
            {
                **edge,
                "source_canonical_id": canonical_id_map.get(src, src),
                "target_canonical_id": canonical_id_map.get(tgt, tgt),
            }
        )

    registry["canonical_nodes"] = global_nodes
    _save_registry(registry)

    return {
        "resolved_nodes": remapped_nodes,
        "resolved_edges": remapped_edges,
        "resolution_report": {
            "nodes_input": len(nodes),
            "edges_input": len(edges),
            "merged_count": merged_count,
            "created_count": created_count,
            "pending_review_count": review_count,
            "registry_total_nodes": len(global_nodes),
            "registry_total_pending_reviews": len(registry.get("pending_reviews", [])),
            "merge_threshold": MERGE_THRESHOLD,
            "review_threshold": REVIEW_THRESHOLD,
            "decisions": decisions[:150],
        },
    }


def list_pending_reviews(status: Optional[str] = "pending", limit: int = 100) -> Dict:
    registry = _load_registry()
    reviews = registry.get("pending_reviews", [])

    if status:
        status_norm = status.strip().lower()
        reviews = [r for r in reviews if str(r.get("status", "")).lower() == status_norm]

    reviews = sorted(reviews, key=lambda r: r.get("created_at", 0), reverse=True)
    reviews = reviews[: max(1, min(limit, 500))]

    return {
        "reviews": reviews,
        "count": len(reviews),
        "updated_at": registry.get("updated_at"),
    }


def apply_review_decision(review_id: str, decision: str, decided_by: Optional[str] = None) -> Dict:
    registry = _load_registry()
    reviews = registry.get("pending_reviews", [])
    nodes = registry.get("canonical_nodes", [])
    node_idx = {n.get("canonical_id"): n for n in nodes if n.get("canonical_id")}

    review = None
    for r in reviews:
        if r.get("review_id") == review_id:
            review = r
            break

    if not review:
        return {"ok": False, "error": "review_not_found"}

    if review.get("status") != "pending":
        return {"ok": False, "error": "review_already_resolved", "review": review}

    decision_norm = (decision or "").strip().lower()
    if decision_norm not in ("approve", "reject"):
        return {"ok": False, "error": "invalid_decision"}

    source_id = review.get("node_canonical_id")
    target_id = review.get("candidate_canonical_id")
    source_node = node_idx.get(source_id)
    target_node = node_idx.get(target_id)

    if decision_norm == "approve" and source_node and target_node and source_id != target_id:
        _merge_node(target_node, source_node)
        registry["canonical_nodes"] = [n for n in nodes if n.get("canonical_id") != source_id]
        registry.setdefault("merge_history", []).append(
            {
                "file_id": review.get("file_id"),
                "source_id": source_id,
                "target_id": target_id,
                "score": review.get("score", 0.0),
                "score_breakdown": review.get("score_breakdown", {}),
                "merged_at": time.time(),
                "decision_source": "human_review",
            }
        )

    review["status"] = "approved" if decision_norm == "approve" else "rejected"
    review["decided_at"] = time.time()
    review["decided_by"] = decided_by or "ui"

    _save_registry(registry)

    return {
        "ok": True,
        "review": review,
        "registry_total_nodes": len(registry.get("canonical_nodes", [])),
    }


def split_entity_from_alias(
    canonical_id: str,
    alias: str,
    entity_type: Optional[str] = None,
    decided_by: Optional[str] = None,
) -> Dict:
    registry = _load_registry()
    nodes = registry.get("canonical_nodes", [])
    node = next((n for n in nodes if n.get("canonical_id") == canonical_id), None)
    if not node:
        return {"ok": False, "error": "canonical_node_not_found"}

    alias_norm = (alias or "").strip()
    if not alias_norm:
        return {"ok": False, "error": "alias_required"}

    aliases = [str(a).strip() for a in node.get("aliases", []) if str(a).strip()]
    if alias_norm not in aliases:
        return {"ok": False, "error": "alias_not_found"}

    new_entity_type = (entity_type or node.get("entity_type") or "entity").strip().lower()
    new_canonical_id = _canonical_entity_id(new_entity_type, alias_norm)
    if any(n.get("canonical_id") == new_canonical_id for n in nodes):
        return {"ok": False, "error": "target_canonical_id_exists", "canonical_id": new_canonical_id}

    source_provenance = node.get("provenance", [])
    alias_lower = alias_norm.lower()
    new_provenance = [
        p for p in source_provenance
        if alias_lower in str(p.get("chunk_preview", "")).lower()
    ]
    if not new_provenance and source_provenance:
        new_provenance = [source_provenance[0]]

    new_node = {
        "canonical_id": new_canonical_id,
        "label": alias_norm,
        "entity_type": new_entity_type,
        "ner_label": node.get("ner_label", "ENTITY"),
        "aliases": [alias_norm],
        "confidence": min(0.9, float(node.get("confidence", 0.6))),
        "provenance": new_provenance,
        "first_seen_file_id": (new_provenance[0].get("file_id") if new_provenance else node.get("first_seen_file_id")),
        "temporal": node.get("temporal", {"valid_from": None, "valid_to": None}),
        "split_from": canonical_id,
        "source_files": sorted({p.get("file_id") for p in new_provenance if p.get("file_id")}),
    }

    if len(aliases) > 1:
        node["aliases"] = [a for a in aliases if a != alias_norm]
    else:
        # Keep original alias set intact if removing would empty aliases.
        node["aliases"] = aliases

    nodes.append(new_node)
    registry["canonical_nodes"] = nodes
    registry.setdefault("split_history", []).append(
        {
            "source_canonical_id": canonical_id,
            "new_canonical_id": new_canonical_id,
            "alias": alias_norm,
            "split_at": time.time(),
            "decided_by": decided_by or "repair_api",
        }
    )
    _save_registry(registry)

    return {
        "ok": True,
        "source_canonical_id": canonical_id,
        "new_canonical_id": new_canonical_id,
        "note": "Alias split applied to registry. Reprocess affected file(s) to fully propagate graph edges.",
    }


def registry_metrics() -> Dict:
    registry = _load_registry()
    nodes = registry.get("canonical_nodes", [])
    pending = registry.get("pending_reviews", [])
    merge_history = registry.get("merge_history", [])
    split_history = registry.get("split_history", [])

    alias_count = sum(len(n.get("aliases", [])) for n in nodes)
    unique_entity_types = sorted({str(n.get("entity_type", "entity")) for n in nodes})

    return {
        "canonical_node_count": len(nodes),
        "total_alias_count": alias_count,
        "avg_aliases_per_node": round(alias_count / max(1, len(nodes)), 2),
        "pending_review_count": len([r for r in pending if r.get("status") == "pending"]),
        "resolved_review_count": len([r for r in pending if r.get("status") != "pending"]),
        "merge_history_count": len(merge_history),
        "split_history_count": len(split_history),
        "entity_types": unique_entity_types,
        "updated_at": registry.get("updated_at"),
    }
