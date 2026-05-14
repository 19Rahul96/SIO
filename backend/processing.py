import json
import os
import re
import time
import logging
from typing import List, Dict, Optional

from ingestion import extract_corpus
from entity_extraction import extract_entities_from_chunks
from entity_resolution import resolve_canonical_graph
from graph_builder import GraphBuilder
from knowledge_schema import build_canonical_edges, build_canonical_nodes, validate_canonical_graph
from wiki_builder import WikiBuilder

logger = logging.getLogger(__name__)

PROCESSED_DIR = "data/processed"
_graph_builder = GraphBuilder()
_wiki_builder = WikiBuilder()


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def chunk_text(text: str, size: int = 400, overlap: int = 60) -> List[Dict]:
    words = text.split()
    chunks: List[Dict] = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append({
            "idx": idx,
            "text": " ".join(words[start:end]),
            "start_word": start,
            "end_word": end,
            "word_count": max(0, end - start),
        })
        start += size - overlap
        idx += 1
    return chunks


def validate_chunking(chunks: List[Dict], total_words: int, target_overlap: int) -> Dict:
    if total_words <= 0:
        return {
            "total_words": 0,
            "chunk_count": len(chunks),
            "covered_words": 0,
            "coverage_pct": 0.0,
            "target_overlap_words": target_overlap,
            "adjacent_pairs_checked": 0,
            "overlap_correct_pairs": 0,
            "overlap_correctness_pct": 0.0,
            "min_overlap_words": 0,
            "max_overlap_words": 0,
            "data_loss_detected": False,
        }

    # Interval-union coverage to avoid large in-memory per-word sets.
    intervals = sorted(
        [(max(0, c.get("start_word", 0)), min(total_words, c.get("end_word", 0))) for c in chunks],
        key=lambda x: x[0],
    )
    covered = 0
    if intervals:
        s, e = intervals[0]
        for ns, ne in intervals[1:]:
            if ns <= e:
                e = max(e, ne)
            else:
                covered += max(0, e - s)
                s, e = ns, ne
        covered += max(0, e - s)

    overlaps: List[int] = []
    correct_pairs = 0
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        curr = chunks[i]
        prev_start = prev.get("start_word", 0)
        prev_end = prev.get("end_word", 0)
        curr_start = curr.get("start_word", 0)
        curr_end = curr.get("end_word", 0)
        actual_overlap = max(0, prev_end - curr_start)
        overlaps.append(actual_overlap)

        prev_len = max(0, prev_end - prev_start)
        curr_len = max(0, curr_end - curr_start)
        expected_overlap = min(target_overlap, prev_len, curr_len)
        if actual_overlap == expected_overlap:
            correct_pairs += 1

    pairs = max(0, len(chunks) - 1)
    overlap_pct = round((correct_pairs / pairs) * 100, 2) if pairs else 100.0
    coverage_pct = round((covered / total_words) * 100, 2) if total_words else 0.0

    return {
        "total_words": total_words,
        "chunk_count": len(chunks),
        "covered_words": covered,
        "coverage_pct": coverage_pct,
        "target_overlap_words": target_overlap,
        "adjacent_pairs_checked": pairs,
        "overlap_correct_pairs": correct_pairs,
        "overlap_correctness_pct": overlap_pct,
        "min_overlap_words": min(overlaps) if overlaps else 0,
        "max_overlap_words": max(overlaps) if overlaps else 0,
        "data_loss_detected": covered < total_words,
    }


def _corpus_profile(corpus: Dict) -> Dict:
    return {
        "source_type": corpus.get("source_type", "unknown"),
        "adapter": corpus.get("adapter", "unknown"),
        "text_block_count": len(corpus.get("text_blocks", [])),
        "table_row_count": len(corpus.get("table_rows", [])),
        "metadata": corpus.get("metadata", {}),
    }


def _write_status(file_id: str, updates: Dict):
    path = f"{PROCESSED_DIR}/{file_id}_status.json"
    try:
        with open(path) as f:
            data = json.load(f)
        data.update(updates)
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Status write failed for {file_id}: {e}")


def get_file_status(file_id: str) -> Optional[Dict]:
    path = f"{PROCESSED_DIR}/{file_id}_status.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def get_all_statuses() -> List[Dict]:
    out: List[Dict] = []
    if not os.path.exists(PROCESSED_DIR):
        return out
    for fname in os.listdir(PROCESSED_DIR):
        if fname.endswith("_status.json"):
            try:
                with open(f"{PROCESSED_DIR}/{fname}") as f:
                    status = json.load(f)

                # Normalize DB pipeline records so frontend can render them in
                # the same ingestion table without a separate endpoint.
                if status.get("db_id") and not status.get("file_id"):
                    status["file_id"] = status.get("db_id")
                if status.get("db_id") and not status.get("filename"):
                    engine = status.get("engine", "db")
                    database = status.get("database") or status.get("db_id", "")[:8]
                    status["filename"] = f"Database ({engine}) {database}"
                if status.get("db_id") and not status.get("ext"):
                    status["ext"] = "DB"
                if status.get("db_id") and "size" not in status:
                    status["size"] = 0

                out.append(status)
            except Exception:
                pass
    out.sort(key=lambda x: x.get("uploaded_at", 0), reverse=True)
    return out


def process_file_pipeline(file_id: str, file_path: str, ext: str, embedding_store):
    try:
        logger.info(f"Pipeline start: {file_id}")
        _write_status(file_id, {"status": "processing", "error": None})

        # 1. Extract
        corpus = extract_corpus(file_path, ext)
        text = corpus.get("plain_text", "")
        if not text.strip():
            _write_status(file_id, {"status": "failed", "error": "No text could be extracted"})
            return

        with open(f"{PROCESSED_DIR}/{file_id}_corpus.json", "w") as f:
            json.dump(corpus, f)

        corpus_profile = _corpus_profile(corpus)

        # 2. Clean
        text = clean_text(text)
        _write_status(file_id, {
            "status": "cleaned",
            "error": None,
            "corpus_profile": corpus_profile,
            "pipeline_steps": {
                "cleaned": True, "chunked": False,
                "entities_extracted": False, "graph_built": False, "indexed": False,
            },
        })
        time.sleep(0.3)

        # 3. Chunk
        chunks = chunk_text(text)
        total_words = len(text.split())
        chunk_validation_report = validate_chunking(chunks, total_words=total_words, target_overlap=60)
        _write_status(file_id, {
            "status": "chunked",
            "error": None,
            "chunks_count": len(chunks),
            "corpus_profile": corpus_profile,
            "chunk_validation_report": chunk_validation_report,
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": False, "graph_built": False, "indexed": False,
            },
        })
        time.sleep(0.3)

        # 4. Entity extraction
        # 4. Per-chunk entity extraction — every entity/relationship carries chunk_idx
        entities, relationships = extract_entities_from_chunks(chunks)

        canonical_nodes, mention_to_canonical = build_canonical_nodes(file_id, entities)
        canonical_edges = build_canonical_edges(file_id, relationships, mention_to_canonical)
        schema_validation = validate_canonical_graph(canonical_nodes, canonical_edges)
        resolution_result = resolve_canonical_graph(
            file_id=file_id,
            nodes=canonical_nodes,
            edges=canonical_edges,
            embed_fn=embedding_store.embed_text,
        )
        resolution_report = resolution_result.get("resolution_report", {})
        resolved_nodes = resolution_result.get("resolved_nodes", [])
        resolved_edges = resolution_result.get("resolved_edges", [])
        canonical_upsert = _graph_builder.upsert_canonical_graph(file_id, resolved_nodes, resolved_edges)
        touched_canonical_ids = sorted({n.get("canonical_id") for n in resolved_nodes if n.get("canonical_id")})
        canonical_graph = _graph_builder.get_canonical_graph()
        wiki_page_report = _wiki_builder.build_pages_for_nodes(file_id, touched_canonical_ids, canonical_graph)

        with open(f"{PROCESSED_DIR}/{file_id}_canonical.json", "w") as f:
            json.dump(
                {
                    "file_id": file_id,
                    "canonical_nodes": canonical_nodes,
                    "canonical_edges": canonical_edges,
                    "resolved_nodes": resolved_nodes,
                    "resolved_edges": resolved_edges,
                    "schema_validation": schema_validation,
                    "resolution_report": resolution_report,
                    "canonical_upsert": canonical_upsert,
                    "wiki_page_report": wiki_page_report,
                },
                f,
            )

        _write_status(file_id, {
            "status": "entities_extracted",
            "error": None,
            "entities_count": len(entities),
            "relations_count": len(relationships),
            "canonical_entities_count": len(canonical_nodes),
            "canonical_relations_count": len(canonical_edges),
            "corpus_profile": corpus_profile,
            "schema_validation": schema_validation,
            "resolution_report": {
                "merged_count": resolution_report.get("merged_count", 0),
                "created_count": resolution_report.get("created_count", 0),
                "pending_review_count": resolution_report.get("pending_review_count", 0),
                "registry_total_nodes": resolution_report.get("registry_total_nodes", 0),
            },
            "canonical_upsert": canonical_upsert,
            "wiki_page_report": {
                "pages_created": wiki_page_report.get("pages_created", 0),
                "pages_updated": wiki_page_report.get("pages_updated", 0),
                "total_target_nodes": wiki_page_report.get("total_target_nodes", 0),
            },
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": True, "graph_built": False, "indexed": False,
            },
        })
        time.sleep(0.3)

        # 5. Build graph
        _graph_builder.build_graph(file_id, entities, relationships)
        _write_status(file_id, {
            "status": "graph_built",
            "error": None,
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": True, "graph_built": True, "indexed": False,
            },
        })
        time.sleep(0.3)

        # 6. Embed & index
        _write_status(file_id, {
            "status": "indexing",
            "error": None,
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": True, "graph_built": True, "indexed": False,
            },
        })
        embedding_store.add_chunks(file_id, chunks)

        # 7. Save processed preview
        with open(f"{PROCESSED_DIR}/{file_id}_data.json", "w") as f:
            json.dump({
                "file_id": file_id,
                "text_preview": text[:500],
                "corpus_profile": corpus_profile,
                "table_rows_preview": corpus.get("table_rows", [])[:20],
                "text_blocks_preview": corpus.get("text_blocks", [])[:20],
                "chunks_count": len(chunks),
                "chunk_validation_report": chunk_validation_report,
                "entities": entities[:50],        # first-seen chunk_idx preserved
                "relationships": relationships[:100],
                "chunk_grounded": True,            # flag: graph elements are chunk-traceable
                "canonical_entities_count": len(canonical_nodes),
                "canonical_relations_count": len(canonical_edges),
                "schema_validation": schema_validation,
                "resolution_report": resolution_report,
                "canonical_upsert": canonical_upsert,
                "wiki_page_report": wiki_page_report,
            }, f)

        _write_status(file_id, {
            "status": "completed",
            "error": None,
            "completed_at": time.time(),
            "chunk_validation_report": chunk_validation_report,
            "corpus_profile": corpus_profile,
            "schema_validation": schema_validation,
            "resolution_report": {
                "merged_count": resolution_report.get("merged_count", 0),
                "created_count": resolution_report.get("created_count", 0),
                "pending_review_count": resolution_report.get("pending_review_count", 0),
                "registry_total_nodes": resolution_report.get("registry_total_nodes", 0),
            },
            "canonical_upsert": canonical_upsert,
            "wiki_page_report": {
                "pages_created": wiki_page_report.get("pages_created", 0),
                "pages_updated": wiki_page_report.get("pages_updated", 0),
                "total_target_nodes": wiki_page_report.get("total_target_nodes", 0),
            },
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": True, "graph_built": True, "indexed": True,
            },
        })
        logger.info(f"Pipeline complete: {file_id}")

    except Exception as e:
        logger.error(f"Pipeline failed for {file_id}: {e}", exc_info=True)
        _write_status(file_id, {"status": "failed", "error": str(e)})


def retry_indexing_pipeline(file_id: str, file_path: str, ext: str, embedding_store):
    """Re-run only the embed & index stage for a file whose graph was already built."""
    try:
        logger.info(f"Retry indexing: {file_id}")
        _write_status(file_id, {"status": "processing", "error": None})

        corpus = extract_corpus(file_path, ext)
        text = corpus.get("plain_text", "")
        if not text.strip():
            _write_status(file_id, {"status": "failed", "error": "No text could be extracted"})
            return

        corpus_profile = _corpus_profile(corpus)

        text = clean_text(text)
        chunks = chunk_text(text)
        total_words = len(text.split())
        chunk_validation_report = validate_chunking(chunks, total_words=total_words, target_overlap=60)

        embedding_store.add_chunks(file_id, chunks)

        entities = []
        relationships = []
        data_path = f"{PROCESSED_DIR}/{file_id}_data.json"
        if os.path.exists(data_path):
            with open(data_path) as f:
                saved = json.load(f)
            entities = saved.get("entities", [])
            relationships = saved.get("relationships", [])
        else:
            entities, relationships = extract_entities_from_chunks(chunks)
            with open(data_path, "w") as f:
                json.dump({
                    "file_id": file_id,
                    "text_preview": text[:500],
                    "chunks_count": len(chunks),
                    "chunk_validation_report": chunk_validation_report,
                    "entities": entities[:50],
                    "relationships": relationships[:100],
                    "chunk_grounded": True,
                }, f)

        _write_status(file_id, {
            "status": "completed",
            "error": None,
            "completed_at": time.time(),
            "chunks_count": len(chunks),
            "chunk_validation_report": chunk_validation_report,
            "corpus_profile": corpus_profile,
            "pipeline_steps": {
                "cleaned": True, "chunked": True,
                "entities_extracted": True, "graph_built": True, "indexed": True,
            },
        })
        logger.info(f"Retry indexing complete: {file_id}")

    except Exception as e:
        logger.error(f"Retry indexing failed for {file_id}: {e}", exc_info=True)
        _write_status(file_id, {"status": "failed", "error": str(e)})
