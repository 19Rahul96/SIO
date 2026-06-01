"""Step 5 — Metadata Intelligence Engine.

WHY: enterprise schemas are cryptic (TMP_X1, col_102); meaning must be inferred.
PRODUCES: per-column semantic labels, datatype inference, PK/FK *predictions*,
          table classification — each with a confidence + explainability trace.
ORDERING: after chunking so tabular structure is known, before entity extraction so
          column semantics can guide what entities/relations to look for.
ENABLES: ontology-aware extraction (6), schema relationships, and metadata studio UI.

Operates on tabular corpora (table_rows/columns). For pure text it returns an empty
metadata set so the pipeline stays uniform.
"""
from __future__ import annotations

import re

from ..contracts.audit import make_audit

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Semantic label hints keyed by normalized column-name tokens.
_NAME_HINTS = {
    "id": "identifier",
    "key": "identifier",
    "ref": "identifier",
    "code": "identifier",
    "name": "person_or_org_name",
    "email": "email",
    "mail": "email",
    "date": "temporal",
    "time": "temporal",
    "amount": "monetary",
    "price": "monetary",
    "cost": "monetary",
    "revenue": "monetary",
    "qty": "quantity",
    "count": "quantity",
    "city": "location",
    "country": "location",
    "address": "location",
}


def _infer_datatype(values: list[str]) -> str:
    sample = [v for v in values if v != ""][:200]
    if not sample:
        return "unknown"
    if all(_NUMERIC.match(v) for v in sample):
        return "numeric"
    if all(_DATE.match(v) for v in sample):
        return "date"
    if all(_EMAIL.match(v) for v in sample):
        return "email"
    return "text"


def _label_column(col: str, values: list[str], datatype: str) -> tuple[str, float, dict]:
    norm = re.sub(r"[^a-z0-9]+", " ", col.lower()).strip()
    tokens = norm.split()
    evidence = {"name_tokens": tokens, "datatype": datatype}

    for tok in tokens:
        if tok in _NAME_HINTS:
            return _NAME_HINTS[tok], 0.78, {**evidence, "matched_token": tok}

    # Value-profile fallback (cryptic names like col_102 / TMP_X1).
    if datatype == "email":
        return "email", 0.82, evidence
    if datatype == "date":
        return "temporal", 0.80, evidence
    if datatype == "numeric":
        return "quantity", 0.55, evidence
    return "free_text", 0.40, evidence


def _predict_keys(columns: list[str], col_values: dict[str, list[str]], n_rows: int) -> dict:
    pk_candidates, fk_candidates = [], []
    for col in columns:
        vals = [v for v in col_values[col] if v != ""]
        if not vals:
            continue
        uniqueness = len(set(vals)) / len(vals)
        name = col.lower()
        # PK: near-unique + non-null + id-like name.
        if uniqueness >= 0.98 and len(vals) >= max(1, int(0.95 * n_rows)):
            score = 0.6 + 0.3 * (1.0 if re.search(r"(^id$|_id$|key|code)", name) else 0.0)
            pk_candidates.append({"column": col, "uniqueness": round(uniqueness, 3), "score": round(score, 3)})
        # FK: id-like name but NOT unique (repeats -> references another table).
        elif re.search(r"(_id$|_ref$|_key$|_code$)", name) and uniqueness < 0.9:
            fk_candidates.append({"column": col, "uniqueness": round(uniqueness, 3), "score": 0.6})
    pk_candidates.sort(key=lambda x: -x["score"])
    return {"primary_key": pk_candidates[:1], "foreign_keys": fk_candidates}


def _classify_table(labels: dict) -> tuple[str, float]:
    sem = list(labels.values())
    if sem.count("monetary") >= 1 and "temporal" in sem:
        return "transactional", 0.7
    if sem.count("identifier") >= 2:
        return "reference/dimension", 0.65
    if "person_or_org_name" in sem:
        return "entity_master", 0.6
    return "generic", 0.4


def build_metadata(corpus: dict, chunked: dict) -> dict:
    columns = corpus.get("columns")
    if not columns or not corpus.get("table_rows"):
        return {"source_id": corpus["source_id"], "is_tabular": False, "columns": []}

    rows = corpus["table_rows"]
    col_values = {c: [str(r["cells"].get(c, "")) for r in rows] for c in columns}

    column_meta, labels = [], {}
    for col in columns:
        values = col_values[col]
        datatype = _infer_datatype(values)
        label, conf, ev = _label_column(col, values, datatype)
        labels[col] = label
        non_null = sum(1 for v in values if v != "")
        column_meta.append(
            {
                "column": col,
                "datatype": datatype,
                "semantic_label": label,
                "null_pct": round(100 * (1 - non_null / max(1, len(values))), 2),
                "cardinality": len(set(values)),
                "audit": make_audit(
                    score=conf,
                    scorer="metadata_intelligence",
                    stage="metadata",
                    action="auto_accept" if conf >= 0.6 else "review_required",
                    evidence=ev,
                ),
            }
        )

    keys = _predict_keys(columns, col_values, len(rows))
    table_class, class_conf = _classify_table(labels)
    return {
        "source_id": corpus["source_id"],
        "is_tabular": True,
        "row_count": len(rows),
        "columns": column_meta,
        "predicted_keys": keys,
        "table_classification": {"label": table_class, "confidence": class_conf},
    }
