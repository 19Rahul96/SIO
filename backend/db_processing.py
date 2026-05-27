import json
import logging
import os
import sqlite3
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional

from db_connector import connect_db, export_schema_as_corpus_text, export_schema_as_ddl, get_schema_metadata
from cross_source_linker import build_db_semantic_hints, link_cross_source
from data_dictionary import upsert_from_profile
from db_graphify import map_graphify_to_canonical, merge_into_canonical, parse_graphify_graph, run_graphify_extract
from db_profiler import compute_accuracy_metrics, detect_implicit_relationships, profile_database
from eda_engine import run_eda_engine
from knowledge_schema import validate_canonical_graph
from processing import chunk_text

PROCESSED_DIR = "data/processed"
DB_SCHEMA_ROOT = "data/db_schemas"
DB_DATA_ROOT = "data/db_data"
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CARBONATED_SQL_DIR = "data/db_data/carbonated_drinks"

logger = logging.getLogger(__name__)


def _resolve_backend_path(path_value: str) -> str:
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)
    return os.path.normpath(os.path.join(BACKEND_ROOT, path_value))


def _default_carbonated_sql_dir() -> str:
    return _resolve_backend_path(DEFAULT_CARBONATED_SQL_DIR)


def _materialize_sql_folder_to_sqlite(db_id: str, source_sql_dir: str, target_path: str | None = None) -> str:
    if not source_sql_dir:
        raise ValueError("source_sql_dir is required")

    sql_dir = _resolve_backend_path(source_sql_dir)

    if not os.path.isdir(sql_dir):
        raise ValueError(f"SQL source directory not found: {source_sql_dir}")

    sql_files = [
        os.path.join(sql_dir, name)
        for name in os.listdir(sql_dir)
        if name.lower().endswith(".sql")
    ]
    if not sql_files:
        raise ValueError(f"No .sql files found in source_sql_dir: {source_sql_dir}")

    create_statements: List[str] = []
    insert_statements: List[str] = []
    other_statements: List[str] = []

    for path in sorted(sql_files):
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for raw_stmt in content.split(";"):
            stmt = raw_stmt.strip()
            if not stmt:
                continue
            stmt_with_term = stmt + ";"
            upper = stmt.upper()
            if upper.startswith("CREATE TABLE"):
                create_statements.append(stmt_with_term)
            elif upper.startswith("INSERT INTO"):
                insert_statements.append(stmt_with_term)
            else:
                other_statements.append(stmt_with_term)

    out_path = target_path or os.path.join(DB_DATA_ROOT, "generated", f"{db_id}.sqlite")
    out_path = _resolve_backend_path(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(out_path):
        os.remove(out_path)

    with sqlite3.connect(out_path) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")
        for stmt in create_statements:
            cur.executescript(stmt)
        for stmt in other_statements:
            cur.executescript(stmt)
        for stmt in insert_statements:
            cur.executescript(stmt)
        cur.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    return out_path


def _fallback_graph_from_schema(metadata: Dict[str, Any], implicit_relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids = set()

    # Table and column nodes provide a deterministic local fallback when Graphify is unavailable.
    for table in metadata.get("tables", []):
        tname = table.get("table_name")
        if not tname:
            continue
        tnode = f"table:{tname}"
        if tnode not in node_ids:
            node_ids.add(tnode)
            nodes.append({"id": tnode, "label": tname, "type": "table"})

        for col in table.get("columns", []):
            cname = col.get("name")
            if not cname:
                continue
            cnode = f"column:{tname}.{cname}"
            if cnode not in node_ids:
                node_ids.add(cnode)
                nodes.append({"id": cnode, "label": f"{tname}.{cname}", "type": "column"})

            edges.append(
                {
                    "source": tnode,
                    "target": cnode,
                    "relation": "has_column",
                    "edge_type": "EXTRACTED",
                }
            )

        for fk in table.get("foreign_keys", []):
            target = fk.get("referred_table")
            if not target:
                continue
            edges.append(
                {
                    "source": tnode,
                    "target": f"table:{target}",
                    "relation": "foreign_key_to",
                    "edge_type": "EXTRACTED",
                }
            )

    for rel in implicit_relationships:
        st = rel.get("source_table")
        tt = rel.get("target_table")
        if not st or not tt:
            continue
        edges.append(
            {
                "source": f"table:{st}",
                "target": f"table:{tt}",
                "relation": f"implicit_{rel.get('source_col', 'link')}",
                "edge_type": "INFERRED",
            }
        )

    return {"nodes": nodes, "edges": edges}


def _status_path(db_id: str) -> str:
    return f"{PROCESSED_DIR}/{db_id}_status.json"


def _write_json(path: str, payload: Dict[str, Any]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except JSONDecodeError:
        # Another task may be writing this file; avoid surfacing transient 500s.
        return {}


def _write_status(db_id: str, updates: Dict[str, Any]):
    current = _read_json(_status_path(db_id))
    current.update(updates)
    current["updated_at"] = time.time()
    if "started_at" not in current and current.get("status") not in {"queued", "failed", "completed"}:
        current["started_at"] = current["updated_at"]
    _write_json(_status_path(db_id), current)


def init_db_status(db_id: str, engine: str, dbname: str = ""):
    _write_status(
        db_id,
        {
            "file_id": db_id,
            "db_id": db_id,
            "filename": f"Database ({engine}) {dbname or db_id[:8]}",
            "ext": "DB",
            "size": 0,
            "engine": engine,
            "database": dbname,
            "source_sql_dir": None,
            "status": "queued",
            "status_message": "DB job queued and waiting to start",
            "error": None,
            "uploaded_at": time.time(),
            "pipeline_steps": {
                "connecting": False,
                "introspecting": False,
                "profiling": False,
                "eda": False,
                "graphify_running": False,
                "merging": False,
                "embedding": False,
            },
        },
    )


def get_db_status(db_id: str) -> Dict[str, Any]:
    return _read_json(_status_path(db_id))


def _profile_path(db_id: str) -> str:
    return f"{PROCESSED_DIR}/{db_id}_profile.json"


def _schema_path(db_id: str) -> str:
    return f"{PROCESSED_DIR}/{db_id}_schema.json"


def _accuracy_path(db_id: str) -> str:
    return f"{PROCESSED_DIR}/{db_id}_accuracy.json"


def get_db_profile(db_id: str) -> Dict[str, Any]:
    return _read_json(_profile_path(db_id))


def get_db_schema(db_id: str) -> Dict[str, Any]:
    return _read_json(_schema_path(db_id))


def get_db_accuracy(db_id: str) -> Dict[str, Any]:
    return _read_json(_accuracy_path(db_id))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def get_eda_visuals(file_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    requested = set(file_ids or [])
    runs: List[Dict[str, Any]] = []

    if not os.path.exists(PROCESSED_DIR):
        return {
            "summary": {
                "run_count": 0,
                "table_count": 0,
                "anomalous_table_count": 0,
                "relationship_evidence_count": 0,
                "avg_overall_kg_quality": 0.0,
                "avg_confidence_score": 0.0,
                "avg_retrieval_readiness": 0.0,
                "avg_graph_trust_score": 0.0,
                "avg_knowledge_graph_effectiveness": 0.0,
                "avg_relationship_effectiveness": 0.0,
                "avg_high_risk_edge_ratio": 0.0,
                "avg_contradiction_ratio": 0.0,
                "avg_calibration_proxy_error": 0.0,
                "joinability_distribution": {"strong": 0, "medium": 0, "weak": 0},
            },
            "runs": [],
            "updated_at": time.time(),
        }

    for fname in os.listdir(PROCESSED_DIR):
        if not fname.endswith("_db_summary.json"):
            continue

        db_id = fname[: -len("_db_summary.json")]
        if requested and db_id not in requested:
            continue

        summary_path = os.path.join(PROCESSED_DIR, fname)
        summary = _read_json(summary_path)
        if not summary:
            continue

        eda_section = summary.get("eda", {})
        artifact_path = eda_section.get("artifact_path")
        artifact = _read_json(artifact_path) if artifact_path else {}

        eda_summary = eda_section.get("summary", {})
        table_stats = artifact.get("table_stats", {})
        anomaly_flags = artifact.get("anomaly_flags", {})
        rel_evidence = artifact.get("relationship_evidence", {})
        capabilities = artifact.get("capabilities", {}) or {}
        core_kpis = artifact.get("core_kpis", {}) or {}
        data_health = artifact.get("data_health", {}) or {}
        correlation = artifact.get("correlation", {}) or {}
        outliers = artifact.get("outliers", {}) or {}
        consistency_checks = artifact.get("consistency_checks", {}) or {}
        statistical_profiles = artifact.get("statistical_profiles", {}) or {}
        time_series = artifact.get("time_series", {}) or {}
        kg_analytics = artifact.get("kg_analytics", {}) or {}
        executive_summary = artifact.get("executive_summary", []) or []

        accuracy = summary.get("accuracy", {})
        graph_trust = accuracy.get("graph_trust", {})
        confidence_analysis = accuracy.get("confidence_analysis", {})

        joinability_distribution = {"strong": 0, "medium": 0, "weak": 0}
        for rel in rel_evidence.values():
            level = str(rel.get("joinability_signal", "weak")).lower()
            if level not in joinability_distribution:
                level = "weak"
            joinability_distribution[level] += 1

        semantic_confidence = accuracy.get("semantic_confidence", {})
        relationship_effectiveness = accuracy.get("relationship_effectiveness", {})

        confidence_score = _safe_float(semantic_confidence.get("mean_confidence", 0.0))
        trust_score = max(
            0.0,
            min(
                1.0,
                (0.45 * (1.0 - _safe_float(graph_trust.get("high_risk_edge_ratio", 0.0))))
                + (0.35 * relationship_effectiveness.get("evidence_success_rate", 0.0))
                + (0.2 * (1.0 - _safe_float(confidence_analysis.get("calibration_proxy_error", 0.0)))),
            ),
        )
        retrieval_readiness = max(
            0.0,
            min(
                1.0,
                (0.5 * confidence_score)
                + (0.35 * relationship_effectiveness.get("evidence_success_rate", 0.0))
                + (0.15 * (1.0 - _safe_float(graph_trust.get("contradiction_ratio", 0.0)))),
            ),
        )
        overall_quality = max(
            0.0,
            min(
                1.0,
                (0.45 * trust_score) + (0.3 * confidence_score) + (0.25 * retrieval_readiness),
            ),
        )

        top_tables = []
        for table_name, stats in table_stats.items():
            top_tables.append(
                {
                    "table_name": table_name,
                    "column_count": int(stats.get("column_count", 0) or 0),
                    "high_risk_column_count": int(stats.get("high_risk_column_count", 0) or 0),
                    "high_risk_ratio": _safe_float(stats.get("high_risk_ratio", 0.0)),
                }
            )
        top_tables.sort(key=lambda x: x["high_risk_ratio"], reverse=True)

        top_relationships = []
        for rel_key, rel in rel_evidence.items():
            top_relationships.append(
                {
                    "key": rel_key,
                    "overlap_pct": _safe_float(rel.get("overlap_pct", 0.0)),
                    "overlap_count": int(rel.get("overlap_count", 0) or 0),
                    "left_sample_count": int(rel.get("left_sample_count", 0) or 0),
                    "right_sample_count": int(rel.get("right_sample_count", 0) or 0),
                    "joinability_signal": rel.get("joinability_signal", "weak"),
                    "basis": rel.get("basis", "implicit"),
                }
            )
        top_relationships.sort(key=lambda x: x["overlap_pct"], reverse=True)

        status = get_db_status(db_id)
        processing_time_ms = 0
        started_at = _safe_float(status.get("uploaded_at", 0.0))
        completed_at = _safe_float(summary.get("completed_at", status.get("completed_at", 0.0)))
        if started_at > 0 and completed_at > 0:
            processing_time_ms = int(max(0.0, completed_at - started_at) * 1000)

        if not core_kpis:
            core_kpis = {
                "total_records": 0,
                "total_columns": sum(int(t.get("column_count", 0) or 0) for t in top_tables),
                "missing_pct": 0.0,
                "duplicate_rows": 0,
                "anomaly_count": sum(int(t.get("high_risk_column_count", 0) or 0) for t in top_tables),
                "file_size": 0,
                "entities_extracted": 0,
                "relationships_extracted": len(rel_evidence),
                "schema_drift_count": 0,
                "orphan_relationships": sum(1 for v in rel_evidence.values() if str(v.get("joinability_signal", "weak")).lower() == "weak"),
                "processing_time_ms": processing_time_ms,
                "timestamp_coverage_pct": 0.0,
            }
        else:
            core_kpis["processing_time_ms"] = int(core_kpis.get("processing_time_ms", processing_time_ms) or processing_time_ms)

        if not capabilities:
            capabilities = {
                "supports_time_series": False,
                "supports_correlation": False,
                "supports_kg_metrics": True,
                "supports_feature_importance": False,
            }

        runs.append(
            {
                "db_id": db_id,
                "status": status.get("status", "unknown"),
                "engine": status.get("engine") or "db",
                "database": status.get("database") or db_id,
                "completed_at": completed_at,
                "generated_at": artifact.get("generated_at", 0),
                "overall_kg_quality_score": round(overall_quality, 4),
                "confidence_score": round(confidence_score, 4),
                "retrieval_readiness_score": round(retrieval_readiness, 4),
                "graph_trust_score": round(trust_score, 4),
                "eda_summary": {
                    "table_count": int(eda_summary.get("table_count", 0) or 0),
                    "anomalous_table_count": int(eda_summary.get("anomalous_table_count", 0) or 0),
                    "relationship_evidence_count": int(eda_summary.get("relationship_evidence_count", 0) or 0),
                },
                "trust": {
                    "high_risk_edge_ratio": _safe_float(graph_trust.get("high_risk_edge_ratio", 0.0)),
                    "contradiction_ratio": _safe_float(graph_trust.get("contradiction_ratio", 0.0)),
                    "calibration_proxy_error": _safe_float(confidence_analysis.get("calibration_proxy_error", 0.0)),
                },
                "joinability_distribution": joinability_distribution,
                "anomaly_table_count": len(anomaly_flags),
                "top_tables": top_tables[:10],
                "top_relationship_evidence": top_relationships[:12],
                "capabilities": capabilities,
                "core_kpis": core_kpis,
                "data_health": data_health,
                "correlation": correlation,
                "outliers": outliers,
                "consistency_checks": consistency_checks,
                "statistical_profiles": statistical_profiles,
                "time_series": time_series,
                "kg_analytics": kg_analytics,
                "executive_summary": executive_summary,
            }
        )

    runs.sort(key=lambda x: float(x.get("completed_at", 0) or 0), reverse=True)

    total_tables = sum(int(r.get("eda_summary", {}).get("table_count", 0) or 0) for r in runs)
    total_anomalous = sum(int(r.get("eda_summary", {}).get("anomalous_table_count", 0) or 0) for r in runs)
    total_rel_evidence = sum(int(r.get("eda_summary", {}).get("relationship_evidence_count", 0) or 0) for r in runs)

    avg_high_risk = sum(_safe_float(r.get("trust", {}).get("high_risk_edge_ratio", 0.0)) for r in runs) / max(1, len(runs))
    avg_contradiction = sum(_safe_float(r.get("trust", {}).get("contradiction_ratio", 0.0)) for r in runs) / max(1, len(runs))
    avg_calibration = sum(_safe_float(r.get("trust", {}).get("calibration_proxy_error", 0.0)) for r in runs) / max(1, len(runs))
    avg_overall_quality = sum(_safe_float(r.get("overall_kg_quality_score", 0.0)) for r in runs) / max(1, len(runs))
    avg_confidence = sum(_safe_float(r.get("confidence_score", 0.0)) for r in runs) / max(1, len(runs))
    avg_retrieval_readiness = sum(_safe_float(r.get("retrieval_readiness_score", 0.0)) for r in runs) / max(1, len(runs))
    avg_trust = sum(_safe_float(r.get("graph_trust_score", 0.0)) for r in runs) / max(1, len(runs))

    joinability_distribution = {"strong": 0, "medium": 0, "weak": 0}
    for run in runs:
        dist = run.get("joinability_distribution", {})
        joinability_distribution["strong"] += int(dist.get("strong", 0) or 0)
        joinability_distribution["medium"] += int(dist.get("medium", 0) or 0)
        joinability_distribution["weak"] += int(dist.get("weak", 0) or 0)

    return {
        "summary": {
            "run_count": len(runs),
            "table_count": total_tables,
            "anomalous_table_count": total_anomalous,
            "relationship_evidence_count": total_rel_evidence,
            "avg_overall_kg_quality": round(avg_overall_quality, 4),
            "avg_confidence_score": round(avg_confidence, 4),
            "avg_retrieval_readiness": round(avg_retrieval_readiness, 4),
            "avg_graph_trust_score": round(avg_trust, 4),
            "avg_knowledge_graph_effectiveness": round(avg_overall_quality, 4),
            "avg_relationship_effectiveness": round(avg_confidence, 4),
            "avg_high_risk_edge_ratio": round(avg_high_risk, 4),
            "avg_contradiction_ratio": round(avg_contradiction, 4),
            "avg_calibration_proxy_error": round(avg_calibration, 4),
            "joinability_distribution": joinability_distribution,
        },
        "runs": runs,
        "updated_at": time.time(),
    }


def db_pipeline(db_id: str, conn_params: Dict[str, Any], embedding_store):
    """Background pipeline for DB -> schema/profile -> Graphify -> canonical merge."""
    db_engine = None
    try:
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        os.makedirs(DB_SCHEMA_ROOT, exist_ok=True)

        _write_status(
            db_id,
            {
                "file_id": db_id,
                "db_id": db_id,
                "status": "connecting",
                "status_message": "Connecting to database source",
                "error": None,
                "uploaded_at": time.time(),
                "pipeline_steps": {
                    "connecting": True,
                    "introspecting": False,
                    "profiling": False,
                    "eda": False,
                    "graphify_running": False,
                    "merging": False,
                    "embedding": False,
                },
            },
        )

        source_sql_dir = conn_params.get("source_sql_dir")

        if source_sql_dir:
            resolved_source = _resolve_backend_path(source_sql_dir)
            _write_status(
                db_id,
                {
                    "source_sql_dir": resolved_source,
                    "status_message": "Preparing sqlite database from SQL folder",
                },
            )
            sqlite_path = _materialize_sql_folder_to_sqlite(
                db_id,
                source_sql_dir=resolved_source,
                target_path=conn_params.get("path"),
            )
            conn_params = {
                "engine": "sqlite",
                "path": sqlite_path,
            }
            _write_status(
                db_id,
                {
                    "engine": "sqlite",
                    "database": "carbonated_drinks",
                    "path": sqlite_path,
                },
            )

        connect_params = {
            "engine": conn_params.get("engine"),
            "host": conn_params.get("host"),
            "port": conn_params.get("port"),
            "dbname": conn_params.get("dbname"),
            "user": conn_params.get("user"),
            "password": conn_params.get("password"),
            "path": conn_params.get("path"),
        }

        db_engine = connect_db(**connect_params)

        _write_status(
            db_id,
            {
                "status": "introspecting",
                "status_message": "Schema introspection in progress",
                "pipeline_steps": {
                    "connecting": True,
                    "introspecting": True,
                    "profiling": False,
                    "eda": False,
                    "graphify_running": False,
                    "merging": False,
                    "embedding": False,
                },
            },
        )

        metadata = get_schema_metadata(db_engine)
        _write_json(_schema_path(db_id), metadata)

        _write_status(
            db_id,
            {
                "status": "profiling",
                "status_message": "Running EDA profiling and semantic inference",
            },
        )
        profiler_emit = {"last_at": 0.0}

        def _profile_progress(done: int, total: int, table_name: str, column_name: str) -> None:
            now = time.time()
            should_emit = done == total or (now - profiler_emit["last_at"]) >= 2.0
            if not should_emit:
                return
            profiler_emit["last_at"] = now
            _write_status(
                db_id,
                {
                    "status": "profiling",
                    "status_message": f"Profiling columns {done}/{total}: {table_name}.{column_name}",
                },
            )


        profile = profile_database(metadata, db_engine, progress_cb=_profile_progress)
        implicit_relationships = detect_implicit_relationships(metadata)
        profile["implicit_relationships"] = implicit_relationships
        column_confidences: List[float] = []
        for t in profile.get("tables", []):
            for c in t.get("columns", []):
                column_confidences.append(float(c.get("semantic_confidence", 0.0) or 0.0))
        pre_eda_baseline = {
            "table_count": len(profile.get("tables", [])),
            "implicit_relationship_count": len(implicit_relationships),
            "semantic_mean_confidence": round(sum(column_confidences) / max(1, len(column_confidences)), 4),
        }
        _write_json(_profile_path(db_id), profile)

        # EDA runs immediately after profiling and before graph/link confidence decisions.
        eda_output_dir = os.path.join(PROCESSED_DIR, f"{db_id}_eda")
        eda_artifact = None
        eda_artifact_path = os.path.join(eda_output_dir, "eda_artifact.json")
        try:
            _write_status(
                db_id,
                {
                    "status": "eda_running",
                    "status_message": "Running EDA Engine (exploratory data analysis)",
                    "pipeline_steps": {
                        "connecting": True,
                        "introspecting": True,
                        "profiling": True,
                        "eda": True,
                        "graphify_running": False,
                        "merging": False,
                        "embedding": False,
                    },
                },
            )
            eda_artifact = run_eda_engine(profile, eda_output_dir)
            _write_status(
                db_id,
                {
                    "status": "eda_completed",
                    "status_message": "EDA Engine completed",
                    "eda_artifact_path": eda_artifact_path,
                },
            )
        except Exception as eda_ex:
            logger.warning(f"EDA Engine failed for {db_id}: {eda_ex}")
            _write_status(
                db_id,
                {
                    "status": "eda_failed",
                    "status_message": f"EDA Engine failed: {eda_ex}",
                },
            )
            eda_artifact = None

        dictionary_report = upsert_from_profile(db_id=db_id, profile=profile, eda_artifact=eda_artifact)
        profile["dictionary_report"] = dictionary_report
        if eda_artifact is not None:
            profile["eda_summary"] = eda_artifact.get("summary", {})
        _write_json(_profile_path(db_id), profile)

        schema_dir = f"{DB_SCHEMA_ROOT}/{db_id}"
        graphify_out_dir = f"{DB_SCHEMA_ROOT}/{db_id}_graphify_out"
        ddl_files = export_schema_as_ddl(db_engine, schema_dir)

        _write_status(
            db_id,
            {
                "status": "graphify_running",
                "status_message": "Exporting DDL and running Graphify extraction",
            },
        )
        graphify_run = run_graphify_extract(schema_dir, graphify_out_dir, backend="claude")
        graph_json_path = graphify_run.get("graph_json_path")
        if graph_json_path:
            graphify_graph = parse_graphify_graph(graph_json_path)
        else:
            graphify_graph = {"nodes": [], "edges": []}

        used_fallback_graph = False
        if not graphify_graph.get("nodes") and not graphify_graph.get("edges"):
            graphify_graph = _fallback_graph_from_schema(metadata, implicit_relationships)
            used_fallback_graph = True

        _write_status(
            db_id,
            {
                "status": "merging",
                "status_message": "Merging extracted graph into canonical knowledge graph",
            },
        )
        mapped = map_graphify_to_canonical(graphify_graph, db_id, eda_artifact=eda_artifact)
        cross_link_result = {
            "source_id": db_id,
            "accepted_edges": [],
            "report": {
                "accepted_count": 0,
                "review_count": 0,
                "rejected_count": 0,
                "linked_source_coverage_pct": 0.0,
            },
        }
        try:
            db_semantic_hints = build_db_semantic_hints(profile, mapped.get("resolved_nodes", []))
            cross_link_result = link_cross_source(
                source_id=db_id,
                source_type="db",
                source_nodes=mapped.get("resolved_nodes", []),
                embed_fn=embedding_store.embed_text,
                source_semantic_hints=db_semantic_hints,
                relationship_evidence=(eda_artifact or {}).get("relationship_evidence", {}),
            )
            mapped["resolved_edges"] = mapped.get("resolved_edges", []) + cross_link_result.get("accepted_edges", [])
        except Exception as ex:
            logger.warning("Cross-source linking failed for %s: %s", db_id, ex)
        schema_validation = validate_canonical_graph(
            mapped.get("resolved_nodes", []),
            mapped.get("resolved_edges", []),
            eda_artifact=eda_artifact,
        )
        merge_report = merge_into_canonical(db_id, mapped)

        _write_status(
            db_id,
            {
                "status": "embedding",
                "status_message": "Building schema embeddings for retrieval",
            },
        )
        corpus_text = export_schema_as_corpus_text(db_engine, metadata)
        chunks = chunk_text(corpus_text, size=300, overlap=50)
        embedding_store.add_chunks(db_id, chunks)

        accuracy = compute_accuracy_metrics(metadata, profile, graphify_graph, eda_artifact=eda_artifact)
        _write_json(_accuracy_path(db_id), accuracy)

        post_eda_effect = {
            "relationship_evidence_count": int(((eda_artifact or {}).get("summary") or {}).get("relationship_evidence_count", 0) or 0),
            "high_risk_edge_ratio": float((accuracy.get("graph_trust") or {}).get("high_risk_edge_ratio", 0.0) or 0.0),
            "contradiction_ratio": float((accuracy.get("graph_trust") or {}).get("contradiction_ratio", 0.0) or 0.0),
        }

        summary = {
            "db_id": db_id,
            "ddl_files": ddl_files,
            "graphify": {
                "ok": graphify_run.get("ok"),
                "return_code": graphify_run.get("return_code"),
                "graph_json_path": graph_json_path,
                "used_fallback_graph": used_fallback_graph,
            },
            "merge_report": merge_report,
            "cross_link_report": cross_link_result.get("report", {}),
            "accuracy": accuracy,
            "pre_eda_baseline": pre_eda_baseline,
            "post_eda_effect": post_eda_effect,
            "dictionary_report": dictionary_report,
            "schema_validation": schema_validation,
            "eda": {
                "artifact_path": eda_artifact_path if os.path.exists(eda_artifact_path) else None,
                "summary": (eda_artifact or {}).get("summary", {}),
            },
            "implicit_relationship_count": len(implicit_relationships),
            "completed_at": time.time(),
        }
        _write_json(f"{PROCESSED_DIR}/{db_id}_db_summary.json", summary)

        _write_status(
            db_id,
            {
                "status": "completed",
                "error": None,
                "completed_at": time.time(),
                "schema_tables": len(metadata.get("tables", [])),
                "profiled_tables": len(profile.get("tables", [])),
                "graphify_ok": bool(graphify_run.get("ok")),
                "semantic_inference": profile.get("semantic_inference", {}),
                "dictionary_report": dictionary_report,
                "cross_link_report": cross_link_result.get("report", {}),
                "schema_validation": schema_validation,
                "status_message": "DB ingestion pipeline completed",
                "pipeline_steps": {
                    "connecting": True,
                    "introspecting": True,
                    "profiling": True,
                    "eda": True,
                    "graphify_running": True,
                    "merging": True,
                    "embedding": True,
                },
            },
        )
    except Exception as ex:
        logger.exception("DB pipeline failed for %s", db_id)
        _write_status(db_id, {"status": "failed", "error": str(ex)})
    finally:
        if db_engine is not None:
            db_engine.dispose()
