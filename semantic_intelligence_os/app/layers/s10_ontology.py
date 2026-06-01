"""Step 10 — Ontology & Semantic Governance Layer (the pre-insertion gate).

WHY: relationships must be validated against enterprise semantics BEFORE entering the
     graph — this is what prevents hallucinated/invalid edges from polluting trust.
PRODUCES: a declarative ontology (taxonomy + relationship constraints + inheritance)
          and per-candidate accept/review/reject verdicts.
ORDERING: after validation, before canonicalization/graph — it gates insertion.
ENABLES: confidence-weighted, ontology-valid graph construction (12) and consistency (13).

Honors GovernanceMode: observe_only annotates verdicts but never blocks; enforce
routes rejects/reviews so they are excluded from auto-insertion.
"""
from __future__ import annotations

from ..config import GovernanceMode, settings
from ..storage.jsonstore import read_json, write_json

_ONTOLOGY_PATH = settings.dir("governance") / "ontology.json"

# Default seed ontology. Extensible / evolvable via update_ontology().
_DEFAULT_ONTOLOGY = {
    "version": 1,
    "taxonomy": {
        "organization": {"parent": "agent"},
        "person": {"parent": "agent"},
        "location": {"parent": "place"},
        "monetary": {"parent": "value"},
        "temporal": {"parent": "value"},
        "concept": {"parent": None},
        "agent": {"parent": None},
        "place": {"parent": None},
        "value": {"parent": None},
    },
    # Allowed (source_type, target_type) per predicate.
    "relationship_constraints": {
        "has_revenue": [["organization", "monetary"]],
        "employs": [["organization", "person"]],
        "owns": [["organization", "organization"], ["person", "organization"]],
        "located_in": [["organization", "location"], ["person", "location"]],
        "occurred_at": [["concept", "temporal"], ["organization", "temporal"]],
        "related_to": "ANY",
    },
}


def load_ontology() -> dict:
    onto = read_json(_ONTOLOGY_PATH, None)
    if onto is None:
        write_json(_ONTOLOGY_PATH, _DEFAULT_ONTOLOGY)
        return dict(_DEFAULT_ONTOLOGY)
    return onto


def allowed_predicates() -> set[str]:
    return set(load_ontology()["relationship_constraints"].keys())


def update_ontology(predicate: str, allowed_pairs: list[list[str]]) -> dict:
    """Ontology evolution: register/extend a predicate's allowed type pairs."""
    onto = load_ontology()
    onto["relationship_constraints"][predicate] = allowed_pairs
    onto["version"] += 1
    write_json(_ONTOLOGY_PATH, onto)
    return onto


def _is_a(onto: dict, t: str, ancestor: str) -> bool:
    seen = set()
    while t and t not in seen:
        if t == ancestor:
            return True
        seen.add(t)
        t = onto["taxonomy"].get(t, {}).get("parent")
    return False


def _pair_ok(onto: dict, constraint, s_type: str, t_type: str) -> bool:
    if constraint == "ANY":
        return True
    for allowed_s, allowed_t in constraint:
        if _is_a(onto, s_type, allowed_s) and _is_a(onto, t_type, allowed_t):
            return True
    return False


def govern(extraction: dict, validation: dict) -> dict:
    """Validate every relationship against the ontology; produce verdicts + gated set."""
    onto = load_ontology()
    constraints = onto["relationship_constraints"]
    mode = settings.governance_mode
    known_types = set(onto["taxonomy"].keys())

    verdicts, accepted, review_queue = [], [], []
    for rel in extraction["relationships"]:
        s_t, t_t, pred = rel["source_type"], rel["target_type"], rel["relation"]
        constraint = constraints.get(pred)
        if constraint is None:
            action, reason = "review_required", f"predicate '{pred}' not in ontology"
        elif s_t not in known_types or t_t not in known_types:
            action, reason = "review_required", "unknown entity type"
        elif _pair_ok(onto, constraint, s_t, t_t):
            action, reason = "auto_accept", "ontology-valid"
        else:
            action, reason = "reject", f"({s_t})-[{pred}]->({t_t}) violates constraints"

        verdict = {**rel, "governance": {"action": action, "reason": reason, "mode": mode.value}}
        verdicts.append(verdict)

        if action == "auto_accept":
            accepted.append(verdict)
        elif action == "review_required":
            review_queue.append(verdict)
            # In observe_only we still let reviewables through downstream (annotated).
            if mode == GovernanceMode.OBSERVE_ONLY:
                accepted.append(verdict)
        else:  # reject
            if mode == GovernanceMode.OBSERVE_ONLY:
                accepted.append(verdict)  # annotate-only, do not block

    violations = sum(1 for v in verdicts if v["governance"]["action"] == "reject")
    total = max(1, len(verdicts))
    return {
        "source_id": extraction["source_id"],
        "ontology_version": onto["version"],
        "mode": mode.value,
        "verdicts_summary": {
            "auto_accept": sum(1 for v in verdicts if v["governance"]["action"] == "auto_accept"),
            "review_required": len(review_queue),
            "reject": violations,
        },
        "ontology_consistency": round(1 - violations / total, 4),
        "accepted_relationships": accepted,
        "review_queue": review_queue,
    }
