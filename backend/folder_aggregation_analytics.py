from collections import Counter, defaultdict
from typing import Any, Dict, List, Set


def _topic_bucket(entity_type: str) -> str:
    t = (entity_type or "entity").lower()
    if t in {"organization", "org", "company"}:
        return "organizations"
    if t in {"location", "gpe", "loc"}:
        return "locations"
    if t in {"time", "date"}:
        return "temporal"
    if t in {"value", "money", "percent", "number"}:
        return "numeric"
    if t in {"product", "event", "facility", "group"}:
        return "domain_entities"
    return "generic_entities"


def build_folder_analytics(
    file_id: str,
    entities: List[Dict[str, Any]],
    cross_file: Dict[str, Any],
) -> Dict[str, Any]:
    common_entities_counter = Counter(str(e.get("text") or "").strip().lower() for e in entities if str(e.get("text") or "").strip())
    common_entities = [{"entity": e, "count": c} for e, c in common_entities_counter.most_common(50)]

    topic_counter = Counter()
    for e in entities:
        topic_counter[_topic_bucket(str(e.get("type") or e.get("label") or "entity"))] += 1
    dominant = [{"topic": t, "count": c} for t, c in topic_counter.most_common(12)]

    overlaps = cross_file.get("document_overlaps", []) or []
    docs = set([file_id])
    for o in overlaps:
        docs.add(str(o.get("other_file") or ""))
    docs = {d for d in docs if d}

    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for o in overlaps:
        a = str(o.get("source_file") or "")
        b = str(o.get("other_file") or "")
        if a and b and float(o.get("overlap_ratio", 0.0) or 0.0) >= 0.1:
            adjacency[a].add(b)
            adjacency[b].add(a)

    clusters: List[List[str]] = []
    seen: Set[str] = set()
    for d in docs:
        if d in seen:
            continue
        q = [d]
        seen.add(d)
        comp = []
        while q:
            cur = q.pop(0)
            comp.append(cur)
            for nxt in adjacency.get(cur, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        clusters.append(sorted(comp))

    cluster_rows = [{"cluster_id": idx + 1, "documents": c, "size": len(c)} for idx, c in enumerate(sorted(clusters, key=lambda x: len(x), reverse=True))]

    return {
        "document_clusters": cluster_rows,
        "common_entities": common_entities,
        "dominant_concepts": dominant,
        "semantic_overlaps": overlaps,
        "summary": {
            "document_count": len(docs),
            "cluster_count": len(cluster_rows),
            "overlap_pairs": len(overlaps),
        },
    }
