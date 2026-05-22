import os
import json
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple


PROCESSED_DIR = "data/processed"


def _safe_read(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _normalized_aliases(node: Dict[str, Any]) -> Set[str]:
    aliases = {str(node.get("label") or "").strip().lower()}
    for alias in node.get("aliases", []) or []:
        if str(alias).strip():
            aliases.add(str(alias).strip().lower())
    return {a for a in aliases if a}


def cross_file_semantic_linking(file_id: str, resolved_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_file_nodes: Dict[str, List[Dict[str, Any]]] = {}
    per_file_checksums: Dict[str, str] = {}
    for name in os.listdir(PROCESSED_DIR) if os.path.exists(PROCESSED_DIR) else []:
        if not name.endswith("_canonical.json"):
            continue
        src_file_id = name.replace("_canonical.json", "")
        payload = _safe_read(os.path.join(PROCESSED_DIR, name))
        if not payload:
            continue
        per_file_nodes[src_file_id] = payload.get("resolved_nodes", []) or []

    for name in os.listdir(PROCESSED_DIR) if os.path.exists(PROCESSED_DIR) else []:
        if not name.endswith("_status.json"):
            continue
        payload = _safe_read(os.path.join(PROCESSED_DIR, name))
        if not payload:
            continue
        fid = str(payload.get("file_id") or "")
        if not fid:
            continue
        per_file_checksums[fid] = str(payload.get("checksum") or "")

    source_nodes = resolved_nodes or per_file_nodes.get(file_id, [])
    source_registry = {str(n.get("canonical_id") or ""): _normalized_aliases(n) for n in source_nodes if n.get("canonical_id")}

    same_entity_links: List[Dict[str, Any]] = []
    semantic_duplicates: List[Dict[str, Any]] = []
    synonym_conflicts: List[Dict[str, Any]] = []
    canonical_drift: List[Dict[str, Any]] = []
    document_overlaps: List[Dict[str, Any]] = []
    cross_source_registry = []

    for cid, aliases in source_registry.items():
        cross_source_registry.append({"canonical_id": cid, "aliases": sorted(aliases), "source_file": file_id})

    source_label_to_cid = {alias: cid for cid, aliases in source_registry.items() for alias in aliases}

    for other_id, other_nodes in per_file_nodes.items():
        if other_id == file_id:
            continue
        overlap_count = 0
        other_alias_to_cid: Dict[str, str] = {}
        for n in other_nodes:
            cid = str(n.get("canonical_id") or "")
            if not cid:
                continue
            aliases = _normalized_aliases(n)
            for alias in aliases:
                other_alias_to_cid[alias] = cid

        shared_aliases = sorted(set(source_label_to_cid.keys()) & set(other_alias_to_cid.keys()))
        for alias in shared_aliases:
            overlap_count += 1
            src_cid = source_label_to_cid.get(alias)
            tgt_cid = other_alias_to_cid.get(alias)
            if src_cid == tgt_cid:
                same_entity_links.append({
                    "entity": alias,
                    "canonical_id": src_cid,
                    "files": [file_id, other_id],
                })
            else:
                canonical_drift.append({
                    "entity": alias,
                    "source_canonical_id": src_cid,
                    "other_canonical_id": tgt_cid,
                    "files": [file_id, other_id],
                })

        source_cids = {str(n.get("canonical_id") or "") for n in source_nodes if n.get("canonical_id")}
        other_cids = {str(n.get("canonical_id") or "") for n in other_nodes if n.get("canonical_id")}
        for cid in sorted((source_cids & other_cids)):
            semantic_duplicates.append({"canonical_id": cid, "files": [file_id, other_id]})

        if overlap_count > 0:
            source_unique = max(1, len(source_label_to_cid))
            overlap_ratio = overlap_count / source_unique
            document_overlaps.append(
                {
                    "source_file": file_id,
                    "other_file": other_id,
                    "shared_entity_count": overlap_count,
                    "overlap_ratio": round(overlap_ratio, 4),
                }
            )

    synonym_groups: Dict[str, Set[str]] = defaultdict(set)
    for item in same_entity_links:
        synonym_groups[item.get("canonical_id", "")].add(item.get("entity", ""))
    for cid, aliases in synonym_groups.items():
        if len(aliases) > 8:
            synonym_conflicts.append({"canonical_id": cid, "alias_count": len(aliases), "aliases": sorted(list(aliases))[:20]})

    duplicate_documents = []
    checksum_groups: Dict[str, List[str]] = defaultdict(list)
    for fid, checksum in per_file_checksums.items():
        if checksum:
            checksum_groups[checksum].append(fid)
    for checksum, ids in checksum_groups.items():
        if len(ids) > 1:
            duplicate_documents.append({"checksum": checksum, "file_ids": sorted(ids)})

    return {
        "same_entities_across_files": same_entity_links[:400],
        "semantic_duplicates": semantic_duplicates[:400],
        "synonym_conflicts": synonym_conflicts[:200],
        "canonical_drift": canonical_drift[:300],
        "cross_source_entity_registry": cross_source_registry[:800],
        "document_overlaps": document_overlaps[:300],
        "duplicate_documents": duplicate_documents[:120],
    }
