import asyncio
import json
import logging
import os
import re
from statistics import mean
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

SEMANTIC_LABELS = [
    "identifier",
    "email",
    "name",
    "phone_number",
    "datetime",
    "monetary_value",
    "status",
    "location",
    "score",
    "category",
    "url",
    "gender",
    "age",
    "text_content",
    "quantity",
    "unknown",
]

_LLM_LOOP: Optional[asyncio.AbstractEventLoop] = None
_LLM_DISABLED_REASON: Optional[str] = None
_LLM_INFERENCE_CALLS = 0
_LLM_MAX_CALLS = max(0, int(os.getenv("DB_SEMANTIC_LLM_MAX_COLUMNS", "12")))


def _run_async(coro):
    global _LLM_LOOP
    if _LLM_LOOP is None or _LLM_LOOP.is_closed():
        _LLM_LOOP = asyncio.new_event_loop()
    return _LLM_LOOP.run_until_complete(coro)


def _quote_identifier(db_engine: Engine, identifier: str) -> str:
    return db_engine.dialect.identifier_preparer.quote(identifier)


def _qualified_name(db_engine: Engine, table_name: str, schema: Optional[str]) -> str:
    qt = _quote_identifier(db_engine, table_name)
    if not schema:
        return qt
    qs = _quote_identifier(db_engine, schema)
    return f"{qs}.{qt}"


def profile_column(
    db_engine: Engine,
    table_name: str,
    column_name: str,
    schema: Optional[str] = None,
    sample_size: int = 20,
) -> Dict[str, Any]:
    q_table = _qualified_name(db_engine, table_name, schema)
    q_col = _quote_identifier(db_engine, column_name)

    profile: Dict[str, Any] = {
        "table": table_name,
        "schema": schema,
        "column": column_name,
        "null_pct": None,
        "cardinality": None,
        "sample_values": [],
        "min": None,
        "max": None,
        "mean": None,
        "std": None,
        "semantic_label": "unknown",
        "semantic_confidence": 0.0,
    }

    with db_engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {q_table}")).scalar() or 0
        if int(total) == 0:
            return profile

        nulls = conn.execute(text(f"SELECT COUNT(*) FROM {q_table} WHERE {q_col} IS NULL")).scalar() or 0
        card = conn.execute(text(f"SELECT COUNT(DISTINCT {q_col}) FROM {q_table}")).scalar() or 0
        samples = conn.execute(
            text(
                f"SELECT {q_col} FROM {q_table} "
                f"WHERE {q_col} IS NOT NULL LIMIT {int(sample_size)}"
            )
        ).fetchall()

        values = [r[0] for r in samples if r and r[0] is not None]
        profile["null_pct"] = round((float(nulls) / float(total)) * 100.0, 2)
        profile["cardinality"] = int(card)
        profile["sample_values"] = [str(v)[:120] for v in values]

        # Numeric stats are attempted without requiring strict SQL type checks.
        numeric_vals: List[float] = []
        for v in values:
            if isinstance(v, (int, float)):
                numeric_vals.append(float(v))
        if numeric_vals:
            profile["min"] = min(numeric_vals)
            profile["max"] = max(numeric_vals)
            profile["mean"] = round(mean(numeric_vals), 6)
            if len(numeric_vals) > 1:
                avg = mean(numeric_vals)
                variance = sum((x - avg) ** 2 for x in numeric_vals) / len(numeric_vals)
                profile["std"] = round(variance ** 0.5, 6)

    return profile


def detect_semantic_meaning(
    col_name: str,
    sample_values: List[Any],
    llm_client: Any = None,
) -> Dict[str, Any]:
    """Infer semantic label using LLM when available, then heuristics as fallback."""
    heuristics = {
        r"(^|_)id$": "identifier",
        r"email": "email",
        r"name": "name",
        r"phone|mobile": "phone_number",
        r"date|time|timestamp": "datetime",
        r"amount|price|cost|total|revenue|budget": "monetary_value",
        r"status|state": "status",
        r"country|city|address|region": "location",
        r"rating|score|index": "score",
        r"type|format|category|platform": "category",
        r"url|website|link": "url",
        r"gender": "gender",
        r"age": "age",
        r"text|review|title|description|notes": "text_content",
        r"units|count|quantity|volume|capacity": "quantity",
    }

    def _heuristic() -> Dict[str, Any]:
        for pattern, label in heuristics.items():
            if re.search(pattern, col_name.lower()):
                return {"semantic_label": label, "confidence": 0.72, "method": "heuristic"}
        return {"semantic_label": "unknown", "confidence": 0.35, "method": "heuristic"}

    heuristic_guess = _heuristic()
    if heuristic_guess["semantic_label"] != "unknown":
        return heuristic_guess

    global _LLM_DISABLED_REASON
    global _LLM_INFERENCE_CALLS

    has_llm_credentials = any(
        os.getenv(key)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")
    )
    if not has_llm_credentials or _LLM_DISABLED_REASON:
        return heuristic_guess
    if _LLM_INFERENCE_CALLS >= _LLM_MAX_CALLS:
        return heuristic_guess

    try:
        from llm_client import call_llm

        preview = ", ".join(str(v)[:48] for v in (sample_values or [])[:8])
        prompt = (
            "Classify this database column into a semantic label. "
            "Return strict JSON only with keys semantic_label and confidence."
        )
        context = (
            f"Column name: {col_name}\n"
            f"Sample values: {preview or 'n/a'}\n"
            f"Allowed labels: {', '.join(SEMANTIC_LABELS)}\n"
            "Confidence must be a float between 0 and 1."
        )

        _LLM_INFERENCE_CALLS += 1
        llm_out = _run_async(call_llm(prompt, context, [], model="gpt-4o-mini"))

        parsed = None
        try:
            parsed = json.loads(llm_out)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", llm_out or "")
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    parsed = None

        if isinstance(parsed, dict):
            label = str(parsed.get("semantic_label", "unknown")).strip().lower()
            confidence = parsed.get("confidence", 0.45)
            try:
                confidence = float(confidence)
            except Exception:
                confidence = 0.45

            if label not in SEMANTIC_LABELS:
                label = "unknown"

            confidence = max(0.0, min(1.0, confidence))
            return {
                "semantic_label": label,
                "confidence": round(confidence, 4),
                "method": "llm",
            }
    except Exception as ex:
        msg = str(ex)
        if "429" in msg or "quota" in msg.lower() or "insufficient_quota" in msg.lower():
            _LLM_DISABLED_REASON = msg
            logger.warning("Disabling semantic LLM inference after quota/rate limit error: %s", ex)
        else:
            logger.warning("Semantic LLM inference failed for column '%s': %s", col_name, ex)

    return heuristic_guess


def profile_database(
    metadata: Dict[str, Any],
    db_engine: Engine,
    progress_cb: Optional[Callable[[int, int, str, str], None]] = None,
) -> Dict[str, Any]:
    tables_report: List[Dict[str, Any]] = []
    method_counts: Dict[str, int] = {"llm": 0, "heuristic": 0}
    total_columns = sum(len(t.get("columns", [])) for t in metadata.get("tables", []))
    profiled_columns = 0

    for table in metadata.get("tables", []):
        table_name = table.get("table_name")
        schema = table.get("schema")
        table_profile = {
            "schema": schema,
            "table_name": table_name,
            "columns": [],
        }

        for col in table.get("columns", []):
            col_name = col.get("name")
            prof = profile_column(db_engine, table_name, col_name, schema=schema)
            semantic = detect_semantic_meaning(col_name, prof.get("sample_values", []))
            prof["semantic_label"] = semantic["semantic_label"]
            prof["semantic_confidence"] = semantic["confidence"]
            prof["semantic_inference_method"] = semantic.get("method", "heuristic")
            method_key = prof["semantic_inference_method"]
            method_counts[method_key] = method_counts.get(method_key, 0) + 1
            table_profile["columns"].append(prof)
            profiled_columns += 1
            if progress_cb:
                progress_cb(profiled_columns, max(1, total_columns), str(table_name or ""), str(col_name or ""))

        tables_report.append(table_profile)

    return {
        "dialect": metadata.get("dialect"),
        "database": metadata.get("database"),
        "tables": tables_report,
        "semantic_inference": {
            "llm_columns": method_counts.get("llm", 0),
            "heuristic_columns": method_counts.get("heuristic", 0),
        },
    }


def detect_implicit_relationships(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    relationships: List[Dict[str, Any]] = []
    table_columns: Dict[str, List[Dict[str, Any]]] = {}

    for t in metadata.get("tables", []):
        tname = t.get("table_name")
        if tname:
            table_columns[tname] = t.get("columns", [])

    for source_table, columns in table_columns.items():
        for col in columns:
            col_name = (col.get("name") or "").lower()
            if not col_name.endswith("_id"):
                continue

            candidate_table = col_name[: -len("_id")]
            candidate_plural = f"{candidate_table}s"
            targets = [candidate_table, candidate_plural]

            for target_table in targets:
                target_cols = table_columns.get(target_table)
                if not target_cols:
                    continue

                id_like = [c for c in target_cols if (c.get("name") or "").lower() in {"id", f"{target_table}_id"}]
                if not id_like:
                    continue

                relationships.append(
                    {
                        "source_table": source_table,
                        "source_col": col.get("name"),
                        "target_table": target_table,
                        "target_col": id_like[0].get("name"),
                        "confidence": 0.75,
                        "basis": "naming_rule:_id",
                    }
                )
                break

    return relationships


def compute_accuracy_metrics(
    metadata: Dict[str, Any],
    profiled: Dict[str, Any],
    graphify_graph: Dict[str, Any],
) -> Dict[str, Any]:
    actual_fk = 0
    for t in metadata.get("tables", []):
        actual_fk += len(t.get("foreign_keys", []))

    detected_explicit_fk = actual_fk
    fk_detection_rate = float(detected_explicit_fk) / float(actual_fk) if actual_fk else 1.0

    semantic_scores: List[float] = []
    for table in profiled.get("tables", []):
        for col in table.get("columns", []):
            semantic_scores.append(float(col.get("semantic_confidence", 0.0) or 0.0))
    semantic_conf = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.0

    edge_quality = {"EXTRACTED": 0, "INFERRED": 0, "AMBIGUOUS": 0}
    for edge in graphify_graph.get("edges", []):
        etype = str(edge.get("edge_type") or edge.get("type") or "").upper()
        if etype in edge_quality:
            edge_quality[etype] += 1

    return {
        "fk_detection": {
            "detected_explicit_fks": detected_explicit_fk,
            "actual_fk_constraints": actual_fk,
            "fk_detection_rate": round(fk_detection_rate, 4),
        },
        "semantic_confidence": {
            "mean_confidence": round(semantic_conf, 4),
            "column_count": len(semantic_scores),
        },
        "graphify_quality": edge_quality,
    }
