import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable

logger = logging.getLogger(__name__)

SYSTEM_SCHEMAS = {
    "postgresql": {"information_schema", "pg_catalog", "pg_toast"},
    "mysql": {"information_schema", "mysql", "performance_schema", "sys"},
}


def connect_db(
    engine: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    dbname: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    path: Optional[str] = None,
) -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL, MySQL, or SQLite."""
    eng = (engine or "").strip().lower()

    if eng == "postgresql":
        if not all([host, dbname, user]):
            raise ValueError("PostgreSQL requires host, dbname, and user")
        port = int(port or 5432)
        url = f"postgresql+psycopg2://{user}:{password or ''}@{host}:{port}/{dbname}"
    elif eng == "mysql":
        if not all([host, dbname, user]):
            raise ValueError("MySQL requires host, dbname, and user")
        port = int(port or 3306)
        url = f"mysql+pymysql://{user}:{password or ''}@{host}:{port}/{dbname}"
    elif eng == "sqlite":
        if not path:
            raise ValueError("SQLite requires path")
        sqlite_path = path if path != ":memory:" else ":memory:"
        url = f"sqlite:///{sqlite_path}" if sqlite_path != ":memory:" else "sqlite:///:memory:"
    else:
        raise ValueError("Unsupported engine. Use postgresql, mysql, or sqlite")

    # Never log URL because it may contain credentials.
    sa_engine = create_engine(url, pool_pre_ping=True)

    # Force an early connectivity check and fail fast.
    with sa_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return sa_engine


def _iter_user_schemas(db_engine: Engine) -> List[Optional[str]]:
    insp = inspect(db_engine)
    dialect = db_engine.dialect.name

    if dialect == "sqlite":
        return [None]

    all_schemas = insp.get_schema_names()
    blocked = SYSTEM_SCHEMAS.get(dialect, set())
    user_schemas = [s for s in all_schemas if s not in blocked]
    return user_schemas or [insp.default_schema_name]


def _safe_row_count(db_engine: Engine, table_name: str, schema: Optional[str]) -> Optional[int]:
    preparer = db_engine.dialect.identifier_preparer
    quoted_table = preparer.quote(table_name)
    qualified = quoted_table
    if schema:
        qualified = f"{preparer.quote(schema)}.{quoted_table}"

    query = text(f"SELECT COUNT(*) AS row_count FROM {qualified}")
    try:
        with db_engine.connect() as conn:
            row = conn.execute(query).first()
        if not row:
            return None
        return int(row[0])
    except Exception:
        return None


def get_schema_metadata(db_engine: Engine) -> Dict[str, Any]:
    insp = inspect(db_engine)
    tables: List[Dict[str, Any]] = []

    for schema in _iter_user_schemas(db_engine):
        table_names = insp.get_table_names(schema=schema)
        for table_name in table_names:
            columns_info = []
            for col in insp.get_columns(table_name, schema=schema):
                columns_info.append(
                    {
                        "name": col.get("name"),
                        "type": str(col.get("type")),
                        "nullable": bool(col.get("nullable", True)),
                        "default": col.get("default"),
                    }
                )

            pk = insp.get_pk_constraint(table_name, schema=schema) or {}
            fks_raw = insp.get_foreign_keys(table_name, schema=schema) or []
            indexes_raw = insp.get_indexes(table_name, schema=schema) or []

            foreign_keys = []
            for fk in fks_raw:
                foreign_keys.append(
                    {
                        "name": fk.get("name"),
                        "constrained_columns": fk.get("constrained_columns", []),
                        "referred_schema": fk.get("referred_schema"),
                        "referred_table": fk.get("referred_table"),
                        "referred_columns": fk.get("referred_columns", []),
                    }
                )

            indexes = []
            for idx in indexes_raw:
                indexes.append(
                    {
                        "name": idx.get("name"),
                        "column_names": idx.get("column_names", []),
                        "unique": bool(idx.get("unique", False)),
                    }
                )

            tables.append(
                {
                    "schema": schema,
                    "table_name": table_name,
                    "columns": columns_info,
                    "primary_key": {
                        "name": pk.get("name"),
                        "constrained_columns": pk.get("constrained_columns", []),
                    },
                    "foreign_keys": foreign_keys,
                    "indexes": indexes,
                    "row_count": _safe_row_count(db_engine, table_name, schema),
                }
            )

    return {
        "dialect": db_engine.dialect.name,
        "database": db_engine.url.database,
        "tables": tables,
    }


def export_schema_as_ddl(db_engine: Engine, output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    metadata = MetaData()
    ddl_files: List[str] = []

    for schema in _iter_user_schemas(db_engine):
        insp = inspect(db_engine)
        for table_name in insp.get_table_names(schema=schema):
            table = Table(table_name, metadata, schema=schema, autoload_with=db_engine)
            ddl_sql = str(CreateTable(table).compile(dialect=db_engine.dialect)).strip() + ";\n"

            safe_name = f"{schema}__{table_name}" if schema else table_name
            path = os.path.join(output_dir, f"{safe_name}.sql")
            with open(path, "w", encoding="utf-8") as f:
                f.write(ddl_sql)
            ddl_files.append(path)

    return ddl_files


def export_schema_as_corpus_text(db_engine: Engine, metadata: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"Database dialect: {db_engine.dialect.name}")
    lines.append(f"Database name: {db_engine.url.database}")

    for table in metadata.get("tables", []):
        schema = table.get("schema")
        table_name = table.get("table_name")
        lines.append("")
        lines.append(f"Table: {schema + '.' if schema else ''}{table_name}")
        lines.append(f"Approx row count: {table.get('row_count')}")

        pk_cols = table.get("primary_key", {}).get("constrained_columns", [])
        if pk_cols:
            lines.append(f"Primary key: {', '.join(pk_cols)}")

        lines.append("Columns:")
        for col in table.get("columns", []):
            default_val = col.get("default")
            default_text = json.dumps(default_val) if default_val is not None else "null"
            lines.append(
                "- "
                f"{col.get('name')} ({col.get('type')}) "
                f"nullable={col.get('nullable')} default={default_text}"
            )

        fks = table.get("foreign_keys", [])
        if fks:
            lines.append("Foreign keys:")
            for fk in fks:
                src = ",".join(fk.get("constrained_columns", []))
                tgt_schema = fk.get("referred_schema")
                tgt_table = fk.get("referred_table")
                tgt_cols = ",".join(fk.get("referred_columns", []))
                target = f"{tgt_schema + '.' if tgt_schema else ''}{tgt_table}({tgt_cols})"
                lines.append(f"- {src} -> {target}")

        idxs = table.get("indexes", [])
        if idxs:
            lines.append("Indexes:")
            for idx in idxs:
                cols = ", ".join(idx.get("column_names", []))
                lines.append(f"- {idx.get('name')}: ({cols}) unique={idx.get('unique')}")

    return "\n".join(lines).strip() + "\n"
