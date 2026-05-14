import hashlib
from typing import Dict, List, Tuple


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def canonical_entity_id(entity_type: str, label: str) -> str:
    norm = (label or "").strip().lower()
    etype = (entity_type or "entity").strip().lower()
    return _stable_id("ce", f"{etype}:{norm}")


def canonical_relation_id(source_id: str, relation: str, target_id: str, chunk_idx: int) -> str:
    rel = (relation or "related_to").strip().lower()
    return _stable_id("cr", f"{source_id}:{rel}:{target_id}:{chunk_idx}")


def build_canonical_nodes(file_id: str, entities: List[Dict]) -> Tuple[List[Dict], Dict[str, str]]:
    nodes: List[Dict] = []
    mention_to_canonical: Dict[str, str] = {}

    for ent in entities:
        label = (ent.get("text") or "").strip()
        if not label:
            continue

        entity_type = ent.get("type", "entity")
        canonical_id = canonical_entity_id(entity_type, label)
        mention_key = f"{ent.get('label', 'ENTITY')}::{label}"
        mention_to_canonical[mention_key] = canonical_id

        nodes.append({
            "canonical_id": canonical_id,
            "label": label,
            "entity_type": entity_type,
            "ner_label": ent.get("label", "ENTITY"),
            "aliases": [label],
            "confidence": 0.65,
            "provenance": [{
                "file_id": file_id,
                "chunk_idx": ent.get("chunk_idx"),
                "chunk_preview": ent.get("chunk_preview", ""),
                "extractor": "entity_extraction",
            }],
            "first_seen_file_id": file_id,
            "temporal": {"valid_from": None, "valid_to": None},
        })

    # De-duplicate canonical nodes by id while combining provenance/aliases.
    dedup: Dict[str, Dict] = {}
    for node in nodes:
        cid = node["canonical_id"]
        if cid not in dedup:
            dedup[cid] = node
            continue

        existing = dedup[cid]
        for alias in node.get("aliases", []):
            if alias not in existing["aliases"]:
                existing["aliases"].append(alias)
        existing["provenance"].extend(node.get("provenance", []))

    return list(dedup.values()), mention_to_canonical


def build_canonical_edges(file_id: str, relationships: List[Dict], mention_to_canonical: Dict[str, str]) -> List[Dict]:
    edges: List[Dict] = []
    for rel in relationships:
        src_label = (rel.get("source") or "").strip()
        tgt_label = (rel.get("target") or "").strip()
        if not src_label or not tgt_label or src_label == tgt_label:
            continue

        # Mention keys default to ENTITY because relationship extraction currently
        # emits only string labels, not full mention objects.
        src_id = mention_to_canonical.get(f"ENTITY::{src_label}") or canonical_entity_id("entity", src_label)
        tgt_id = mention_to_canonical.get(f"ENTITY::{tgt_label}") or canonical_entity_id("entity", tgt_label)
        chunk_idx = int(rel.get("chunk_idx", -1) or -1)

        edges.append({
            "canonical_relation_id": canonical_relation_id(src_id, rel.get("relation", "related_to"), tgt_id, chunk_idx),
            "source_canonical_id": src_id,
            "target_canonical_id": tgt_id,
            "relation": rel.get("relation", "related_to"),
            "confidence": 0.55,
            "provenance": [{
                "file_id": file_id,
                "chunk_idx": rel.get("chunk_idx"),
                "chunk_preview": rel.get("chunk_preview", ""),
                "context": rel.get("context", ""),
                "extractor": "relationship_extraction",
            }],
            "temporal": {"valid_from": None, "valid_to": None},
        })

    return edges


def validate_canonical_graph(nodes: List[Dict], edges: List[Dict]) -> Dict:
    node_required = {
        "canonical_id",
        "label",
        "entity_type",
        "aliases",
        "confidence",
        "provenance",
        "temporal",
    }
    edge_required = {
        "canonical_relation_id",
        "source_canonical_id",
        "target_canonical_id",
        "relation",
        "confidence",
        "provenance",
        "temporal",
    }

    errors: List[str] = []
    node_ids = set()

    for idx, node in enumerate(nodes):
        missing = node_required - set(node.keys())
        if missing:
            errors.append(f"node[{idx}] missing fields: {sorted(missing)}")
        cid = node.get("canonical_id")
        if cid in node_ids:
            errors.append(f"duplicate canonical_id: {cid}")
        if cid:
            node_ids.add(cid)

    for idx, edge in enumerate(edges):
        missing = edge_required - set(edge.keys())
        if missing:
            errors.append(f"edge[{idx}] missing fields: {sorted(missing)}")
        if edge.get("source_canonical_id") not in node_ids:
            errors.append(f"edge[{idx}] source not found: {edge.get('source_canonical_id')}")
        if edge.get("target_canonical_id") not in node_ids:
            errors.append(f"edge[{idx}] target not found: {edge.get('target_canonical_id')}")

    return {
        "valid": len(errors) == 0,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "error_count": len(errors),
        "errors": errors[:25],
    }
