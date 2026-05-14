import json
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


def extract_text(file_path: str, ext: str) -> str:
    """Backward-compatible text extraction wrapper.

    Existing pipeline stages still consume plain text; this delegates to the
    adapter-based corpus extractor and returns its plain_text field.
    """
    corpus = extract_corpus(file_path, ext)
    return corpus.get("plain_text", "")


def extract_corpus(file_path: str, ext: str) -> Dict:
    normalized_ext = _normalize_ext(ext)
    adapter = _adapter_registry().get(normalized_ext, _txt_adapter)

    try:
        corpus = adapter(file_path)
        plain_text = (corpus.get("plain_text") or "").strip()
        if plain_text:
            return corpus

        logger.warning("Primary adapter returned empty text for %s; using fallback decode", file_path)
        return _raw_fallback_adapter(file_path)
    except Exception as e:
        logger.error("Corpus extraction failed for %s: %s", file_path, e)
        return _raw_fallback_adapter(file_path)


def _normalize_ext(ext: str) -> str:
    return (ext or "txt").lower().lstrip(".")


def _adapter_registry() -> Dict[str, Callable[[str], Dict]]:
    return {
        "pdf": _pdf_adapter,
        "docx": _docx_adapter,
        "txt": _txt_adapter,
        "csv": _csv_adapter,
        "xlsx": _excel_adapter,
        "xls": _excel_adapter,
        "json": _json_adapter,
    }


def _base_corpus(source_type: str, adapter: str) -> Dict:
    return {
        "source_type": source_type,
        "adapter": adapter,
        "plain_text": "",
        "text_blocks": [],
        "table_rows": [],
        "metadata": {},
    }


def _pdf_adapter(path: str) -> Dict:
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass

    corpus = _base_corpus("document", "pdf")
    for page_idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            corpus["text_blocks"].append({
                "block_id": f"page_{page_idx}",
                "text": text,
                "page": page_idx,
            })

    corpus["plain_text"] = "\n\n".join(block["text"] for block in corpus["text_blocks"])
    corpus["metadata"] = {
        "page_count": len(reader.pages),
        "text_block_count": len(corpus["text_blocks"]),
    }
    return corpus


def _docx_adapter(path: str) -> Dict:
    from docx import Document

    doc = Document(path)
    corpus = _base_corpus("document", "docx")
    for idx, para in enumerate(doc.paragraphs, start=1):
        text = (para.text or "").strip()
        if text:
            corpus["text_blocks"].append({
                "block_id": f"paragraph_{idx}",
                "text": text,
                "paragraph": idx,
            })

    corpus["plain_text"] = "\n".join(block["text"] for block in corpus["text_blocks"])
    corpus["metadata"] = {
        "paragraph_count": len(corpus["text_blocks"]),
    }
    return corpus


def _txt_adapter(path: str) -> Dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    corpus = _base_corpus("document", "txt")
    corpus["text_blocks"] = [{"block_id": "full_text", "text": text.strip()}]
    corpus["plain_text"] = text
    corpus["metadata"] = {
        "char_count": len(text),
    }
    return corpus


def _csv_adapter(path: str) -> Dict:
    import pandas as pd

    df = pd.read_csv(path)
    return _table_corpus_from_dataframe(df, adapter="csv", table_id="csv_main")


def _excel_adapter(path: str) -> Dict:
    import pandas as pd

    sheets = pd.read_excel(path, sheet_name=None)
    corpus = _base_corpus("table", "excel")
    plain_parts: List[str] = []
    total_rows = 0

    for name, df in sheets.items():
        table_corpus = _table_corpus_from_dataframe(df, adapter="excel", table_id=f"sheet::{name}")
        plain_parts.append(f"Sheet: {name}\n{table_corpus['plain_text']}")
        corpus["table_rows"].extend(table_corpus["table_rows"])
        total_rows += table_corpus["metadata"].get("row_count", 0)

    corpus["plain_text"] = "\n\n".join(plain_parts)
    corpus["metadata"] = {
        "sheet_count": len(sheets),
        "row_count": total_rows,
    }
    return corpus


def _json_adapter(path: str) -> Dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        payload = json.load(f)

    corpus = _base_corpus("json", "json")

    if isinstance(payload, list) and payload and all(isinstance(x, dict) for x in payload):
        import pandas as pd

        df = pd.DataFrame(payload)
        table_corpus = _table_corpus_from_dataframe(df, adapter="json", table_id="json_records")
        corpus["table_rows"] = table_corpus["table_rows"]
        corpus["plain_text"] = table_corpus["plain_text"]
        corpus["metadata"] = {
            "record_count": len(payload),
            "as_table": True,
        }
        return corpus

    pretty = json.dumps(payload, ensure_ascii=True, indent=2)
    corpus["text_blocks"] = [{"block_id": "json_pretty", "text": pretty}]
    corpus["plain_text"] = pretty
    corpus["metadata"] = {
        "record_count": len(payload) if isinstance(payload, list) else 1,
        "as_table": False,
    }
    return corpus


def _table_corpus_from_dataframe(df, adapter: str, table_id: str) -> Dict:
    corpus = _base_corpus("table", adapter)

    normalized = df.where(df.notna(), None)
    columns = [str(c) for c in normalized.columns.tolist()]
    row_records = normalized.to_dict(orient="records")

    rows: List[Dict] = []
    for ridx, row in enumerate(row_records):
        typed_cells: Dict[str, Dict] = {}
        for col in columns:
            value = row.get(col)
            typed_cells[col] = {
                "value": value,
                "value_type": _infer_type(value),
            }
        rows.append({
            "table_id": table_id,
            "row_idx": ridx,
            "cells": typed_cells,
        })

    corpus["table_rows"] = rows
    corpus["plain_text"] = _table_rows_to_text(rows)
    corpus["metadata"] = {
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
    }
    return corpus


def _table_rows_to_text(rows: List[Dict]) -> str:
    lines: List[str] = []
    for row in rows:
        parts: List[str] = []
        for col, payload in row.get("cells", {}).items():
            value = payload.get("value")
            if value is None:
                continue
            parts.append(f"{col}={value}")
        lines.append(
            f"table {row.get('table_id')} row {row.get('row_idx')}: " + "; ".join(parts)
        )
    return "\n".join(lines)


def _infer_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def _raw_fallback_adapter(path: str) -> Dict:
    corpus = _base_corpus("binary_fallback", "raw_decode")
    try:
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            text = raw.decode("latin-1", errors="ignore").strip()
        corpus["plain_text"] = text
        corpus["text_blocks"] = [{"block_id": "raw_decode", "text": text}]
        corpus["metadata"] = {
            "byte_count": len(raw),
            "fallback": True,
        }
    except Exception as e:
        logger.error("Fallback raw decode failed for %s: %s", path, e)
        corpus["metadata"] = {"fallback": True, "error": str(e)}
    return corpus
