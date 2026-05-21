import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.request
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
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
_OLLAMA_FALLBACK_MODELS = ["llama3:8b", "qwen2.5:7b", "phi3:mini"]
_TABLE_LLM_MAX_CALLS = max(0, int(os.getenv("DB_SEMANTIC_LLM_MAX_TABLES", "40")))

TABLE_DOMAIN_LABELS = [
    "reference_dimension",
    "master_entity",
    "transaction_fact",
    "event_log",
    "metrics_aggregate",
    "bridge_mapping",
    "audit_history",
    "configuration",
    "lookup_code",
    "unknown",
]


def _run_async(coro):
    global _LLM_LOOP
    if _LLM_LOOP is None or _LLM_LOOP.is_closed():
        _LLM_LOOP = asyncio.new_event_loop()
    return _LLM_LOOP.run_until_complete(coro)


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _call_ollama_json(prompt: str, max_tokens: int = 180) -> Optional[Dict[str, Any]]:
    global _LLM_DISABLED_REASON
    if _LLM_DISABLED_REASON:
        return None

    model_candidates = [_OLLAMA_MODEL] + [m for m in _OLLAMA_FALLBACK_MODELS if m != _OLLAMA_MODEL]

    try:
        for model in model_candidates:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.0,
                },
            }

            req = urllib.request.Request(
                url=f"{_OLLAMA_URL.rstrip('/')}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="ignore")

            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("error"):
                err = str(parsed.get("error"))
                if "not found" in err.lower() or "pull" in err.lower():
                    continue
                logger.warning("Ollama returned error for model '%s': %s", model, err)
                return None

            response_text = parsed.get("response", "") if isinstance(parsed, dict) else ""
            extracted = _extract_json_object(response_text)
            if extracted:
                return extracted
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as ex:
        logger.warning("Ollama semantic inference unavailable: %s", ex)
        _LLM_DISABLED_REASON = str(ex)
        return None
    except Exception as ex:
        logger.warning("Ollama semantic inference failed: %s", ex)
        return None


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

    if _LLM_DISABLED_REASON:
        return heuristic_guess
    if _LLM_INFERENCE_CALLS >= _LLM_MAX_CALLS:
        return heuristic_guess

    try:
        preview = ", ".join(str(v)[:48] for v in (sample_values or [])[:8])
        prompt = (
            "Classify this database column into one allowed semantic label. "
            "Return only JSON with keys semantic_label and confidence.\n\n"
            f"Column name: {col_name}\n"
            f"Sample values: {preview or 'n/a'}\n"
            f"Allowed labels: {', '.join(SEMANTIC_LABELS)}\n"
            "Confidence must be a float between 0 and 1."
        )

        _LLM_INFERENCE_CALLS += 1
        parsed = _call_ollama_json(prompt, max_tokens=100)

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
                "method": "ollama",
            }
    except Exception as ex:
        logger.warning("Semantic LLM inference failed for column '%s': %s", col_name, ex)

    return heuristic_guess


def detect_table_semantic_meaning(
    table_name: str,
    columns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    name = str(table_name or "").lower()
    labels = [str(c.get("semantic_label", "unknown")) for c in columns]
    label_counts = {k: labels.count(k) for k in set(labels)}

    # Fast deterministic fallback.
    if name.endswith("_dim") or name.startswith("dim_"):
        fallback = {"table_semantic_label": "reference_dimension", "confidence": 0.82, "method": "heuristic"}
    elif name.endswith("_fact") or name.startswith("fact_"):
        fallback = {"table_semantic_label": "transaction_fact", "confidence": 0.82, "method": "heuristic"}
    elif "audit" in name or "history" in name:
        fallback = {"table_semantic_label": "audit_history", "confidence": 0.8, "method": "heuristic"}
    elif "config" in name or "setting" in name:
        fallback = {"table_semantic_label": "configuration", "confidence": 0.78, "method": "heuristic"}
    elif ("identifier" in label_counts and label_counts.get("identifier", 0) >= 2) and any(
        l in label_counts for l in ("amount", "price", "datetime")
    ):
        fallback = {"table_semantic_label": "transaction_fact", "confidence": 0.7, "method": "heuristic"}
    else:
        fallback = {"table_semantic_label": "unknown", "confidence": 0.4, "method": "heuristic"}

    if _LLM_DISABLED_REASON:
        return fallback
    if _LLM_INFERENCE_CALLS >= (_LLM_MAX_CALLS + _TABLE_LLM_MAX_CALLS):
        return fallback

    column_summaries = []
    for c in columns[:20]:
        column_summaries.append(
            {
                "name": c.get("column"),
                "semantic_label": c.get("semantic_label"),
                "null_pct": c.get("null_pct"),
                "cardinality": c.get("cardinality"),
            }
        )

    prompt = (
        "Classify the table role using the provided columns and semantic labels. "
        "Return only JSON with keys table_semantic_label and confidence.\n\n"
        f"Table name: {table_name}\n"
        f"Columns: {json.dumps(column_summaries, ensure_ascii=True)}\n"
        f"Allowed labels: {', '.join(TABLE_DOMAIN_LABELS)}\n"
        "Confidence must be float between 0 and 1."
    )

    parsed = _call_ollama_json(prompt, max_tokens=140)
    if not isinstance(parsed, dict):
        return fallback

    label = str(parsed.get("table_semantic_label", "unknown")).strip().lower()
    confidence = parsed.get("confidence", fallback["confidence"])
    try:
        confidence = float(confidence)
    except Exception:
        confidence = fallback["confidence"]
    confidence = max(0.0, min(1.0, confidence))

    if label not in TABLE_DOMAIN_LABELS:
        return fallback

    return {
        "table_semantic_label": label,
        "confidence": round(confidence, 4),
        "method": "ollama",
    }


def profile_database(
    metadata: Dict[str, Any],
    db_engine: Engine,
    progress_cb: Optional[Callable[[int, int, str, str], None]] = None,
) -> Dict[str, Any]:
    tables_report: List[Dict[str, Any]] = []
    method_counts: Dict[str, int] = {"ollama": 0, "heuristic": 0}
    table_method_counts: Dict[str, int] = {"ollama": 0, "heuristic": 0}
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

        table_semantic = detect_table_semantic_meaning(str(table_name or ""), table_profile["columns"])
        table_profile["table_semantic_label"] = table_semantic["table_semantic_label"]
        table_profile["table_semantic_confidence"] = table_semantic["confidence"]
        table_profile["table_semantic_inference_method"] = table_semantic.get("method", "heuristic")
        tmethod_key = table_profile["table_semantic_inference_method"]
        table_method_counts[tmethod_key] = table_method_counts.get(tmethod_key, 0) + 1

        tables_report.append(table_profile)

    return {
        "dialect": metadata.get("dialect"),
        "database": metadata.get("database"),
        "tables": tables_report,
        "semantic_inference": {
            "ollama_columns": method_counts.get("ollama", 0),
            "heuristic_columns": method_counts.get("heuristic", 0),
            "ollama_tables": table_method_counts.get("ollama", 0),
            "heuristic_tables": table_method_counts.get("heuristic", 0),
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
    eda_artifact: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    actual_fk = 0
    for t in metadata.get("tables", []):
        actual_fk += len(t.get("foreign_keys", []))

    detected_explicit_fk = actual_fk
    fk_detection_rate = float(detected_explicit_fk) / float(actual_fk) if actual_fk else 1.0

    semantic_scores: List[float] = []
    table_semantic_scores: List[float] = []
    for table in profiled.get("tables", []):
        for col in table.get("columns", []):
            semantic_scores.append(float(col.get("semantic_confidence", 0.0) or 0.0))
        table_semantic_scores.append(float(table.get("table_semantic_confidence", 0.0) or 0.0))
    semantic_conf = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.0
    table_semantic_conf = sum(table_semantic_scores) / len(table_semantic_scores) if table_semantic_scores else 0.0

    edge_quality = {"EXTRACTED": 0, "INFERRED": 0, "AMBIGUOUS": 0}
    for edge in graphify_graph.get("edges", []):
        etype = str(edge.get("edge_type") or edge.get("type") or "").upper()
        if etype in edge_quality:
            edge_quality[etype] += 1

    confidence_bands = {"low": 0, "medium": 0, "high": 0}
    for table in profiled.get("tables", []):
        for col in table.get("columns", []):
            conf = float(col.get("semantic_confidence", 0.0) or 0.0)
            if conf < 0.5:
                confidence_bands["low"] += 1
            elif conf < 0.75:
                confidence_bands["medium"] += 1
            else:
                confidence_bands["high"] += 1

    rel_evidence = (eda_artifact or {}).get("relationship_evidence", {})
    rel_count = len(rel_evidence)
    strong_evidence = 0
    weak_evidence = 0
    for payload in rel_evidence.values():
        overlap = float((payload or {}).get("overlap_pct", 0.0) or 0.0)
        if overlap >= 0.7:
            strong_evidence += 1
        elif overlap < 0.35:
            weak_evidence += 1

    inferred_edges = edge_quality.get("INFERRED", 0)
    ambiguous_edges = edge_quality.get("AMBIGUOUS", 0)
    extracted_edges = edge_quality.get("EXTRACTED", 0)
    total_modeled_edges = inferred_edges + ambiguous_edges + extracted_edges

    high_risk_edge_ratio = (ambiguous_edges + weak_evidence) / max(1, total_modeled_edges)
    contradiction_ratio = weak_evidence / max(1, rel_count)

    calibration_proxy_error = abs(confidence_bands["high"] - strong_evidence) / max(
        1, confidence_bands["high"] + strong_evidence
    )

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
        "table_semantic_confidence": {
            "mean_confidence": round(table_semantic_conf, 4),
            "table_count": len(table_semantic_scores),
        },
        "graphify_quality": edge_quality,
        "relationship_effectiveness": {
            "evidence_count": rel_count,
            "strong_evidence_count": strong_evidence,
            "weak_evidence_count": weak_evidence,
            "evidence_success_rate": round(strong_evidence / max(1, rel_count), 4),
        },
        "confidence_analysis": {
            "confidence_bands": confidence_bands,
            "calibration_proxy_error": round(calibration_proxy_error, 4),
        },
        "graph_trust": {
            "high_risk_edge_ratio": round(high_risk_edge_ratio, 4),
            "contradiction_ratio": round(contradiction_ratio, 4),
            "edge_confidence_distribution": {
                "extracted": extracted_edges,
                "inferred": inferred_edges,
                "ambiguous": ambiguous_edges,
            },
        },
    }
