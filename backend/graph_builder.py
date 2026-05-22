import json
import os
import logging
from typing import List, Dict, Optional, Callable
import re

import numpy as np

logger = logging.getLogger(__name__)

GRAPH_DIR = "data/graphs"
os.makedirs(GRAPH_DIR, exist_ok=True)
CANONICAL_GRAPH_PATH = "data/canonical_graph.json"


class GraphBuilder:
    RELATION_PRIOR = {
        "has_revenue": 1.0,
        "owns": 0.9,
        "employs": 0.85,
        "located_in": 0.75,
        "occurred_at": 0.7,
        "related_to": 0.55,
    }

    def __init__(self):
        # Cache node label embeddings to avoid recomputing on each query.
        self._label_embedding_cache: Dict[str, np.ndarray] = {}

    @staticmethod
    def _graph_stats(node_count: int, edge_count: int) -> Dict:
        if node_count <= 1:
            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "density": 0.0,
                "avg_degree": 0.0,
            }

        # Directed graph density: E / (N * (N - 1))
        density = edge_count / (node_count * (node_count - 1))
        avg_degree = (2 * edge_count) / node_count if node_count else 0.0
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": round(density, 6),
            "avg_degree": round(avg_degree, 4),
        }

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def _embed_label(self, label: str, embed_fn: Callable[[str], np.ndarray]) -> np.ndarray:
        cached = self._label_embedding_cache.get(label)
        if cached is not None:
            return cached

        vec = np.asarray(embed_fn(label), dtype=np.float32)
        self._label_embedding_cache[label] = vec
        return vec

    @staticmethod
    def _tokenize(text: str) -> set:
        return set(re.findall(r"[a-z0-9_]+", (text or "").lower()))

    @staticmethod
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def _node_index_and_degree(self, graph: Dict) -> (Dict[str, Dict], Dict[str, int]):
        node_idx = {n["id"]: n for n in graph.get("nodes", []) if "id" in n}
        degree = {nid: 0 for nid in node_idx.keys()}
        for e in graph.get("edges", []):
            s = e.get("source")
            t = e.get("target")
            if s in degree:
                degree[s] += 1
            if t in degree:
                degree[t] += 1
        return node_idx, degree

    def _score_edge(
        self,
        edge: Dict,
        query_tokens: set,
        node_idx: Dict[str, Dict],
        degree_map: Dict[str, int],
        node_scores: Optional[Dict[str, Dict]] = None,
    ) -> Dict:
        src = edge.get("source")
        tgt = edge.get("target")
        src_label = (node_idx.get(src, {}) or {}).get("label", "")
        tgt_label = (node_idx.get(tgt, {}) or {}).get("label", "")

        edge_tokens = self._tokenize(f"{src_label} {tgt_label} {edge.get('relation', '')} {edge.get('context', '')}")
        lexical_overlap = len(query_tokens & edge_tokens) / max(1, len(query_tokens))
        lexical_score = self._clamp01(lexical_overlap)

        rel_type = edge.get("relation", "related_to")
        relation_prior = self.RELATION_PRIOR.get(rel_type, 0.5)

        max_degree = max(1, max(degree_map.values()) if degree_map else 1)
        src_deg = degree_map.get(src, 0) / max_degree
        tgt_deg = degree_map.get(tgt, 0) / max_degree
        structural_score = self._clamp01((src_deg + tgt_deg) / 2.0)

        semantic_score = 0.0
        if node_scores:
            # node_scores values are cosine in [-1,1] -> normalize to [0,1]
            s_raw = node_scores.get(src, {}).get("score", 0.0)
            t_raw = node_scores.get(tgt, {}).get("score", 0.0)
            semantic_score = self._clamp01(((s_raw + t_raw) / 2.0 + 1.0) / 2.0)

        # Weighted relevance with deterministic breakdown for explainability.
        relevance = (
            0.45 * semantic_score
            + 0.30 * lexical_score
            + 0.15 * relation_prior
            + 0.10 * structural_score
        )

        return {
            "relevance_score": round(self._clamp01(relevance), 4),
            "score_breakdown": {
                "semantic": round(semantic_score, 4),
                "lexical": round(lexical_score, 4),
                "relation_prior": round(relation_prior, 4),
                "structural": round(structural_score, 4),
            },
        }

    def build_graph(self, file_id: str, entities: List[Dict], relationships: List[Dict]) -> Dict:
        node_ids: Dict[str, str] = {}
        nodes: List[Dict] = []
        edges: List[Dict] = []

        for ent in entities:
            nid = f"n{len(nodes)}"
            node_ids[ent["text"]] = nid
            nodes.append({
                "id": nid,
                "label": ent["text"],
                "type": ent.get("type", "entity"),
                "entity_type": ent.get("label", "ENTITY"),
                "confidence": ent.get("eda_confidence", ent.get("confidence", 0.0)),
                "chunk_idx": ent.get("chunk_idx"),
                "chunk_occurrences": ent.get("chunk_occurrences", []),
                "chunk_preview": ent.get("chunk_preview", ""),
            })

        for rel in relationships:
            src = node_ids.get(rel["source"])
            tgt = node_ids.get(rel["target"])
            if src and tgt and src != tgt:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "relation": rel["relation"],
                    "confidence": rel.get("eda_confidence", rel.get("confidence", 0.0)),
                    "context": rel.get("context", "")[:100],
                    "chunk_idx": rel.get("chunk_idx"),
                    "chunk_preview": rel.get("chunk_preview", ""),
                })

        graph = {
            "file_id": file_id,
            "nodes": nodes,
            "edges": edges,
            "stats": self._graph_stats(len(nodes), len(edges)),
            "chunk_grounded": True,
        }

        with open(f"{GRAPH_DIR}/{file_id}_graph.json", "w") as f:
            json.dump(graph, f)

        return graph

    def _load_canonical_graph(self) -> Dict:
        if not os.path.exists(CANONICAL_GRAPH_PATH):
            return {
                "nodes": [],
                "edges": [],
                "stats": self._graph_stats(0, 0),
                "updated_at": None,
            }
        try:
            with open(CANONICAL_GRAPH_PATH) as f:
                graph = json.load(f)
            graph.setdefault("nodes", [])
            graph.setdefault("edges", [])
            graph.setdefault("stats", self._graph_stats(len(graph["nodes"]), len(graph["edges"])))
            return graph
        except Exception as ex:
            logger.error("Failed to load canonical graph: %s", ex)
            return {
                "nodes": [],
                "edges": [],
                "stats": self._graph_stats(0, 0),
                "updated_at": None,
            }

    def _save_canonical_graph(self, graph: Dict):
        graph["stats"] = self._graph_stats(len(graph.get("nodes", [])), len(graph.get("edges", [])))
        with open(CANONICAL_GRAPH_PATH, "w") as f:
            json.dump(graph, f)

    @staticmethod
    def _edge_key(source_id: str, relation: str, target_id: str) -> str:
        return f"{source_id}|{relation}|{target_id}"

    def upsert_canonical_graph(self, file_id: str, resolved_nodes: List[Dict], resolved_edges: List[Dict]) -> Dict:
        graph = self._load_canonical_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        node_idx = {n.get("canonical_id"): n for n in nodes if n.get("canonical_id")}
        edge_idx = {
            self._edge_key(e.get("source_canonical_id", ""), e.get("relation", "related_to"), e.get("target_canonical_id", "")): e
            for e in edges
            if e.get("source_canonical_id") and e.get("target_canonical_id")
        }

        nodes_created = 0
        nodes_updated = 0
        for node in resolved_nodes:
            cid = node.get("canonical_id")
            if not cid:
                continue

            existing = node_idx.get(cid)
            if not existing:
                new_node = dict(node)
                new_node.setdefault("source_files", [file_id])
                nodes.append(new_node)
                node_idx[cid] = new_node
                nodes_created += 1
                continue

            # Merge aliases, provenance, and source file backlinks.
            existing_aliases = set(existing.get("aliases", []))
            for alias in node.get("aliases", []):
                if alias and alias not in existing_aliases:
                    existing.setdefault("aliases", []).append(alias)
                    existing_aliases.add(alias)

            existing.setdefault("provenance", []).extend(node.get("provenance", []))
            source_files = set(existing.get("source_files", []))
            source_files.add(file_id)
            existing["source_files"] = sorted(source_files)
            existing["confidence"] = round(max(float(existing.get("confidence", 0.0)), float(node.get("confidence", 0.0))), 4)
            nodes_updated += 1

        edges_created = 0
        edges_updated = 0
        for edge in resolved_edges:
            src = edge.get("source_canonical_id")
            tgt = edge.get("target_canonical_id")
            relation = edge.get("relation", "related_to")
            if not src or not tgt or src == tgt:
                continue

            key = self._edge_key(src, relation, tgt)
            existing = edge_idx.get(key)
            if not existing:
                new_edge = dict(edge)
                new_edge["edge_key"] = key
                new_edge.setdefault("source_files", [file_id])
                edges.append(new_edge)
                edge_idx[key] = new_edge
                edges_created += 1
                continue

            existing.setdefault("provenance", []).extend(edge.get("provenance", []))
            source_files = set(existing.get("source_files", []))
            source_files.add(file_id)
            existing["source_files"] = sorted(source_files)
            existing["confidence"] = round(max(float(existing.get("confidence", 0.0)), float(edge.get("confidence", 0.0))), 4)
            edges_updated += 1

        graph["nodes"] = nodes
        graph["edges"] = edges
        self._save_canonical_graph(graph)

        return {
            "nodes_created": nodes_created,
            "nodes_updated": nodes_updated,
            "edges_created": edges_created,
            "edges_updated": edges_updated,
            "stats": graph.get("stats", {}),
        }

    def suppress_canonical_relation(self, edge_key: str, reason: Optional[str] = None, decided_by: Optional[str] = None) -> Dict:
        graph = self._load_canonical_graph()
        for edge in graph.get("edges", []):
            current_key = edge.get("edge_key") or self._edge_key(
                edge.get("source_canonical_id", ""),
                edge.get("relation", "related_to"),
                edge.get("target_canonical_id", ""),
            )
            edge["edge_key"] = current_key
            if current_key != edge_key:
                continue

            edge["suppressed"] = True
            edge["suppressed_meta"] = {
                "reason": reason or "manual_review",
                "decided_by": decided_by or "repair_api",
                "suppressed_at": time.time(),
            }
            self._save_canonical_graph(graph)
            return {"ok": True, "edge_key": edge_key, "suppressed": True}

        return {"ok": False, "error": "edge_not_found", "edge_key": edge_key}

    def restore_canonical_relation(self, edge_key: str, decided_by: Optional[str] = None) -> Dict:
        graph = self._load_canonical_graph()
        for edge in graph.get("edges", []):
            current_key = edge.get("edge_key") or self._edge_key(
                edge.get("source_canonical_id", ""),
                edge.get("relation", "related_to"),
                edge.get("target_canonical_id", ""),
            )
            edge["edge_key"] = current_key
            if current_key != edge_key:
                continue

            edge["suppressed"] = False
            edge["suppressed_meta"] = {
                "reason": "restored",
                "decided_by": decided_by or "repair_api",
                "restored_at": time.time(),
            }
            self._save_canonical_graph(graph)
            return {"ok": True, "edge_key": edge_key, "suppressed": False}

        return {"ok": False, "error": "edge_not_found", "edge_key": edge_key}

    def canonical_graph_metrics(self) -> Dict:
        graph = self._load_canonical_graph()
        edges = graph.get("edges", [])
        nodes = graph.get("nodes", [])
        suppressed = [e for e in edges if e.get("suppressed")]
        active_edges = [e for e in edges if not e.get("suppressed")]

        low_conf = 0
        medium_conf = 0
        high_conf = 0
        contradictory = 0
        for edge in active_edges:
            conf = float(edge.get("confidence", 0.0) or 0.0)
            if conf < 0.5:
                low_conf += 1
            elif conf < 0.8:
                medium_conf += 1
            else:
                high_conf += 1

            relation = str(edge.get("relation", "")).lower()
            if "contradict" in relation or "ambiguous" in relation:
                contradictory += 1

        high_risk_edge_ratio = low_conf / max(1, len(active_edges))
        contradiction_ratio = contradictory / max(1, len(active_edges))

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "active_edge_count": len(active_edges),
            "suppressed_edge_count": len(suppressed),
            "suppressed_ratio_pct": round((len(suppressed) / max(1, len(edges))) * 100, 2),
            "high_risk_edge_ratio": round(high_risk_edge_ratio, 4),
            "contradiction_ratio": round(contradiction_ratio, 4),
            "edge_confidence_distribution": {
                "low": low_conf,
                "medium": medium_conf,
                "high": high_conf,
            },
            "stats": self._graph_stats(len(nodes), len(active_edges)),
        }

    def get_canonical_graph(self, file_ids: Optional[List[str]] = None) -> Dict:
        graph = self._load_canonical_graph()
        if not file_ids:
            nodes = [
                {
                    **n,
                    "id": n.get("canonical_id"),
                    "label": n.get("label", ""),
                }
                for n in graph.get("nodes", [])
                if n.get("canonical_id")
            ]
            edges = [
                {
                    **e,
                    "source": e.get("source_canonical_id"),
                    "target": e.get("target_canonical_id"),
                }
                for e in graph.get("edges", [])
                if e.get("source_canonical_id") and e.get("target_canonical_id") and not e.get("suppressed")
            ]
            return {
                "nodes": nodes,
                "edges": edges,
                "stats": self._graph_stats(len(nodes), len(edges)),
            }

        fid_set = set(file_ids)
        nodes = []
        keep_ids = set()
        for n in graph.get("nodes", []):
            source_files = set(n.get("source_files", []))
            if source_files & fid_set:
                keep_ids.add(n.get("canonical_id"))
                nodes.append({
                    **n,
                    "id": n.get("canonical_id"),
                    "label": n.get("label", ""),
                })

        edges = []
        for e in graph.get("edges", []):
            src = e.get("source_canonical_id")
            tgt = e.get("target_canonical_id")
            source_files = set(e.get("source_files", []))
            if src in keep_ids and tgt in keep_ids and source_files & fid_set and not e.get("suppressed"):
                edges.append({
                    **e,
                    "source": src,
                    "target": tgt,
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": self._graph_stats(len(nodes), len(edges)),
        }

    def get_graph(self, file_ids: Optional[List[str]] = None) -> Dict:
        all_nodes: List[Dict] = []
        all_edges: List[Dict] = []

        if not os.path.exists(GRAPH_DIR):
            return {"nodes": [], "edges": [], "stats": self._graph_stats(0, 0)}

        for fname in os.listdir(GRAPH_DIR):
            if not fname.endswith("_graph.json"):
                continue
            fid = fname.replace("_graph.json", "")
            if file_ids and fid not in file_ids:
                continue
            try:
                with open(os.path.join(GRAPH_DIR, fname)) as f:
                    g = json.load(f)
                prefix = fid[:8]
                for node in g.get("nodes", []):
                    n = dict(node)
                    n["id"] = f"{prefix}_{n['id']}"
                    n["file_id"] = fid
                    all_nodes.append(n)
                for edge in g.get("edges", []):
                    e = dict(edge)
                    e["source"] = f"{prefix}_{e['source']}"
                    e["target"] = f"{prefix}_{e['target']}"
                    e["file_id"] = fid
                    all_edges.append(e)
            except Exception as ex:
                logger.error(f"Failed to load graph {fname}: {ex}")

        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "stats": self._graph_stats(len(all_nodes), len(all_edges)),
        }

    def get_relations(self, entity_texts: List[str], file_ids: Optional[List[str]] = None) -> List[Dict]:
        graph = self.get_graph(file_ids)
        node_idx, degree_map = self._node_index_and_degree(graph)
        query_tokens = self._tokenize(" ".join(entity_texts))
        matching = {
            n["id"]
            for n in graph["nodes"]
            if any(et.lower() in n["label"].lower() for et in entity_texts)
        }
        rels = []
        for e in graph["edges"]:
            if e["source"] not in matching and e["target"] not in matching:
                continue
            scored = self._score_edge(e, query_tokens, node_idx, degree_map, node_scores=None)
            rels.append({
                **e,
                **scored,
                "semantic_match": False,
            })

        rels.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        return rels[:20]

    def get_canonical_relations(self, entity_texts: List[str], file_ids: Optional[List[str]] = None) -> List[Dict]:
        graph = self.get_canonical_graph(file_ids)
        node_idx, degree_map = self._node_index_and_degree(graph)
        query_tokens = self._tokenize(" ".join(entity_texts))
        matching = {
            n["id"]
            for n in graph["nodes"]
            if any(et.lower() in (n.get("label", "")).lower() for et in entity_texts)
        }
        rels = []
        for e in graph["edges"]:
            if e.get("source") not in matching and e.get("target") not in matching:
                continue
            scored = self._score_edge(e, query_tokens, node_idx, degree_map, node_scores=None)
            rels.append({
                **e,
                **scored,
                "semantic_match": False,
                "graph_scope": "canonical",
            })

        rels.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        return rels[:20]

    def get_relations_semantic(
        self,
        query: str,
        embed_fn: Callable[[str], np.ndarray],
        file_ids: Optional[List[str]] = None,
        top_k_nodes: int = 8,
        max_relations: int = 25,
    ) -> List[Dict]:
        graph = self.get_graph(file_ids)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not nodes or not edges:
            return []

        node_idx, degree_map = self._node_index_and_degree(graph)
        query_tokens = self._tokenize(query)

        try:
            q_vec = np.asarray(embed_fn(query), dtype=np.float32)
        except Exception as ex:
            logger.warning("Semantic graph traversal failed to embed query: %s", ex)
            return []

        if q_vec.ndim != 1 or np.linalg.norm(q_vec) == 0:
            return []

        node_scores: Dict[str, Dict] = {}
        for n in nodes:
            nid = n.get("id")
            label = (n.get("label") or "").strip()
            if not nid or not label:
                continue
            try:
                n_vec = self._embed_label(label, embed_fn)
                score = self._cosine(q_vec, n_vec)
                node_scores[nid] = {"score": score, "label": label}
            except Exception:
                continue

        if not node_scores:
            return []

        ranked_ids = sorted(node_scores.keys(), key=lambda nid: node_scores[nid]["score"], reverse=True)

        # Keep at least 3 nodes even with low scores; otherwise require modest semantic similarity.
        selected_ids: List[str] = []
        for nid in ranked_ids:
            if len(selected_ids) >= top_k_nodes:
                break
            score = node_scores[nid]["score"]
            if len(selected_ids) < 3 or score >= 0.15:
                selected_ids.append(nid)

        selected = set(selected_ids)
        if not selected:
            return []

        ranked_edges: List[Dict] = []
        for e in edges:
            src = e.get("source")
            tgt = e.get("target")
            if src not in selected and tgt not in selected:
                continue

            src_score = node_scores.get(src, {}).get("score", 0.0)
            tgt_score = node_scores.get(tgt, {}).get("score", 0.0)
            scored = self._score_edge(e, query_tokens, node_idx, degree_map, node_scores=node_scores)

            matched_nodes = []
            if src in selected:
                matched_nodes.append({"id": src, "label": node_scores.get(src, {}).get("label", "")})
            if tgt in selected:
                matched_nodes.append({"id": tgt, "label": node_scores.get(tgt, {}).get("label", "")})

            ranked_edges.append({
                **e,
                "semantic_match": True,
                **scored,
                "node_similarity_raw": {
                    "source": round(src_score, 4),
                    "target": round(tgt_score, 4),
                },
                "matched_nodes": matched_nodes,
            })

        ranked_edges.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        return ranked_edges[:max_relations]

    def get_canonical_relations_semantic(
        self,
        query: str,
        embed_fn: Callable[[str], np.ndarray],
        file_ids: Optional[List[str]] = None,
        top_k_nodes: int = 8,
        max_relations: int = 25,
    ) -> List[Dict]:
        graph = self.get_canonical_graph(file_ids)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not nodes or not edges:
            return []

        node_idx, degree_map = self._node_index_and_degree(graph)
        query_tokens = self._tokenize(query)

        try:
            q_vec = np.asarray(embed_fn(query), dtype=np.float32)
        except Exception as ex:
            logger.warning("Semantic canonical graph traversal failed to embed query: %s", ex)
            return []

        if q_vec.ndim != 1 or np.linalg.norm(q_vec) == 0:
            return []

        node_scores: Dict[str, Dict] = {}
        for n in nodes:
            nid = n.get("id")
            label = (n.get("label") or "").strip()
            if not nid or not label:
                continue
            try:
                n_vec = self._embed_label(label, embed_fn)
                score = self._cosine(q_vec, n_vec)
                node_scores[nid] = {"score": score, "label": label}
            except Exception:
                continue

        if not node_scores:
            return []

        ranked_ids = sorted(node_scores.keys(), key=lambda nid: node_scores[nid]["score"], reverse=True)

        selected_ids: List[str] = []
        for nid in ranked_ids:
            if len(selected_ids) >= top_k_nodes:
                break
            score = node_scores[nid]["score"]
            if len(selected_ids) < 3 or score >= 0.15:
                selected_ids.append(nid)

        selected = set(selected_ids)
        if not selected:
            return []

        ranked_edges: List[Dict] = []
        for e in edges:
            src = e.get("source")
            tgt = e.get("target")
            if src not in selected and tgt not in selected:
                continue

            src_score = node_scores.get(src, {}).get("score", 0.0)
            tgt_score = node_scores.get(tgt, {}).get("score", 0.0)
            scored = self._score_edge(e, query_tokens, node_idx, degree_map, node_scores=node_scores)

            matched_nodes = []
            if src in selected:
                matched_nodes.append({"id": src, "label": node_scores.get(src, {}).get("label", "")})
            if tgt in selected:
                matched_nodes.append({"id": tgt, "label": node_scores.get(tgt, {}).get("label", "")})

            ranked_edges.append({
                **e,
                "semantic_match": True,
                "graph_scope": "canonical",
                **scored,
                "node_similarity_raw": {
                    "source": round(src_score, 4),
                    "target": round(tgt_score, 4),
                },
                "matched_nodes": matched_nodes,
            })

        ranked_edges.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        return ranked_edges[:max_relations]
