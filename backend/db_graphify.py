import json
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Tuple

from graph_builder import GraphBuilder
from knowledge_schema import canonical_entity_id
from wiki_builder import WikiBuilder


_EDGE_CONFIDENCE = {
    "EXTRACTED": 1.0,
    "INFERRED": 0.7,
    "AMBIGUOUS": 0.4,
}


def install_graphify() -> str:
    """Ensure Graphify CLI is available and return its executable path."""
    cli_path = shutil.which("graphify")
    if not cli_path:
        raise RuntimeError("Graphify CLI not found on PATH. Install graphifyy[sql] in backend venv.")
    return cli_path


def run_graphify_extract(schema_dir: str, output_dir: str, backend: str = "claude") -> Dict[str, Any]:
    cli = install_graphify()
    os.makedirs(output_dir, exist_ok=True)

    cmd = [cli, "extract", schema_dir, "--backend", backend]
    proc = subprocess.run(
        cmd,
        cwd=output_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    graph_json_path = os.path.join(output_dir, "graph.json")
    if not os.path.exists(graph_json_path):
        # Fallback search in output subtree.
        for root, _, files in os.walk(output_dir):
            if "graph.json" in files:
                graph_json_path = os.path.join(root, "graph.json")
                break

    return {
        "ok": proc.returncode == 0,
        "return_code": proc.returncode,
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-6000:],
        "graph_json_path": graph_json_path if os.path.exists(graph_json_path) else None,
        "command": " ".join(cmd),
    }


def parse_graphify_graph(graph_json_path: str) -> Dict[str, Any]:
    with open(graph_json_path, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    return {
        "nodes": nodes if isinstance(nodes, list) else [],
        "edges": edges if isinstance(edges, list) else [],
        "raw": data,
    }


def _node_label(node: Dict[str, Any]) -> str:
    return str(node.get("label") or node.get("name") or node.get("id") or "unknown").strip()


def _node_type(node: Dict[str, Any]) -> str:
    return str(node.get("type") or node.get("node_type") or "entity").strip().lower()


def map_graphify_to_canonical(graphify_graph: Dict[str, Any], db_id: str) -> Dict[str, List[Dict[str, Any]]]:
    nodes = graphify_graph.get("nodes", [])
    edges = graphify_graph.get("edges", [])

    node_by_key: Dict[str, Dict[str, Any]] = {}
    resolved_nodes: List[Dict[str, Any]] = []

    for node in nodes:
        label = _node_label(node)
        entity_type = _node_type(node)
        cid = canonical_entity_id(entity_type, label)
        node_key = str(node.get("id") or label)
        node_by_key[node_key] = {
            "canonical_id": cid,
            "label": label,
        }

        resolved_nodes.append(
            {
                "canonical_id": cid,
                "label": label,
                "entity_type": entity_type,
                "aliases": [label],
                "confidence": 0.8,
                "provenance": [
                    {
                        "file_id": db_id,
                        "chunk_idx": -1,
                        "chunk_preview": "Generated from Graphify schema extraction",
                        "extractor": "graphify",
                    }
                ],
                "first_seen_file_id": db_id,
                "temporal": {"valid_from": None, "valid_to": None},
            }
        )

    resolved_edges: List[Dict[str, Any]] = []
    for edge in edges:
        src_key = str(edge.get("source") or edge.get("from") or "")
        tgt_key = str(edge.get("target") or edge.get("to") or "")
        if src_key not in node_by_key or tgt_key not in node_by_key:
            continue

        raw_type = str(edge.get("edge_type") or edge.get("type") or edge.get("kind") or "INFERRED").upper()
        conf = _EDGE_CONFIDENCE.get(raw_type, 0.6)
        relation = str(edge.get("relation") or edge.get("label") or "related_to").strip().lower()

        resolved_edges.append(
            {
                "source_canonical_id": node_by_key[src_key]["canonical_id"],
                "target_canonical_id": node_by_key[tgt_key]["canonical_id"],
                "relation": relation,
                "confidence": conf,
                "edge_type": raw_type,
                "provenance": [
                    {
                        "file_id": db_id,
                        "chunk_idx": -1,
                        "context": f"Graphify edge type={raw_type}",
                        "extractor": "graphify",
                    }
                ],
                "temporal": {"valid_from": None, "valid_to": None},
            }
        )

    return {
        "resolved_nodes": resolved_nodes,
        "resolved_edges": resolved_edges,
    }


def _canonical_to_file_graph_entities(mapped: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities = []
    rels = []

    seen = set()
    id_to_label = {}
    for node in mapped.get("resolved_nodes", []):
        cid = node.get("canonical_id")
        label = node.get("label")
        id_to_label[cid] = label
        if cid in seen:
            continue
        seen.add(cid)
        entities.append(
            {
                "text": label,
                "type": node.get("entity_type", "entity"),
                "label": "ENTITY",
                "chunk_idx": -1,
                "chunk_preview": "Graphify mapped node",
            }
        )

    for edge in mapped.get("resolved_edges", []):
        src = id_to_label.get(edge.get("source_canonical_id"))
        tgt = id_to_label.get(edge.get("target_canonical_id"))
        if not src or not tgt:
            continue
        rels.append(
            {
                "source": src,
                "target": tgt,
                "relation": edge.get("relation", "related_to"),
                "context": f"Graphify {edge.get('edge_type', 'INFERRED')}",
                "chunk_idx": -1,
            }
        )

    return entities, rels


def merge_into_canonical(db_id: str, mapped: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    graph_builder = GraphBuilder()
    wiki_builder = WikiBuilder()

    upsert = graph_builder.upsert_canonical_graph(
        file_id=db_id,
        resolved_nodes=mapped.get("resolved_nodes", []),
        resolved_edges=mapped.get("resolved_edges", []),
    )

    touched_ids = sorted({n.get("canonical_id") for n in mapped.get("resolved_nodes", []) if n.get("canonical_id")})
    canonical_graph = graph_builder.get_canonical_graph()
    wiki_report = wiki_builder.build_pages_for_nodes(db_id, touched_ids, canonical_graph)

    # Also persist a file-scoped graph so existing /graph endpoints can include DB-derived graph.
    entities, relationships = _canonical_to_file_graph_entities(mapped)
    file_graph = graph_builder.build_graph(db_id, entities, relationships)

    return {
        "upsert": upsert,
        "wiki_report": wiki_report,
        "file_graph_stats": file_graph.get("stats", {}),
        "merged_at": time.time(),
    }
