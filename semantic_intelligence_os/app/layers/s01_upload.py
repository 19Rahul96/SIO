"""Step 1 — File Upload + Lineage Registration.

WHY: every downstream trust signal must trace back to an immutable source record.
PRODUCES: a source record (fingerprint, tags, source type) and a lineage entry.
ORDERING: first — nothing can be ingested without an identity + lineage anchor.
ENABLES: provenance/citations in every later layer and dedup on re-upload.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..storage.jsonstore import read_json, write_json

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls", ".json"}


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def register_source(
    *,
    filename: str,
    raw: bytes,
    role: str = "",
    domain: str = "",
    parent_source_id: str | None = None,
) -> dict:
    """Persist the raw file, compute a fingerprint and register lineage.

    Returns the source record. Duplicate fingerprints are flagged but not rejected
    (additive, non-blocking) so callers decide policy.
    """
    ext = Path(filename).suffix.lower()
    fp = _fingerprint(raw)
    source_id = uuid.uuid4().hex[:12]

    # Dedup scan across existing source records.
    duplicate_of = None
    sources_dir = settings.dir("sources")
    for rec_path in sources_dir.glob("*.json"):
        rec = read_json(rec_path, {})
        if rec.get("fingerprint") == fp:
            duplicate_of = rec.get("source_id")
            break

    stored = settings.dir("sources") / f"{source_id}{ext}"
    stored.write_bytes(raw)

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "source_id": source_id,
        "filename": filename,
        "ext": ext,
        "supported": ext in SUPPORTED_EXTS,
        "fingerprint": fp,
        "size_bytes": len(raw),
        "stored_path": str(stored),
        "tags": {"role": role, "domain": domain},
        "duplicate_of": duplicate_of,
        "uploaded_at": now,
    }
    write_json(sources_dir / f"{source_id}.json", record)

    lineage = {
        "source_id": source_id,
        "fingerprint": fp,
        "parent_source_id": parent_source_id,
        "derived": [],
        "events": [{"stage": "upload", "at": now, "detail": filename}],
    }
    write_json(settings.dir("lineage") / f"{source_id}.json", lineage)
    return record


def append_lineage(source_id: str, stage: str, detail: str = "") -> None:
    path = settings.dir("lineage") / f"{source_id}.json"
    lineage = read_json(path, None)
    if lineage is None:
        return
    lineage["events"].append(
        {"stage": stage, "at": datetime.now(timezone.utc).isoformat(), "detail": detail}
    )
    write_json(path, lineage)
