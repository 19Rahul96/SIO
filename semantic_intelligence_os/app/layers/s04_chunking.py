"""Step 4 — Chunking + Structural Segmentation.

WHY: create semantically meaningful, provenance-carrying processing units.
PRODUCES: chunks with lineage (source/block idx) + a coverage validation report.
ORDERING: after normalization, before extraction — extraction is chunk-grounded.
ENABLES: chunk-grounded entities/relations, retrieval, and citation back-references.

Strategies: table-aware (one chunk per row group) when table_rows present, else a
word-window fallback. Both preserve start/end offsets so coverage can be validated.
"""
from __future__ import annotations

from ..config import settings


def _window_chunks(text: str) -> list[dict]:
    words = text.split()
    size, overlap = settings.chunk_size_words, settings.chunk_overlap_words
    step = max(1, size - overlap)
    chunks = []
    for idx, start in enumerate(range(0, max(1, len(words)), step)):
        window = words[start : start + size]
        if not window:
            break
        chunks.append(
            {
                "idx": idx,
                "text": " ".join(window),
                "start_word": start,
                "end_word": start + len(window),
                "word_count": len(window),
                "strategy": "word_window",
            }
        )
        if start + size >= len(words):
            break
    return chunks


def _table_chunks(corpus: dict, rows_per_chunk: int = 25) -> list[dict]:
    blocks = [b for b in corpus.get("text_blocks", []) if b.get("kind") == "row"]
    chunks = []
    for idx, start in enumerate(range(0, len(blocks), rows_per_chunk)):
        group = blocks[start : start + rows_per_chunk]
        text = "\n".join(b["text"] for b in group)
        chunks.append(
            {
                "idx": idx,
                "text": text,
                "start_word": start,
                "end_word": start + len(group),
                "word_count": len(text.split()),
                "strategy": "table_aware",
            }
        )
    return chunks


def chunk_corpus(corpus: dict) -> dict:
    if corpus.get("table_rows"):
        chunks = _table_chunks(corpus)
        total_units = len(corpus["table_rows"])
        covered = sum(c["end_word"] - c["start_word"] for c in chunks)
    else:
        text = corpus.get("plain_text", "")
        chunks = _window_chunks(text)
        total_units = len(text.split())
        covered = len({w for c in chunks for w in range(c["start_word"], c["end_word"])})

    coverage = (covered / total_units) if total_units else 0.0
    report = {
        "chunk_count": len(chunks),
        "total_units": total_units,
        "covered_units": covered,
        "coverage_pct": round(min(1.0, coverage) * 100, 2),
        "data_loss_suspected": coverage < 0.98 and total_units > 0,
        "strategy": chunks[0]["strategy"] if chunks else "none",
    }
    return {"source_id": corpus["source_id"], "chunks": chunks, "validation": report}
