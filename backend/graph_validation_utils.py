from collections import defaultdict, deque
from typing import Any, Dict, List, Set, Tuple


def build_light_graph(entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    node_ids: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for ent in entities:
        label = str(ent.get("text") or "").strip()
        if not label or label.lower() in node_ids:
            continue
        nid = f"n{len(nodes)}"
        node_ids[label.lower()] = nid
        nodes.append({
            "id": nid,
            "label": label,
            "entity_type": ent.get("type") or ent.get("label") or "entity",
        })

    seen: Set[Tuple[str, str, str]] = set()
    for rel in relationships:
        source = str(rel.get("source") or "").strip().lower()
        target = str(rel.get("target") or "").strip().lower()
        relation = str(rel.get("relation") or "related_to").strip()
        if source not in node_ids or target not in node_ids:
            continue
        key = (node_ids[source], relation, node_ids[target])
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "source": node_ids[source],
            "target": node_ids[target],
            "relation": relation,
            "confidence": float(rel.get("eda_confidence", 0.0) or 0.0),
            "chunk_idx": rel.get("chunk_idx"),
        })

    return {"nodes": nodes, "edges": edges}


def _components(node_ids: List[str], undirected_adj: Dict[str, Set[str]]) -> List[List[str]]:
    seen: Set[str] = set()
    components: List[List[str]] = []
    for nid in node_ids:
        if nid in seen:
            continue
        q = deque([nid])
        seen.add(nid)
        comp: List[str] = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nxt in undirected_adj.get(cur, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        components.append(comp)
    return components


def graph_metrics(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    n = len(nodes)
    e = len(edges)

    out_degree = defaultdict(int)
    in_degree = defaultdict(int)
    undirected_adj: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        s = str(edge.get("source") or "")
        t = str(edge.get("target") or "")
        if not s or not t:
            continue
        out_degree[s] += 1
        in_degree[t] += 1
        undirected_adj[s].add(t)
        undirected_adj[t].add(s)

    node_ids = [str(n0.get("id")) for n0 in nodes if n0.get("id")]
    isolated = [nid for nid in node_ids if out_degree[nid] == 0 and in_degree[nid] == 0]
    components = _components(node_ids, undirected_adj) if node_ids else []

    density = 0.0
    if n > 1:
        density = e / float(n * (n - 1))

    degrees = [out_degree[nid] + in_degree[nid] for nid in node_ids]
    noisy_hubs = [nid for nid in node_ids if (out_degree[nid] + in_degree[nid]) >= max(8, int(0.2 * max(1, n)))]

    central = sorted(
        [{"node_id": nid, "degree": out_degree[nid] + in_degree[nid]} for nid in node_ids],
        key=lambda x: x["degree"],
        reverse=True,
    )[:15]

    return {
        "node_count": n,
        "edge_count": e,
        "graph_density": round(density, 6),
        "degree_distribution": degrees,
        "isolated_node_ids": isolated,
        "disconnected_component_count": len(components),
        "disconnected_components": components[:20],
        "central_entities": central,
        "noisy_hub_node_ids": noisy_hubs,
    }


def validate_relationship_quality(
    graph: Dict[str, Any],
    rels: List[Dict[str, Any]],
    weak_threshold: float = 0.5,
) -> Dict[str, Any]:
    nodes = {str(n.get("id")): n for n in graph.get("nodes", []) if n.get("id")}
    edges = graph.get("edges", [])

    weak_edges: List[Dict[str, Any]] = []
    invalid_edges: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    sparse_regions: List[Dict[str, Any]] = []
    missing_inverse: List[Dict[str, Any]] = []
    cross_doc_inconsistencies: List[Dict[str, Any]] = []

    seen = defaultdict(int)
    pair_relations: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    reverse_idx = set()

    for e in edges:
        s = str(e.get("source") or "")
        t = str(e.get("target") or "")
        r = str(e.get("relation") or "related_to")
        if not s or not t:
            continue
        seen[(s, r, t)] += 1
        reverse_idx.add((t, r, s))
        pair_relations[(s, t)].add(r)
        conf = float(e.get("confidence", 0.0) or 0.0)
        if conf < weak_threshold:
            weak_edges.append({"source": s, "target": t, "relation": r, "confidence": round(conf, 4)})

        if s == t or s not in nodes or t not in nodes:
            invalid_edges.append({"source": s, "target": t, "relation": r, "reason": "self_loop_or_missing_node"})

    for key, count in seen.items():
        if count > 1:
            s, r, t = key
            duplicates.append({"source": s, "target": t, "relation": r, "count": count})

    for edge in edges:
        s = str(edge.get("source") or "")
        t = str(edge.get("target") or "")
        r = str(edge.get("relation") or "related_to")
        if r in {"related_to", "cross_source_related"} and (s, r, t) not in reverse_idx:
            missing_inverse.append({"source": s, "target": t, "relation": r})

    for (s, t), rel_set in pair_relations.items():
        if len(rel_set) > 1:
            cross_doc_inconsistencies.append({"source": s, "target": t, "relations": sorted(rel_set)})

    deg = defaultdict(int)
    for e in edges:
        s = str(e.get("source") or "")
        t = str(e.get("target") or "")
        if s:
            deg[s] += 1
        if t:
            deg[t] += 1
    for nid, d in deg.items():
        if d <= 1:
            sparse_regions.append({"node_id": nid, "degree": d})

    return {
        "weak_edges": weak_edges[:250],
        "invalid_edge_patterns": invalid_edges[:250],
        "duplicate_relationships": duplicates[:250],
        "sparse_relationship_areas": sparse_regions[:300],
        "missing_inverse_relationships": missing_inverse[:250],
        "cross_document_inconsistencies": cross_doc_inconsistencies[:250],
    }
