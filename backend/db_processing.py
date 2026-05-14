import json
import logging
import os
import sqlite3
import time
from json import JSONDecodeError
from typing import Any, Dict, List

from db_connector import connect_db, export_schema_as_corpus_text, export_schema_as_ddl, get_schema_metadata
from db_graphify import map_graphify_to_canonical, merge_into_canonical, parse_graphify_graph, run_graphify_extract
from db_profiler import compute_accuracy_metrics, detect_implicit_relationships, profile_database
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
    source_sql_dir = _default_carbonated_sql_dir() if engine == "sqlite" else None
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
            "source_sql_dir": source_sql_dir,
            "status": "queued",
            "status_message": "DB job queued and waiting to start",
            "error": None,
            "uploaded_at": time.time(),
            "pipeline_steps": {
                "connecting": False,
                "introspecting": False,
                "profiling": False,
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
                    "graphify_running": False,
                    "merging": False,
                    "embedding": False,
                },
            },
        )

        source_sql_dir = conn_params.get("source_sql_dir")
        engine = str(conn_params.get("engine") or "").lower()
        if engine == "sqlite" and not source_sql_dir:
            source_sql_dir = _default_carbonated_sql_dir()

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
        mapped = map_graphify_to_canonical(graphify_graph, db_id)
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

        accuracy = compute_accuracy_metrics(metadata, profile, graphify_graph)
        _write_json(_accuracy_path(db_id), accuracy)

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
            "accuracy": accuracy,
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
                "status_message": "DB ingestion pipeline completed",
                "pipeline_steps": {
                    "connecting": True,
                    "introspecting": True,
                    "profiling": True,
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
