import datetime as dt
import re
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|thousand))?", text.strip().lower()))


def _as_number(text: str) -> float:
    value = text.strip().lower().replace("$", "").replace(",", "")
    mult = 1.0
    if value.endswith("million"):
        mult = 1_000_000.0
        value = value.replace("million", "").strip()
    elif value.endswith("billion"):
        mult = 1_000_000_000.0
        value = value.replace("billion", "").strip()
    elif value.endswith("thousand"):
        mult = 1_000.0
        value = value.replace("thousand", "").strip()
    return float(value) * mult


def _extract_year(text: str) -> int:
    m = re.search(r"(19\d{2}|20\d{2}|21\d{2})", text)
    if not m:
        return -1
    return int(m.group(1))


def analyze_semantic_consistency(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ontology_violations: List[Dict[str, Any]] = []
    type_conflicts: List[Dict[str, Any]] = []
    contradictions: List[Dict[str, Any]] = []
    temporal_inconsistencies: List[Dict[str, Any]] = []
    numeric_anomalies: List[Dict[str, Any]] = []
    direction_issues: List[Dict[str, Any]] = []

    entity_types: Dict[str, Set[str]] = defaultdict(set)
    for ent in entities:
        text = str(ent.get("text") or "").strip().lower()
        typ = str(ent.get("type") or ent.get("label") or "entity").strip().lower()
        if text:
            entity_types[text].add(typ)

    for label, types in entity_types.items():
        if len(types) > 1:
            type_conflicts.append({"entity": label, "types": sorted(types)})

    current_year = dt.datetime.utcnow().year
    numeric_values: List[Tuple[str, float]] = []
    for ent in entities:
        text = str(ent.get("text") or "").strip()
        typ = str(ent.get("type") or ent.get("label") or "").lower()
        year = _extract_year(text)
        if typ in {"time", "date"} and year > 0 and (year < 1900 or year > current_year + 2):
            temporal_inconsistencies.append({"entity": text, "year": year, "reason": "year_out_of_range"})
        if _is_number(text):
            try:
                numeric_values.append((text, _as_number(text)))
            except Exception:
                pass

    if numeric_values:
        vals = [v for _, v in numeric_values]
        mean = sum(vals) / max(1, len(vals))
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals))
        std = var ** 0.5
        if std > 0:
            for text, value in numeric_values:
                z = abs(value - mean) / std
                if z >= 3.0:
                    numeric_anomalies.append({"entity": text, "value": round(value, 4), "z_score": round(z, 4)})

    relation_polarity: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for rel in relationships:
        source = str(rel.get("source") or "").strip().lower()
        target = str(rel.get("target") or "").strip().lower()
        relation = str(rel.get("relation") or "related_to").strip().lower()
        if not source or not target:
            continue
        relation_polarity[(source, target)].add(relation)

        if relation in {"located_in"}:
            stypes = entity_types.get(source, {"entity"})
            ttypes = entity_types.get(target, {"entity"})
            if "location" not in ttypes and "gpe" not in ttypes:
                direction_issues.append({
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "reason": "target_not_location_like",
                })
            if "location" in stypes and "organization" in ttypes:
                direction_issues.append({
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "reason": "likely_direction_reversed",
                })

        if relation in {"owns", "employs"} and source == target:
            ontology_violations.append({"source": source, "target": target, "relation": relation, "reason": "self_relation"})

    for (s, t), rels in relation_polarity.items():
        reverse_rels = relation_polarity.get((t, s), set())
        if "owns" in rels and "owns" in reverse_rels:
            contradictions.append({"source": s, "target": t, "reason": "mutual_ownership_cycle"})

    score_penalty = (
        len(ontology_violations)
        + len(type_conflicts)
        + len(contradictions)
        + len(temporal_inconsistencies)
        + len(numeric_anomalies)
        + len(direction_issues)
    )
    volume = max(1, len(entities) + len(relationships))
    consistency_score = max(0.0, min(1.0, 1.0 - (score_penalty / float(volume))))

    return {
        "ontology_violations": ontology_violations[:300],
        "invalid_entity_type_mappings": type_conflicts[:300],
        "semantic_contradictions": contradictions[:200],
        "temporal_inconsistencies": temporal_inconsistencies[:200],
        "numeric_anomalies": numeric_anomalies[:200],
        "relationship_direction_issues": direction_issues[:250],
        "consistency_score": round(consistency_score, 4),
    }
