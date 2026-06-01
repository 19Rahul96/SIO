"""Step 12 — Knowledge Graph Construction.

WHY: materialize the validated, canonical, confidence-weighted enterprise graph.
PRODUCES: an upserted canonical graph (nodes + confidence-weighted edges) and an
          RDF-style triple export, with lineage-aware node provenance.
ORDERING: after canonicalization (needs canonical_ids) and governance (only accepted
          edges) — insertion is the payoff of all prior trust-building.
ENABLES: graph consistency validation (13) and wiki/explainability (14).
"""
from __future__ import annotations

from ..config import settings
from ..storage.jsonstore import read_json, write_json
from . import s07_semantic_learning as sl

_GRAPH_PATH = settings.dir("graph") / "canonical_graph.json"


def _load_graph() -> dict:
    return read_json(_GRAPH_PATH, {"nodes": {}, "edges": {}})


def _edge_confidence(rel: dict) -> float:
    base = {"related_to": 0.4}.get(rel["relation"], 0.7)
    # Co-occurrence reinforcement from learned memory.
    pair_boost = min(0.2, 0.02 * sl._load()["cooccurrence"].get(
        " :: ".join(sorted([rel["source"].lower(), rel["target"].lower()])), 0
    ))
    return round(min(1.0, base + pair_boost), 4)


def construct(canonical: dict, governance: dict, validation: dict) -> dict:
    graph = _load_graph()
    reg = read_json(settings.dir("canonical") / "registry.json", {"nodes": {}})["nodes"]
    t2c = canonical["text_to_canonical"]
    source_id = canonical["source_id"]

    # Upsert nodes from canonical registry (lineage-aware).
    added_nodes = 0
    for cid in set(t2c.values()):
        node = reg.get(cid)
        if not node:
            continue
        if cid not in graph["nodes"]:
            graph["nodes"][cid] = {
                "canonical_id": cid,
                "label": node["label"],
                "entity_type": node["entity_type"],
                "aliases": node["aliases"],
                "provenance": [],
            }
            added_nodes += 1
        prov = graph["nodes"][cid]["provenance"]
        if source_id not in prov:
            prov.append(source_id)

    # Insert ontology-accepted, confidence-weighted edges.
    triples, added_edges, skipped = [], 0, 0
    for rel in governance["accepted_relationships"]:
        s_cid = t2c.get(rel["source"])
        t_cid = t2c.get(rel["target"])
        if not s_cid or not t_cid or s_cid == t_cid:
            skipped += 1
            continue
        eid = f"{s_cid}|{rel['relation']}|{t_cid}"
        conf = _edge_confidence(rel)
        if eid not in graph["edges"]:
            graph["edges"][eid] = {
                "edge_id": eid,
                "source": s_cid,
                "target": t_cid,
                "relation": rel["relation"],
                "confidence": conf,
                "governance": rel["governance"]["action"],
                "provenance": [],
                "suppressed": False,
            }
            added_edges += 1
        if source_id not in graph["edges"][eid]["provenance"]:
            graph["edges"][eid]["provenance"].append(source_id)
        triples.append([s_cid, rel["relation"], t_cid])

    write_json(_GRAPH_PATH, graph)
    # RDF-style triple export for this source.
    write_json(settings.dir("graph") / f"{source_id}_triples.json", {"triples": triples})

    return {
        "source_id": source_id,
        "nodes_added": added_nodes,
        "edges_added": added_edges,
        "edges_skipped": skipped,
        "graph_node_total": len(graph["nodes"]),
        "graph_edge_total": len(graph["edges"]),
        "triple_count": len(triples),
    }


def get_graph() -> dict:
    return _load_graph()
