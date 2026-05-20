import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

DICTIONARY_PATH = "data/data_dictionary.json"

VALID_STATUSES = {"draft", "reviewed", "approved", "deprecated"}


def _default_store() -> Dict[str, Any]:
    return {
        "version": 1,
        "tables": {},
        "columns": {},
        "reviews": [],
        "history": [],
        "updated_at": None,
    }


def _load_store() -> Dict[str, Any]:
    if not os.path.exists(DICTIONARY_PATH):
        return _default_store()
    try:
        with open(DICTIONARY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_store()
        data.setdefault("version", 1)
        data.setdefault("tables", {})
        data.setdefault("columns", {})
        data.setdefault("reviews", [])
        data.setdefault("history", [])
        data.setdefault("updated_at", None)
        return data
    except Exception:
        return _default_store()


def _save_store(store: Dict[str, Any]) -> None:
    store["updated_at"] = time.time()
    os.makedirs(os.path.dirname(DICTIONARY_PATH), exist_ok=True)
    with open(DICTIONARY_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f)


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _table_key(schema: Optional[str], table_name: str) -> str:
    return f"{schema}.{table_name}" if schema else table_name


def _column_key(schema: Optional[str], table_name: str, column_name: str) -> str:
    tkey = _table_key(schema, table_name)
    return f"{tkey}.{column_name}"


def _derive_table_definition(table_name: str, semantic_label: str, columns: List[Dict[str, Any]]) -> str:
    label = semantic_label or "unknown"
    return (
        f"{table_name} acts as a {label} table inferred from schema and column semantic patterns "
        f"across {len(columns)} columns."
    )


def _derive_column_definition(table_name: str, column_name: str, semantic_label: str) -> str:
    label = semantic_label or "unknown"
    return f"{column_name} in {table_name} represents {label} data inferred from profiling and sample values."


def _transition_status(current: str, semantic_changed: bool) -> str:
    if current == "approved" and semantic_changed:
        return "reviewed"
    if current == "reviewed" and semantic_changed:
        return "draft"
    if current in VALID_STATUSES:
        return current
    return "draft"


def _entry_snapshot(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entry_id": entry.get("entry_id"),
        "entry_type": entry.get("entry_type"),
        "key": entry.get("key"),
        "semantic_label": entry.get("semantic_label"),
        "semantic_confidence": entry.get("semantic_confidence"),
        "lifecycle_status": entry.get("lifecycle_status"),
        "version": entry.get("version"),
    }


def upsert_from_profile(db_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    store = _load_store()
    tables = store.get("tables", {})
    columns = store.get("columns", {})

    tables_created = 0
    tables_updated = 0
    columns_created = 0
    columns_updated = 0

    for table in profile.get("tables", []):
        schema = table.get("schema")
        table_name = table.get("table_name")
        if not table_name:
            continue

        tkey = _table_key(schema, table_name)
        semantic_label = table.get("table_semantic_label", "unknown")
        semantic_confidence = float(table.get("table_semantic_confidence", 0.0) or 0.0)
        semantic_method = table.get("table_semantic_inference_method", "heuristic")

        existing = tables.get(tkey)
        semantic_changed = bool(existing) and existing.get("semantic_label") != semantic_label
        if not existing:
            existing = {
                "entry_id": f"ddt_{uuid.uuid4().hex[:12]}",
                "entry_type": "table",
                "schema": schema,
                "table_name": table_name,
                "key": tkey,
                "lifecycle_status": "draft",
                "source_db_ids": [],
                "created_at": time.time(),
                "version": 0,
            }
            tables_created += 1
        else:
            tables_updated += 1

        existing["semantic_label"] = semantic_label
        existing["semantic_confidence"] = round(semantic_confidence, 4)
        existing["semantic_method"] = semantic_method
        existing["business_definition"] = _derive_table_definition(table_name, semantic_label, table.get("columns", []))
        existing["lifecycle_status"] = _transition_status(existing.get("lifecycle_status", "draft"), semantic_changed)
        existing["source_db_ids"] = sorted(set(existing.get("source_db_ids", []) + [db_id]))
        existing["last_profiled_at"] = time.time()
        existing["version"] = int(existing.get("version", 0)) + 1
        existing["updated_at"] = time.time()
        tables[tkey] = existing

        for col in table.get("columns", []):
            col_name = col.get("column") or col.get("name")
            if not col_name:
                continue

            ckey = _column_key(schema, table_name, col_name)
            c_semantic = col.get("semantic_label", "unknown")
            c_conf = float(col.get("semantic_confidence", 0.0) or 0.0)
            c_method = col.get("semantic_inference_method", "heuristic")

            c_existing = columns.get(ckey)
            c_changed = bool(c_existing) and c_existing.get("semantic_label") != c_semantic
            if not c_existing:
                c_existing = {
                    "entry_id": f"ddc_{uuid.uuid4().hex[:12]}",
                    "entry_type": "column",
                    "schema": schema,
                    "table_name": table_name,
                    "column_name": col_name,
                    "key": ckey,
                    "table_key": tkey,
                    "lifecycle_status": "draft",
                    "source_db_ids": [],
                    "created_at": time.time(),
                    "version": 0,
                }
                columns_created += 1
            else:
                columns_updated += 1

            c_existing["semantic_label"] = c_semantic
            c_existing["semantic_confidence"] = round(c_conf, 4)
            c_existing["semantic_method"] = c_method
            c_existing["business_definition"] = _derive_column_definition(table_name, col_name, c_semantic)
            c_existing["null_pct"] = col.get("null_pct")
            c_existing["cardinality"] = col.get("cardinality")
            c_existing["sample_values"] = col.get("sample_values", [])[:10]
            c_existing["lifecycle_status"] = _transition_status(c_existing.get("lifecycle_status", "draft"), c_changed)
            c_existing["source_db_ids"] = sorted(set(c_existing.get("source_db_ids", []) + [db_id]))
            c_existing["last_profiled_at"] = time.time()
            c_existing["version"] = int(c_existing.get("version", 0)) + 1
            c_existing["updated_at"] = time.time()
            columns[ckey] = c_existing

    store["tables"] = tables
    store["columns"] = columns
    store.setdefault("history", []).append(
        {
            "db_id": db_id,
            "event": "upsert_from_profile",
            "tables_created": tables_created,
            "tables_updated": tables_updated,
            "columns_created": columns_created,
            "columns_updated": columns_updated,
            "at": time.time(),
        }
    )
    _save_store(store)

    return {
        "tables_created": tables_created,
        "tables_updated": tables_updated,
        "columns_created": columns_created,
        "columns_updated": columns_updated,
        "table_count": len(tables),
        "column_count": len(columns),
    }


def list_table_entries(query: Optional[str] = None, status: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    store = _load_store()
    rows = list(store.get("tables", {}).values())
    if status:
        rows = [r for r in rows if r.get("lifecycle_status") == status]
    if query:
        q = _normalize_text(query)
        rows = [
            r
            for r in rows
            if q in _normalize_text(r.get("table_name", ""))
            or q in _normalize_text(r.get("business_definition", ""))
            or q in _normalize_text(r.get("semantic_label", ""))
        ]
    rows.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    rows = rows[: max(1, min(limit, 1000))]
    return {"count": len(rows), "tables": rows}


def list_column_entries(
    query: Optional[str] = None,
    status: Optional[str] = None,
    table_key: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    store = _load_store()
    rows = list(store.get("columns", {}).values())
    if status:
        rows = [r for r in rows if r.get("lifecycle_status") == status]
    if table_key:
        rows = [r for r in rows if r.get("table_key") == table_key]
    if query:
        q = _normalize_text(query)
        rows = [
            r
            for r in rows
            if q in _normalize_text(r.get("column_name", ""))
            or q in _normalize_text(r.get("business_definition", ""))
            or q in _normalize_text(r.get("semantic_label", ""))
        ]
    rows.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    rows = rows[: max(1, min(limit, 2000))]
    return {"count": len(rows), "columns": rows}


def get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    store = _load_store()
    for entry in store.get("tables", {}).values():
        if entry.get("entry_id") == entry_id:
            return entry
    for entry in store.get("columns", {}).values():
        if entry.get("entry_id") == entry_id:
            return entry
    return None


def review_entry(entry_id: str, decision: str, decided_by: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    store = _load_store()
    decision_norm = (decision or "").strip().lower()
    target_status = {
        "approve": "approved",
        "approved": "approved",
        "review": "reviewed",
        "reviewed": "reviewed",
        "deprecate": "deprecated",
        "deprecated": "deprecated",
        "draft": "draft",
    }.get(decision_norm)

    if not target_status:
        return {"ok": False, "error": "invalid_decision"}

    entry = None
    entry_type = None
    entry_key = None

    for key, val in store.get("tables", {}).items():
        if val.get("entry_id") == entry_id:
            entry = val
            entry_type = "table"
            entry_key = key
            break
    if entry is None:
        for key, val in store.get("columns", {}).items():
            if val.get("entry_id") == entry_id:
                entry = val
                entry_type = "column"
                entry_key = key
                break

    if entry is None:
        return {"ok": False, "error": "entry_not_found"}

    before = _entry_snapshot(entry)
    entry["lifecycle_status"] = target_status
    entry["reviewed_by"] = decided_by or "api"
    entry["review_notes"] = notes or ""
    entry["reviewed_at"] = time.time()
    entry["updated_at"] = time.time()
    entry["version"] = int(entry.get("version", 0)) + 1

    if entry_type == "table":
        store["tables"][entry_key] = entry
    else:
        store["columns"][entry_key] = entry

    review_record = {
        "review_id": f"ddr_{uuid.uuid4().hex[:10]}",
        "entry_id": entry_id,
        "entry_type": entry_type,
        "decision": target_status,
        "decided_by": decided_by or "api",
        "notes": notes or "",
        "at": time.time(),
    }
    store.setdefault("reviews", []).append(review_record)
    store.setdefault("history", []).append(
        {
            "event": "review_entry",
            "entry_id": entry_id,
            "before": before,
            "after": _entry_snapshot(entry),
            "review_id": review_record["review_id"],
            "at": time.time(),
        }
    )
    _save_store(store)
    return {"ok": True, "entry": entry, "review": review_record}


def dictionary_metrics() -> Dict[str, Any]:
    store = _load_store()
    tables = list(store.get("tables", {}).values())
    columns = list(store.get("columns", {}).values())

    table_status_counts: Dict[str, int] = {s: 0 for s in VALID_STATUSES}
    col_status_counts: Dict[str, int] = {s: 0 for s in VALID_STATUSES}

    for row in tables:
        st = row.get("lifecycle_status", "draft")
        table_status_counts[st] = table_status_counts.get(st, 0) + 1
    for row in columns:
        st = row.get("lifecycle_status", "draft")
        col_status_counts[st] = col_status_counts.get(st, 0) + 1

    approved_cols = col_status_counts.get("approved", 0)
    approved_tables = table_status_counts.get("approved", 0)

    return {
        "table_count": len(tables),
        "column_count": len(columns),
        "table_status_counts": table_status_counts,
        "column_status_counts": col_status_counts,
        "approved_table_pct": round((approved_tables / max(1, len(tables))) * 100, 2),
        "approved_column_pct": round((approved_cols / max(1, len(columns))) * 100, 2),
        "review_count": len(store.get("reviews", [])),
        "updated_at": store.get("updated_at"),
    }
