"""Step 14 — Wiki + Explainability Generation.

WHY: semantic intelligence is only trustworthy if a human can read WHY the graph says
     what it says.
PRODUCES: per-entity wiki pages with summary, key facts (cited), relationship
          explanations, lineage explanation, and confidence explanation.
ORDERING: last — it explains the fully built + validated graph.
ENABLES: the Wiki + Graph dual view and explainable graph intelligence UI.
"""
from __future__ import annotations

from ..config import settings
from ..storage.jsonstore import read_json, write_json
from . import s12_graph as graph_layer


def _confidence_explanation(score: float) -> str:
    if score >= settings.band_high:
        return f"High confidence ({score}): corroborated by multiple groundings and ontology-valid edges."
    if score >= settings.band_low:
        return f"Medium confidence ({score}): partially supported; some signals weak or unreviewed."
    return f"Low confidence ({score}): sparse evidence — treat as a hypothesis pending review."


def build_pages(canonical: dict, validation: dict) -> dict:
    graph = graph_layer.get_graph()
    nodes, edges = graph["nodes"], graph["edges"]
    touched = set(canonical["text_to_canonical"].values())
    pages_dir = settings.dir("wiki")
    index = read_json(pages_dir / "index.json", {"pages": {}})

    built = 0
    for cid in touched:
        node = nodes.get(cid)
        if not node:
            continue
        related, facts, rel_explanations = [], [], []
        for e in edges.values():
            if e.get("suppressed"):
                continue
            if e["source"] == cid or e["target"] == cid:
                other = e["target"] if e["source"] == cid else e["source"]
                other_label = nodes.get(other, {}).get("label", other)
                related.append(other_label)
                direction = "->" if e["source"] == cid else "<-"
                facts.append(
                    {
                        "fact": f"{node['label']} {direction} [{e['relation']}] {direction} {other_label}",
                        "confidence": e["confidence"],
                        "provenance": e["provenance"],
                    }
                )
                rel_explanations.append(
                    f"Linked to '{other_label}' via '{e['relation']}' "
                    f"(confidence {e['confidence']}, governance={e['governance']}, "
                    f"seen in sources {e['provenance']})."
                )

        page = {
            "canonical_id": cid,
            "title": node["label"],
            "entity_type": node["entity_type"],
            "aliases": node["aliases"],
            "summary": f"'{node['label']}' is a {node['entity_type']} appearing across "
            f"{len(node['provenance'])} source(s) with {len(facts)} related relationship(s).",
            "key_facts": facts[:25],
            "related_entities": sorted(set(related))[:25],
            "explanations": {
                "relationships": rel_explanations[:25],
                "lineage": f"Derived from sources {node['provenance']}; aliases merged: {node['aliases']}.",
                "confidence": _confidence_explanation(validation.get("graph_trust_score", 0.0)),
            },
            "sources": node["provenance"],
        }
        write_json(pages_dir / f"{cid}.json", page)
        index["pages"][cid] = {"title": node["label"], "type": node["entity_type"]}
        built += 1

    write_json(pages_dir / "index.json", index)
    return {"source_id": canonical["source_id"], "pages_built": built, "wiki_total": len(index["pages"])}
