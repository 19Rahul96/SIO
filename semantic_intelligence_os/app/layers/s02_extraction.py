"""Step 2 — Ingestion & Extraction Engine (with parser-confidence + lineage).

WHY: convert heterogeneous raw files into one machine-readable corpus contract.
PRODUCES: a corpus {plain_text, text_blocks, table_rows, metadata} + parser confidence.
ORDERING: must run after upload, before any cleaning/segmentation.
ENABLES: every text/table-based layer downstream; OCR/parser confidence feeds Step 9.
"""
from __future__ import annotations

from pathlib import Path

from ..contracts.audit import make_audit


def _alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    alnum = sum(c.isalnum() or c.isspace() for c in text)
    return alnum / max(1, len(text))


def _extract_pdf(path: Path) -> dict:
    blocks, text = [], []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages):
            t = page.extract_text() or ""
            blocks.append({"kind": "page", "idx": i, "text": t, "confidence": _alnum_ratio(t)})
            text.append(t)
    except Exception as exc:  # pragma: no cover
        return {"plain_text": "", "text_blocks": [], "table_rows": [], "error": str(exc)}
    return {"plain_text": "\n".join(text), "text_blocks": blocks, "table_rows": []}


def _extract_docx(path: Path) -> dict:
    try:
        import docx

        doc = docx.Document(str(path))
        blocks = [
            {"kind": "paragraph", "idx": i, "text": p.text, "confidence": 1.0}
            for i, p in enumerate(doc.paragraphs)
            if p.text.strip()
        ]
        return {
            "plain_text": "\n".join(b["text"] for b in blocks),
            "text_blocks": blocks,
            "table_rows": [],
        }
    except Exception as exc:  # pragma: no cover
        return {"plain_text": "", "text_blocks": [], "table_rows": [], "error": str(exc)}


def _extract_table(path: Path, ext: str) -> dict:
    try:
        import pandas as pd

        df = pd.read_csv(path) if ext == ".csv" else pd.read_excel(path)
        rows, blocks = [], []
        for r, (_, row) in enumerate(df.iterrows()):
            cells = {str(k): ("" if pd.isna(v) else v) for k, v in row.items()}
            rows.append({"row": r, "cells": cells})
            flat = "; ".join(f"{k}={v}" for k, v in cells.items())
            blocks.append({"kind": "row", "idx": r, "text": flat, "confidence": 1.0})
        return {
            "plain_text": "\n".join(b["text"] for b in blocks),
            "text_blocks": blocks,
            "table_rows": rows,
            "columns": [str(c) for c in df.columns],
        }
    except Exception as exc:  # pragma: no cover
        return {"plain_text": "", "text_blocks": [], "table_rows": [], "error": str(exc)}


def _extract_text(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # pragma: no cover
        raw = path.read_text(encoding="latin-1", errors="ignore")
    return {
        "plain_text": raw,
        "text_blocks": [{"kind": "text", "idx": 0, "text": raw, "confidence": 1.0}],
        "table_rows": [],
    }


def extract_corpus(source: dict) -> dict:
    """Dispatch by extension and attach a parser-confidence audit block."""
    path = Path(source["stored_path"])
    ext = source["ext"]
    if ext == ".pdf":
        corpus = _extract_pdf(path)
    elif ext == ".docx":
        corpus = _extract_docx(path)
    elif ext in (".csv", ".xlsx", ".xls"):
        corpus = _extract_table(path, ext)
    else:  # .txt, .md, .json and fallback
        corpus = _extract_text(path)

    blocks = corpus.get("text_blocks", [])
    confidences = [b.get("confidence", 1.0) for b in blocks] or [0.0]
    parser_conf = sum(confidences) / len(confidences)
    needs_ocr = ext == ".pdf" and parser_conf < 0.4

    corpus.update(
        {
            "source_id": source["source_id"],
            "source_type": ext.lstrip("."),
            "block_count": len(blocks),
            "table_row_count": len(corpus.get("table_rows", [])),
            "needs_ocr": needs_ocr,
            "audit": make_audit(
                score=parser_conf,
                scorer="parser_confidence",
                stage="extraction",
                action="review_required" if needs_ocr else "auto_accept",
                reason="low parser confidence; OCR recommended" if needs_ocr else "",
                evidence={"avg_block_confidence": round(parser_conf, 4), "blocks": len(blocks)},
            ),
        }
    )
    return corpus
