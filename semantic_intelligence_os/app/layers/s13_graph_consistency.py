"""Step 13 — Graph Validation & Consistency Engine.

WHY: a graph degrades silently; correctness must be continuously verifiable.
PRODUCES: orphan-node, cycle, ontology-violation, and drift checks + a graph trust
          score and an observability artifact.
ORDERING: after construction; runs per-ingestion and on-demand (continuous).
ENABLES: the AI Trust Command Center, repair workflows, and decay monitoring.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from ..storage.jsonstore import write_json
from . import s10_ontology as onto_layer
from . import s12_graph as graph_layer

_REPORT_PATH = settings.dir("graph") / "consistency_report.json"


def _find_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """Detect directed cycles via DFS (returns sample cycles, capped)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    cycles: list[list[str]] = []

    def dfs(node, stack):
        if len(cycles) >= 10:
            return
        color[node] = GRAY
        stack.append(node)
        for nxt in adj.get(node, []):
            if color.get(nxt) == GRAY:
                idx = stack.index(nxt) if nxt in stack else 0
                cycles.append(stack[idx:] + [nxt])
            elif color.get(nxt) == WHITE:
                dfs(nxt, stack)
        stack.pop()
        color[node] = BLACK

    for n in list(adj.keys()):
        if color[n] == WHITE:
            dfs(n, [])
    return cycles


def validate_graph() -> dict:
    graph = graph_layer.get_graph()
    nodes, edges = graph["nodes"], graph["edges"]
    onto = onto_layer.load_ontology()
    constraints = onto["relationship_constraints"]

    active_edges = [e for e in edges.values() if not e.get("suppressed")]

    # Orphan nodes: no active incident edge.
    incident = set()
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in active_edges:
        incident.add(e["source"])
        incident.add(e["target"])
        adj.setdefault(e["source"], []).append(e["target"])
    orphans = [n for n in nodes if n not in incident]

    # Ontology violations on persisted edges.
    violations = []
    for e in active_edges:
        s_t = nodes.get(e["source"], {}).get("entity_type")
        t_t = nodes.get(e["target"], {}).get("entity_type")
        c = constraints.get(e["relation"])
        if c is None:
            violations.append({"edge": e["edge_id"], "reason": "unknown predicate"})
        elif c != "ANY" and not any(
            onto_layer._is_a(onto, s_t, a) and onto_layer._is_a(onto, t_t, b) for a, b in c
        ):
            violations.append({"edge": e["edge_id"], "reason": "type-constraint violation"})

    cycles = _find_cycles(adj)
    low_conf = [e["edge_id"] for e in active_edges if e["confidence"] < settings.band_low]

    n_edges = max(1, len(active_edges))
    consistency = round(
        1
        - 0.4 * (len(violations) / n_edges)
        - 0.2 * (len(orphans) / max(1, len(nodes)))
        - 0.2 * (len(low_conf) / n_edges)
        - 0.2 * min(1.0, len(cycles) / 5.0),
        4,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(nodes),
        "active_edge_count": len(active_edges),
        "orphan_nodes": {"count": len(orphans), "sample": orphans[:10]},
        "ontology_violations": {"count": len(violations), "sample": violations[:10]},
        "cycles": {"count": len(cycles), "sample": cycles[:5]},
        "low_confidence_edges": {"count": len(low_conf), "sample": low_conf[:10]},
        "graph_trust_score": max(0.0, consistency),
        "trust_band": "high" if consistency >= settings.band_high else "medium" if consistency >= settings.band_low else "low",
    }
    write_json(_REPORT_PATH, report)
    return report
