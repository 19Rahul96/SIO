"""Extraction observability — parser/OCR confidence + per-chunk lineage (Section 7).

Assembles a queryable lineage table from the corpus (s02), chunks (s04) and entity
chunk-groundings (s06). For PDF sources it also derives page-level confidence /
OCR-noise regions from the per-page block confidences produced in s02.
"""
from __future__ import annotations


def build(source: dict, corpus: dict, chunked: dict, extraction: dict) -> dict:
    blocks = corpus.get("text_blocks", [])
    source_type = corpus.get("source_type", source.get("ext", "").lstrip("."))
    is_pdf = source_type == "pdf"

    # --- PDF / OCR quality from per-page block confidences ---
    page_confidence, ocr_noise = [], []
    if is_pdf:
        for b in blocks:
            if b.get("kind") != "page":
                continue
            conf = round(float(b.get("confidence", 0.0)), 4)
            page_confidence.append({"page": b.get("idx"), "confidence": conf, "char_count": len(b.get("text", ""))})
            if conf < 0.45:
                ocr_noise.append({"page": b.get("idx"), "confidence": conf, "reason": "low_extraction_confidence"})

    # --- Per-chunk lineage rows ---
    # entity_count per chunk via chunk_idxs grounding.
    ent_by_chunk: dict[int, int] = {}
    for e in extraction.get("entities", []):
        for ci in e.get("chunk_idxs", []):
            ent_by_chunk[ci] = ent_by_chunk.get(ci, 0) + 1

    block_confs = [b.get("confidence", 1.0) for b in blocks] or [1.0]
    parser_conf = round(sum(block_confs) / len(block_confs), 4)

    rows = []
    for c in chunked.get("chunks", []):
        idx = c["idx"]
        is_table = c.get("strategy") == "table_aware"
        conf = 1.0 if is_table else parser_conf
        ecount = ent_by_chunk.get(idx, 0)
        warnings = []
        if conf < 0.6:
            warnings.append("low_parser_confidence")
        if ecount == 0:
            warnings.append("no_entities_extracted")
        rows.append({
            "chunk_id": idx,
            "source_file": source.get("filename"),
            "adapter": source_type,
            "confidence": round(conf, 4),
            "page_or_row": (f"rows {c['start_word']}-{c['end_word']}" if is_table else f"words {c['start_word']}-{c['end_word']}"),
            "entity_count": ecount,
            "warnings": warnings,
        })

    return {
        "source_id": source["source_id"],
        "source_file": source.get("filename"),
        "adapter": source_type,
        "parser_confidence": parser_conf,
        "needs_ocr": bool(corpus.get("needs_ocr")),
        "pdf_quality": {
            "pdf_enabled": is_pdf,
            "page_confidence": page_confidence,
            "ocr_noise_regions": ocr_noise[:200],
        },
        "lineage": rows,
    }
