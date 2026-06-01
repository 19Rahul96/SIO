"""Per-entity × per-pipeline-layer confidence ledger (Section 5 heatmap).

Joins the confidence signals that each layer produces for an entity into one matrix:
  Extraction · Resolution · Canonicalization · Graph Insert · EDA Validation
Persists per-source (`confidence/{sid}.json`) and merges a global `confidence/matrix.json`
keyed by canonical_id (latest run wins). Missing signals are recorded as null so the
heatmap renders a gray "—" cell.
"""
from __future__ import annotations

from ..config import settings
from ..storage.jsonstore import read_json, write_json
from . import s07_semantic_learning as sl

LAYERS = ["Extraction", "Resolution", "Canonicalization", "Graph Insert", "EDA Validation"]


def build(extraction: dict, canonical: dict, eda: dict, validation: dict) -> dict:
    t2c = canonical.get("text_to_canonical", {})
    registry = read_json(settings.dir("canonical") / "registry.json", {"nodes": {}})["nodes"]
    graph = read_json(settings.dir("graph") / "canonical_graph.json", {"nodes": {}, "edges": {}})

    # Mean incident edge confidence per canonical node (Graph Insert signal).
    edge_conf: dict[str, list[float]] = {}
    for e in graph.get("edges", {}).values():
        if e.get("suppressed"):
            continue
        edge_conf.setdefault(e["source"], []).append(e["confidence"])
        edge_conf.setdefault(e["target"], []).append(e["confidence"])

    drift = {d["term"]: d for d in eda.get("semantic_drift", {}).get("samples", [])}
    trust = validation.get("graph_trust_score")

    rows = []
    seen = set()
    for ent in extraction.get("entities", []):
        cid = t2c.get(ent["text"])
        if not cid or cid in seen:
            continue
        seen.add(cid)
        node = registry.get(cid, {})
        extraction_score = ent.get("audit", {}).get("confidence", {}).get("score")
        resolution_score = round(sl.prior_for(ent["text"]), 4)
        canon_score = node.get("confidence")
        gi = edge_conf.get(cid)
        graph_score = round(sum(gi) / len(gi), 4) if gi else None
        if ent["text"] in drift:
            d = drift[ent["text"]]
            eda_score = round(1.0 - abs(d["learned_prior"] - d["current"]), 4)
        else:
            eda_score = trust
        rows.append({
            "canonical_id": cid,
            "label": node.get("label", ent["text"]),
            "entity_type": ent.get("entity_type"),
            "scores": {
                "Extraction": extraction_score,
                "Resolution": resolution_score,
                "Canonicalization": canon_score,
                "Graph Insert": graph_score,
                "EDA Validation": eda_score,
            },
        })

    result = {"source_id": extraction["source_id"], "layers": LAYERS, "entities": rows}
    write_json(settings.dir("confidence") / f"{extraction['source_id']}.json", result)

    # Merge into the global matrix (latest run wins per canonical_id).
    matrix_path = settings.dir("confidence") / "matrix.json"
    matrix = read_json(matrix_path, {"layers": LAYERS, "entities": {}})
    for r in rows:
        matrix["entities"][r["canonical_id"]] = r
    write_json(matrix_path, matrix)
    return result
