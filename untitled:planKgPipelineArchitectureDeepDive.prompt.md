## Plan: KG Pipeline Architecture Deep-Dive Document

Produce a comprehensive, code-grounded KG lifecycle document for this repository, covering ingestion, preprocessing, extraction, canonicalization, storage, retrieval, observability, scalability, risks, and improvements, then save it as /home/neelam/AI-Orchestrator/KG_creation_process.md. The write-up should be reproducible for another environment and include both high-level architecture and low-level file-level behavior.

**Steps**
1. Freeze scope and evidence set from discovered code paths: file ingestion, DB ingestion, graph building, canonical merge, indexing, and retrieval.
2. Build architecture map and dependency flow from FastAPI entrypoints to pipeline services, including file uploads, URL scraping, and DB connect jobs, and note BackgroundTasks plus frontend polling.
3. Document ingestion mechanics in detail: supported formats and adapters, duplicate detection/checksum logic, storage paths under data/files and data/processed, DB materialization from SQL folders, schema export, and Graphify fallback behavior.
4. Document preprocessing and normalization: text cleaning, chunk strategy (size/overlap), chunk validation coverage checks, metadata/corpus profile generation, and any OCR limitations.
5. Document NLP/AI extraction and quality pipeline: spaCy/regex entity extraction fallback, heuristic relationship extraction, per-chunk grounding, EDA/confidence scoring, semantic consistency checks, and reprocess hooks.
6. Document canonical KG construction: canonical IDs, node/edge schema fields, entity resolution thresholds (merge/review), cross-source linking gates and review queues, canonical upsert semantics, wiki page generation, and graph suppression/repair controls.
7. Document storage layer and data models: canonical graph JSON, per-file graph JSON, FAISS index/chunk pickle, canonical registry, SLM registry, processed status/data artifacts, DB summary/profile/accuracy artifacts, and wiki index/pages.
8. Document retrieval/query layer and GraphRAG orchestration: wiki-first planner, graph mode fallbacks (canonical semantic -> file semantic -> lexical), vector search, routing profile by graph density, LLM provider fallback stack, faithfulness/coverage explainability signals.
9. Create file-level module explanations for the requested files and related services, with each module’s responsibilities, inputs/outputs, and side effects.
10. Produce a sequence/lifecycle representation for one uploaded document and one DB ingestion run, including status transitions and artifact creation at each stage.
11. Assess architecture quality: weak points, bottlenecks, security concerns, and best-practice improvements.
12. Generate the final deliverable markdown with detailed narrative, architecture breakdown, data-flow explanation, dependency map, lifecycle, technology stack summary table, Mermaid sequence flow, and replication checklist.

**Relevant files**
- /home/neelam/AI-Orchestrator/backend/main.py — API entrypoints, orchestration, retrieval planning, and query/final-run flow.
- /home/neelam/AI-Orchestrator/backend/processing.py — file pipeline lifecycle, status tracking, chunking, EDA integration, graph build, and indexing.
- /home/neelam/AI-Orchestrator/backend/ingestion.py — ingestion adapters for pdf/docx/txt/csv/xlsx/json and fallback decode.
- /home/neelam/AI-Orchestrator/backend/entity_extraction.py — entity and relationship extraction logic with chunk grounding.
- /home/neelam/AI-Orchestrator/backend/knowledge_schema.py — canonical node/edge builders and canonical graph validation.
- /home/neelam/AI-Orchestrator/backend/entity_resolution.py — canonical registry merge/review thresholds and deduplication logic.
- /home/neelam/AI-Orchestrator/backend/cross_source_linker.py — cross-source edge scoring, gates, acceptance/review queues.
- /home/neelam/AI-Orchestrator/backend/graph_builder.py — file graph persistence, canonical graph upsert/query/summary, semantic traversal.
- /home/neelam/AI-Orchestrator/backend/file_eda_service.py — KG quality analytics, confidence scoring integration, artifact bundle outputs.
- /home/neelam/AI-Orchestrator/backend/confidence_scoring.py — entity/relationship confidence formulas and quality scorecard.
- /home/neelam/AI-Orchestrator/backend/embedding.py — sentence-transformer embeddings, deterministic fallback, FAISS persistence/search.
- /home/neelam/AI-Orchestrator/backend/db_processing.py — DB background pipeline, profiling, EDA, Graphify, merge, embedding.
- /home/neelam/AI-Orchestrator/backend/db_graphify.py — Graphify execution, mapping to canonical schema, merge operations.
- /home/neelam/AI-Orchestrator/backend/db_connector.py — SQLAlchemy connectivity/introspection/DDL and corpus text export.
- /home/neelam/AI-Orchestrator/backend/llm_client.py — provider selection/fallback and generation behavior.
- /home/neelam/AI-Orchestrator/backend/slm.py — SLM registry, embedding match thresholds, scoped reuse/modify/create.
- /home/neelam/AI-Orchestrator/backend/router.py — model recommendation scoring.
- /home/neelam/AI-Orchestrator/backend/trace.py — trace lifecycle for final-run execution steps.
- /home/neelam/AI-Orchestrator/backend/wiki_builder.py — canonical wiki page generation and lookup.
- /home/neelam/AI-Orchestrator/frontend/src/services/api.js — frontend API contract to ingestion/status/query/graph endpoints.
- /home/neelam/AI-Orchestrator/frontend/src/store/index.js — frontend state model for ingestion and run status.
- /home/neelam/AI-Orchestrator/frontend/src/pages/InjectPage.jsx — polling and ingestion status presentation.
- /home/neelam/AI-Orchestrator/frontend/src/pages/inject/UploadSurface.jsx — upload/scrape trigger flow.
- /home/neelam/AI-Orchestrator/frontend/src/pages/inject/DirectUpload.jsx — DB connect/test trigger flow.

**Verification**
1. Cross-check each requested section against explicit code references before finalizing the document.
2. Validate that file pipeline and DB pipeline lifecycles both include status transitions, artifacts, and storage locations.
3. Confirm technology stack coverage includes frameworks, libraries, models, databases/storage, APIs, and async orchestration tools.
4. Confirm improvement section includes weak points, performance bottlenecks, security considerations, and recommended best practices.
5. Validate that output includes architecture breakdown, module dependency mapping, KG lifecycle, and sequence-style flow narrative.

**Decisions**
- Included scope: current repository behavior only, including both file and DB ingestion branches and retrieval/GraphRAG execution.
- Excluded scope: hypothetical external graph/vector DB architectures beyond recommendations, because implementation is currently local JSON + FAISS.
- Included caveat: code quality issues found during discovery, including fragile sections in llm_client.py and overlapping definitions in embedding.py, should be called out as architecture risks.
