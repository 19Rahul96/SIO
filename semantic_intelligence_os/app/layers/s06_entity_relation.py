"""Step 6 — Entity + Relationship Extraction (chunk-grounded, ontology-aware).

WHY: entities/relations are the atoms of the knowledge graph.
PRODUCES: entities and relationships, each grounded to the chunk that produced them,
          with a confidence + extraction-method observability trace.
ORDERING: after metadata (so column semantics can hint entity types) and chunking.
ENABLES: semantic learning (7), canonicalization (11), and graph construction (12).

Primary path: spaCy NER. Fallback: regex. Relations: sentence co-occurrence with a
lexical predicate classifier, optionally constrained to ontology-allowed predicates.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..contracts.audit import make_audit

_MONEY = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|INR)\b")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_PROPER = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b")

# Lexical predicate cues -> relation label.
_PREDICATES = {
    "has_revenue": ["revenue", "earned", "income", "sales of"],
    "employs": ["employs", "hired", "staff", "employees"],
    "owns": ["owns", "acquired", "subsidiary", "parent of"],
    "located_in": ["located in", "based in", "headquartered", "in the city"],
    "occurred_at": ["on", "during", "dated"],
}


@lru_cache(maxsize=1)
def _nlp():
    try:  # pragma: no cover
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def _ner(text: str) -> list[dict]:
    nlp = _nlp()
    out = []
    if nlp is not None:  # pragma: no cover
        for ent in nlp(text[:100000]).ents:
            out.append({"text": ent.text.strip(), "label": ent.label_})
        return out
    # Regex fallback with lightweight type heuristics.
    spans = []
    for m in _MONEY.finditer(text):
        out.append({"text": m.group(0), "label": "MONEY"})
        spans.append((m.start(), m.end()))
    for m in _DATE.finditer(text):
        out.append({"text": m.group(0), "label": "DATE"})
        spans.append((m.start(), m.end()))
    for m in _PROPER.finditer(text):
        # Skip proper-noun matches overlapping an already-tagged money/date span.
        if any(s <= m.start() < e for s, e in spans):
            continue
        out.append({"text": m.group(1), "label": _guess_proper_label(m.group(1))})
    return out


_ORG_SUFFIX = re.compile(r"\b(corp|corporation|inc|incorporated|ltd|llc|plc|gmbh|company|co)\b", re.I)
_LOCATION_GAZ = {"berlin", "new york", "london", "paris", "tokyo", "san francisco", "mumbai"}


def _guess_proper_label(text: str) -> str:
    """Heuristic NER labels for the no-spaCy path: ORG by suffix, GPE by gazetteer,
    PERSON for two-token capitalized names, else generic ENTITY."""
    low = text.lower()
    if _ORG_SUFFIX.search(low):
        return "ORG"
    if low in _LOCATION_GAZ:
        return "GPE"
    tokens = text.split()
    if len(tokens) == 2 and all(t[:1].isupper() for t in tokens):
        return "PERSON"
    return "ENTITY"


_LABEL_TO_TYPE = {
    "ORG": "organization",
    "PERSON": "person",
    "GPE": "location",
    "LOC": "location",
    "MONEY": "monetary",
    "DATE": "temporal",
    "ENTITY": "concept",
}


def _classify_relation(sentence: str, allowed: set[str] | None) -> str:
    low = sentence.lower()
    for rel, cues in _PREDICATES.items():
        if allowed and rel not in allowed:
            continue
        if any(c in low for c in cues):
            return rel
    return "related_to"


def extract(chunked: dict, ontology_predicates: set[str] | None = None) -> dict:
    source_id = chunked["source_id"]
    entities: dict[tuple, dict] = {}
    relationships: list[dict] = []
    method = "spacy" if _nlp() is not None else "regex"

    for chunk in chunked["chunks"]:
        text = chunk["text"]
        found = _ner(text)
        # Dedup entities per (text, label); track chunk grounding + frequency.
        local = []
        for e in found:
            txt = e["text"]
            if len(txt) < 2:
                continue
            key = (txt.lower(), e["label"])
            etype = _LABEL_TO_TYPE.get(e["label"], "concept")
            if key not in entities:
                entities[key] = {
                    "text": txt,
                    "label": e["label"],
                    "entity_type": etype,
                    "frequency": 0,
                    "chunk_idxs": [],
                    "chunk_preview": text[:160],
                }
            entities[key]["frequency"] += 1
            if chunk["idx"] not in entities[key]["chunk_idxs"]:
                entities[key]["chunk_idxs"].append(chunk["idx"])
            local.append((txt, etype))

        # Sentence-level pairwise relations.
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            present = [(t, ty) for (t, ty) in local if t in sentence]
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    if len(relationships) >= 800:
                        break
                    rel = _classify_relation(sentence, ontology_predicates)
                    relationships.append(
                        {
                            "source": present[i][0],
                            "source_type": present[i][1],
                            "target": present[j][0],
                            "target_type": present[j][1],
                            "relation": rel,
                            "chunk_idx": chunk["idx"],
                            "method": "lexical_cooccurrence",
                            "evidence_sentence": sentence[:200],
                        }
                    )

    entity_list = []
    for e in entities.values():
        # Confidence: frequency + label signal + length.
        freq_sig = min(1.0, e["frequency"] / 5.0)
        label_sig = 0.0 if e["entity_type"] == "concept" else 0.5
        len_sig = min(1.0, len(e["text"]) / 25.0)
        score = round(0.4 * freq_sig + 0.35 * label_sig + 0.25 * len_sig, 4)
        e["audit"] = make_audit(
            score=score,
            scorer="entity_confidence",
            stage="entity_extraction",
            evidence={"frequency": e["frequency"], "method": method},
            citations=[{"source_id": source_id, "chunk_idx": e["chunk_idxs"][0] if e["chunk_idxs"] else None}],
        )
        entity_list.append(e)

    return {
        "source_id": source_id,
        "extraction_method": method,
        "entities": entity_list,
        "relationships": relationships,
        "observability": {
            "entity_count": len(entity_list),
            "relationship_count": len(relationships),
            "ontology_constrained": ontology_predicates is not None,
        },
    }
