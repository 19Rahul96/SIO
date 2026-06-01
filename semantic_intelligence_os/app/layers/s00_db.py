"""Database source connector for the Semantic Intelligence OS.

Reuses the proven SQLAlchemy introspection logic from the legacy backend so a live
database can be ingested through the same 14-layer pipeline: we connect, introspect
the schema (tables/columns/PK/FK/indexes), and render it as a corpus-text blob that
flows into extraction -> metadata -> entity/relation -> graph just like a document.

Supports PostgreSQL, MySQL, and SQLite. Drivers are optional; a clear error is
returned if SQLAlchemy or a dialect driver is missing.
"""
from __future__ import annotations

import json
from typing import Any, Optional

SYSTEM_SCHEMAS = {
    "postgresql": {"information_schema", "pg_catalog", "pg_toast"},
    "mysql": {"information_schema", "mysql", "performance_schema", "sys"},
}


def _engine(payload: dict):
    from sqlalchemy import create_engine, text  # imported lazily

    eng = (payload.get("engine") or "").strip().lower()
    if eng == "postgresql":
        url = (
            f"postgresql+psycopg2://{payload.get('user')}:{payload.get('password') or ''}"
            f"@{payload.get('host')}:{int(payload.get('port') or 5432)}/{payload.get('dbname')}"
        )
    elif eng == "mysql":
        url = (
            f"mysql+pymysql://{payload.get('user')}:{payload.get('password') or ''}"
            f"@{payload.get('host')}:{int(payload.get('port') or 3306)}/{payload.get('dbname')}"
        )
    elif eng == "sqlite":
        path = payload.get("path") or payload.get("dbname")
        if not path:
            raise ValueError("SQLite requires a file path")
        url = f"sqlite:///{path}"
    else:
        raise ValueError("Unsupported engine. Use postgresql, mysql, or sqlite")

    sa_engine = create_engine(url, pool_pre_ping=True)
    with sa_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return sa_engine


def _user_schemas(insp, dialect):
    if dialect == "sqlite":
        return [None]
    blocked = SYSTEM_SCHEMAS.get(dialect, set())
    schemas = [s for s in insp.get_schema_names() if s not in blocked]
    return schemas or [insp.default_schema_name]


def _schema_metadata(sa_engine) -> dict:
    from sqlalchemy import inspect

    insp = inspect(sa_engine)
    dialect = sa_engine.dialect.name
    tables = []
    for schema in _user_schemas(insp, dialect):
        for tname in insp.get_table_names(schema=schema):
            cols = [
                {"name": c.get("name"), "type": str(c.get("type")), "nullable": bool(c.get("nullable", True))}
                for c in insp.get_columns(tname, schema=schema)
            ]
            pk = insp.get_pk_constraint(tname, schema=schema) or {}
            fks = [
                {
                    "constrained_columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns", []),
                }
                for fk in (insp.get_foreign_keys(tname, schema=schema) or [])
            ]
            tables.append(
                {
                    "schema": schema,
                    "table_name": tname,
                    "columns": cols,
                    "primary_key": {"constrained_columns": pk.get("constrained_columns", [])},
                    "foreign_keys": fks,
                }
            )
    return {"dialect": dialect, "database": sa_engine.url.database, "tables": tables}


def _corpus_text(meta: dict) -> str:
    lines = [f"Database dialect: {meta['dialect']}", f"Database name: {meta['database']}"]
    for t in meta["tables"]:
        prefix = f"{t['schema']}." if t.get("schema") else ""
        lines += ["", f"Table: {prefix}{t['table_name']}"]
        pk = t["primary_key"]["constrained_columns"]
        if pk:
            lines.append(f"Primary key: {', '.join(pk)}")
        lines.append("Columns:")
        for c in t["columns"]:
            lines.append(f"- {c['name']} ({c['type']}) nullable={c['nullable']}")
        for fk in t["foreign_keys"]:
            src = ",".join(fk["constrained_columns"])
            tgt = f"{fk['referred_table']}({','.join(fk['referred_columns'])})"
            lines.append(f"Foreign key: {src} references {tgt}")
    return "\n".join(lines).strip() + "\n"


def test_connection(payload: dict) -> dict:
    """Validate connectivity and report table count + dialect (mirrors /db/test)."""
    try:
        eng = _engine(payload)
        meta = _schema_metadata(eng)
        eng.dispose()
        return {"ok": True, "dialect": meta["dialect"], "table_count": len(meta["tables"])}
    except ModuleNotFoundError as exc:
        return {"ok": False, "error": f"missing driver: {exc}. pip install sqlalchemy psycopg2-binary pymysql"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def schema_corpus(payload: dict) -> tuple[str, str]:
    """Connect, introspect, and return (corpus_text, db_label) for pipeline ingestion."""
    eng = _engine(payload)
    meta = _schema_metadata(eng)
    eng.dispose()
    label = f"database_{meta['dialect']}_{meta['database'] or 'db'}".replace("/", "_")
    return _corpus_text(meta), label
