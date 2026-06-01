"""Step 7 — Semantic Learning Layer.

WHY: enterprise semantics evolve; the platform must learn meaning progressively
     instead of treating every ingestion as cold-start.
PRODUCES: a persistent semantic memory (entity embeddings, co-occurrence stats,
          term clusters) + adaptive confidence priors that update over time.
ORDERING: after extraction (needs entities) and before ontology/canonicalization,
          which consume its priors and cluster suggestions.
ENABLES: better merge priors (11), ontology suggestions (10), drift detection (8).
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from ..contracts.embedding import cosine, embed
from ..storage.jsonstore import read_json, write_json

_MEMORY_PATH = settings.dir("semantic_memory") / "memory.json"


def _load() -> dict:
    return read_json(_MEMORY_PATH, {"terms": {}, "cooccurrence": {}, "updated_at": None})


def _save(mem: dict) -> None:
    mem["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(_MEMORY_PATH, mem)


def learn(extraction: dict) -> dict:
    """Update semantic memory from one source's extraction; return learning report."""
    mem = _load()
    terms = mem["terms"]
    cooc = mem["cooccurrence"]

    new_terms, reinforced = 0, 0
    for ent in extraction["entities"]:
        key = ent["text"].lower()
        if key not in terms:
            terms[key] = {
                "text": ent["text"],
                "entity_type": ent["entity_type"],
                "embedding": embed(ent["text"]),
                "observations": 0,
                "prior": 0.5,
            }
            new_terms += 1
        else:
            reinforced += 1
        rec = terms[key]
        rec["observations"] += 1
        # Adaptive prior: more observations -> higher confidence prior (saturating).
        rec["prior"] = round(min(0.95, 0.5 + 0.05 * rec["observations"]), 4)

    # Co-occurrence statistics drive future relation priors.
    for rel in extraction["relationships"]:
        pair = " :: ".join(sorted([rel["source"].lower(), rel["target"].lower()]))
        cooc[pair] = cooc.get(pair, 0) + 1

    _save(mem)
    return {
        "source_id": extraction["source_id"],
        "new_terms": new_terms,
        "reinforced_terms": reinforced,
        "memory_size": len(terms),
        "distinct_pairs": len(cooc),
    }


def prior_for(term: str) -> float:
    rec = _load()["terms"].get(term.lower())
    return rec["prior"] if rec else 0.5


def nearest_terms(term: str, top_k: int = 5) -> list[dict]:
    """Semantic clustering helper: nearest known terms by embedding cosine."""
    mem = _load()
    q = embed(term)
    scored = [
        {"text": r["text"], "type": r["entity_type"], "similarity": round(cosine(q, r["embedding"]), 4)}
        for r in mem["terms"].values()
    ]
    scored.sort(key=lambda x: -x["similarity"])
    return scored[:top_k]
