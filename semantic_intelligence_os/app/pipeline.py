"""Pipeline orchestrator — wires all 14 layers in trust-building order.

Each stage persists its artifact and appends to lineage, so a run is fully traceable
and partial state is inspectable. Any non-foundational layer failure is non-blocking:
it is recorded in the run report but does not abort ingestion.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import settings
from .storage.jsonstore import write_json
from .layers import (
    s01_upload,
    s02_extraction,
    s03_normalization,
    s04_chunking,
    s05_metadata,
    s06_entity_relation,
    s07_semantic_learning,
    s08_eda,
    s09_validation,
    s10_ontology,
    s11_canonicalization,
    s12_graph,
    s13_graph_consistency,
    s14_wiki,
    extraction_observability,
    confidence_ledger,
)


def _persist(stage: str, source_id: str, artifact: dict) -> None:
    write_json(settings.dir(stage) / f"{source_id}.json", artifact)


def run_pipeline(*, filename: str, raw: bytes, role: str = "", domain: str = "") -> dict:
    started = datetime.now(timezone.utc).isoformat()

    # Step 1 — Upload + lineage (foundational; failure aborts).
    source = s01_upload.register_source(filename=filename, raw=raw, role=role, domain=domain)
    sid = source["source_id"]
    report = {"source_id": sid, "filename": filename, "started_at": started, "stages": {}}

    def stage(name: str, fn):
        try:
            out = fn()
            report["stages"][name] = "ok"
            s01_upload.append_lineage(sid, name)
            return out
        except Exception as exc:  # non-blocking for analytic layers
            report["stages"][name] = f"failed: {exc}"
            return {}

    # Step 2-4 — extraction / normalization / chunking.
    corpus = stage("extraction", lambda: s02_extraction.extract_corpus(source))
    _persist("corpus", sid, corpus)
    corpus = stage("normalization", lambda: s03_normalization.normalize_corpus(corpus)) or corpus
    chunked = stage("chunking", lambda: s04_chunking.chunk_corpus(corpus))
    _persist("chunks", sid, chunked)

    # Step 5 — metadata intelligence.
    metadata = stage("metadata", lambda: s05_metadata.build_metadata(corpus, chunked))
    _persist("metadata", sid, metadata)

    # Step 6 — entity + relation extraction (ontology-aware predicates).
    extraction = stage(
        "entity_relation",
        lambda: s06_entity_relation.extract(chunked, s10_ontology.allowed_predicates()),
    )
    _persist("entities", sid, extraction)

    # Step 6b — extraction observability: parser/OCR confidence + per-chunk lineage.
    lineage = stage("extraction_observability",
                    lambda: extraction_observability.build(source, corpus, chunked, extraction))
    _persist("extraction", sid, lineage)

    # Step 7 — semantic learning (updates persistent memory).
    learning = stage("semantic_learning", lambda: s07_semantic_learning.learn(extraction))

    # Step 8 — EDA intelligence (semantic + numeric stats for tabular sources).
    eda = stage("eda", lambda: s08_eda.run_eda(extraction, corpus, metadata))
    _persist("eda", sid, eda)

    # Step 9 — ML validation & accuracy.
    validation = stage("validation", lambda: s09_validation.validate(extraction, eda))
    _persist("validation", sid, validation)

    # Step 10 — ontology governance gate (pre-insertion).
    governance = stage("governance", lambda: s10_ontology.govern(extraction, validation))
    _persist("governance", sid, governance)

    # Step 11 — canonicalization.
    canonical = stage("canonicalization", lambda: s11_canonicalization.resolve(extraction, governance))

    # Step 12 — knowledge graph construction.
    graph = stage("graph_construction", lambda: s12_graph.construct(canonical, governance, validation))

    # Step 12b — per-entity × per-layer confidence ledger (Section 5 heatmap).
    stage("confidence_ledger",
          lambda: confidence_ledger.build(extraction, canonical, eda, validation))

    # Step 13 — graph consistency validation.
    consistency = stage("graph_consistency", lambda: s13_graph_consistency.validate_graph())

    # Step 14 — wiki + explainability.
    wiki = stage("wiki", lambda: s14_wiki.build_pages(canonical, validation))

    report.update(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "governance_mode": settings.governance_mode.value,
            "summary": {
                "chunks": chunked.get("validation", {}).get("chunk_count"),
                "entities": extraction.get("observability", {}).get("entity_count"),
                "relationships": extraction.get("observability", {}).get("relationship_count"),
                "learning": learning,
                "graph_trust_score": validation.get("graph_trust_score"),
                "ontology_consistency": governance.get("ontology_consistency"),
                "graph": graph,
                "graph_consistency": (consistency or {}).get("graph_trust_score"),
                "wiki_pages_built": wiki.get("pages_built"),
            },
        }
    )
    write_json(settings.dir("sources") / f"{sid}_run.json", report)
    return report
