"""Step 8 — EDA Intelligence Engine (semantic + graph-aware, not traditional).

WHY: surface health/anomaly/drift signals about the *semantics*, not just raw stats.
PRODUCES: graph-density/topology stats, semantic cluster map, confidence overlays,
          semantic-drift indicators (vs accumulated semantic memory).
ORDERING: after extraction + semantic learning so both current and historical signal
          are available; before validation/governance which consume EDA flags.
ENABLES: trust scoring (9), governance prioritization (10), and the EDA dashboards.
"""
from __future__ import annotations

from collections import Counter

from . import _stats
from . import s07_semantic_learning as sl


def _numeric_eda(corpus: dict, metadata: dict) -> dict:
    """Statistical EDA for tabular sources (Sections 2 & 3 of the Observatory)."""
    columns = (corpus or {}).get("columns")
    rows = (corpus or {}).get("table_rows")
    if not columns or not rows:
        return {"is_tabular": False}

    label_by_col = {c["column"]: c.get("semantic_label", "") for c in (metadata or {}).get("columns", [])}
    dtype_by_col = {c["column"]: c.get("datatype", "") for c in (metadata or {}).get("columns", [])}
    col_meta = [{"column": c, "semantic_label": label_by_col.get(c, ""), "datatype": dtype_by_col.get(c, "")} for c in columns]

    col_values = {c: [r["cells"].get(c, "") for r in rows] for c in columns}
    col_stats = [_stats.column_stats(c, col_values[c]) for c in columns]
    numeric_cols = {
        s["column"]: [float(str(v).replace(",", "")) for v in col_values[s["column"]]
                      if str(v).strip() and _is_num(v)]
        for s in col_stats if s["is_numeric"]
    }
    return {
        "is_tabular": True,
        "row_count": len(rows),
        "columns": col_stats,
        "correlation": _stats.correlation(numeric_cols),
        "consistency_checks": _stats.consistency_checks(col_meta, rows),
        "capabilities": {"supports_correlation": len(numeric_cols) >= 2, "supports_time_series": False},
    }


def _is_num(v) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except Exception:
        return False


def run_eda(extraction: dict, corpus: dict | None = None, metadata: dict | None = None) -> dict:
    entities = extraction["entities"]
    rels = extraction["relationships"]

    # --- Graph topology / density EDA ---
    nodes = {e["text"] for e in entities}
    degree: Counter = Counter()
    for r in rels:
        degree[r["source"]] += 1
        degree[r["target"]] += 1
    n, m = len(nodes), len(rels)
    max_edges = n * (n - 1) / 2 if n > 1 else 1
    density = round(m / max_edges, 4) if max_edges else 0.0
    orphan_nodes = [e["text"] for e in entities if degree[e["text"]] == 0]

    # --- Confidence overlay EDA ---
    confs = [e["audit"]["confidence"]["score"] for e in entities] or [0.0]
    bands = Counter(e["audit"]["confidence"]["band"] for e in entities)

    # --- Semantic cluster map EDA ---
    type_dist = Counter(e["entity_type"] for e in entities)

    # --- Semantic drift EDA (current vs learned memory priors) ---
    drift = []
    for e in entities[:200]:
        learned = sl.prior_for(e["text"])
        cur = e["audit"]["confidence"]["score"]
        if abs(learned - cur) > 0.3:
            drift.append({"term": e["text"], "current": cur, "learned_prior": learned})

    return {
        "source_id": extraction["source_id"],
        "graph_eda": {
            "node_count": n,
            "edge_count": m,
            "density": density,
            "avg_degree": round(sum(degree.values()) / n, 3) if n else 0.0,
            "orphan_node_count": len(orphan_nodes),
            "orphan_sample": orphan_nodes[:10],
        },
        "confidence_eda": {
            "avg_confidence": round(sum(confs) / len(confs), 4),
            "band_distribution": dict(bands),
        },
        "semantic_cluster_map": dict(type_dist),
        "relation_distribution": dict(Counter(r["relation"] for r in rels)),
        "semantic_drift": {"count": len(drift), "samples": drift[:10]},
        "numeric": _numeric_eda(corpus, metadata),
    }
