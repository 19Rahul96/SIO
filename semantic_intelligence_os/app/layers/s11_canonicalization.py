"""Step 11 — Canonicalization & Semantic Resolution.

WHY: the same real-world entity appears under many surface forms; the graph needs one
     canonical node per concept, with aliases preserved.
PRODUCES: canonical entity registry updates (merge/create), alias/synonym mapping, and
          a mapping from raw entity text -> canonical_id for edge rewriting.
ORDERING: after governance (only ontology-valid context) and before graph build.
ENABLES: a deduplicated, mergeable knowledge graph (12).

Resolution = exact-norm + lexical Jaccard + embedding cosine + type compatibility,
boosted by learned semantic priors (7). Mirrors proven merge/review thresholds.
"""
from __future__ import annotations

import hashlib
import re

from ..config import settings
from ..contracts.embedding import cosine, embed
from ..storage.jsonstore import read_json, write_json
from . import s07_semantic_learning as sl

_REGISTRY_PATH = settings.dir("canonical") / "registry.json"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def _canonical_id(entity_type: str, norm: str) -> str:
    return "c_" + hashlib.sha1(f"{entity_type}:{norm}".encode()).hexdigest()[:16]


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def _load_registry() -> dict:
    return read_json(_REGISTRY_PATH, {"nodes": {}, "merges": [], "pending_reviews": []})


def resolve(extraction: dict, governance: dict) -> dict:
    reg = _load_registry()
    nodes = reg["nodes"]
    text_to_canonical: dict[str, str] = {}
    created, merged, reviewed = 0, 0, 0

    for ent in extraction["entities"]:
        norm = _norm(ent["text"])
        if not norm:
            continue
        etype = ent["entity_type"]
        emb = embed(ent["text"])

        # Score against existing canonical nodes of compatible type.
        best_id, best_score = None, 0.0
        for cid, node in nodes.items():
            if node["entity_type"] != etype:
                continue
            exact = 1.0 if node["norm"] == norm else 0.0
            lex = _jaccard(norm, node["norm"])
            emb_sim = cosine(emb, node["embedding"])
            score = 0.45 * exact + 0.35 * lex + 0.20 * emb_sim
            # Learned-prior boost.
            score = min(1.0, score + 0.1 * (sl.prior_for(ent["text"]) - 0.5))
            if score > best_score:
                best_id, best_score = cid, score

        if best_id and best_score >= settings.merge_threshold:
            node = nodes[best_id]
            if ent["text"] not in node["aliases"]:
                node["aliases"].append(ent["text"])
            node["frequency"] += ent.get("frequency", 1)
            node["provenance"].append({"source_id": extraction["source_id"]})
            text_to_canonical[ent["text"]] = best_id
            reg["merges"].append({"into": best_id, "alias": ent["text"], "score": round(best_score, 4)})
            merged += 1
        else:
            cid = _canonical_id(etype, norm)
            if cid not in nodes:
                nodes[cid] = {
                    "canonical_id": cid,
                    "label": ent["text"],
                    "norm": norm,
                    "entity_type": etype,
                    "aliases": [ent["text"]],
                    "embedding": emb,
                    "frequency": ent.get("frequency", 1),
                    "confidence": ent["audit"]["confidence"]["score"],
                    "provenance": [{"source_id": extraction["source_id"]}],
                }
                created += 1
            text_to_canonical[ent["text"]] = cid
            # Borderline match -> queue for human review.
            if best_id and settings.review_threshold <= best_score < settings.merge_threshold:
                reg["pending_reviews"].append(
                    {"new": cid, "candidate": best_id, "score": round(best_score, 4)}
                )
                reviewed += 1

    write_json(_REGISTRY_PATH, reg)
    return {
        "source_id": extraction["source_id"],
        "text_to_canonical": text_to_canonical,
        "created": created,
        "merged": merged,
        "pending_review": reviewed,
        "registry_size": len(nodes),
    }
