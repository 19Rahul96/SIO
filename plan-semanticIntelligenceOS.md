# Plan: Enterprise Semantic Intelligence OS — Consolidated Target Plan

Status: design / planning. Date: 2026-05-29.

This plan reconciles the **existing AI_Orchestrator pipeline** (file + DB GraphRAG, JSON/FAISS,
canonical merge, EDA, wiki, SLM routing) with the **proposed 14-step "AI Data Orchestrator
Platform"** target architecture. It records what already exists, what the new plan adds, what the
new plan *drops* (and must keep), and a phased path to close the gaps without breaking current
contracts.

Guiding non-regression rule (carried from `plan-confidenceAuditLayer.prompt.md` and
`cross_source_linker_plan.md`): **additive schema only**, no removal/rename of fields used by the
UI, EDA failures and new layers must never block ingestion completion, and every new gate ships
behind an `observe_only` (default) vs `enforce` mode flag.

---

## A. Architecture decision: post-hoc scoring -> pre-insertion governance

Today the graph is built first, then scored (EDA/confidence run around or after `graph_builder`
upsert). The target requires Ontology (10) + ML Validation (9) to gate Canonicalization (11) and
Graph Construction (12). Adopt incrementally:

1. Phase in a `governance_gate` that runs in `observe_only` mode first — it annotates each
   candidate edge/entity with an ontology-validity verdict but still inserts everything.
2. Compare annotated verdicts against existing post-hoc `semantic_quality_analyzer` output to
   calibrate.
3. Flip to `enforce` per relationship-type once precision is acceptable; rejected edges go to the
   existing review queue rather than being silently dropped.

This preserves "progressively increase semantic trust" without a risky big-bang reorder.

---

## B. Gaps to close, by target step

Legend: [HAVE] reuse as-is · [EXTEND] enhance existing module · [NEW] new module.

### Step 1 — File Upload
- [HAVE] `/upload`, SHA-256 checksum dedup, status JSON, `/scrape`, `/db/connect`.
- [EXTEND] Formal **file metadata + lineage registry** artifact (`data/lineage/{source_id}.json`):
  source type, fingerprint, role/domain tags, parent/derived links, ingestion timestamps.
- [NEW] Chunked/async upload endpoint for large files; source connectors for ERP/CRM/API exports
  (start with a generic "structured export" adapter reusing the CSV/JSON path).
- Defer: true streaming/broker ingestion.

### Step 2 — Ingestion & Extraction Engine
- [HAVE] adapter registry in `ingestion.py`, fallback raw decode, structured corpus
  (`plain_text`/`text_blocks`/`table_rows`/`metadata`).
- [NEW] **OCR pipeline** (Tesseract or doc-AI) for scanned PDFs/images with per-page OCR
  confidence -> feeds Step 9 metrics.
- [EXTEND] **Parser confidence + extraction lineage**: every block records adapter, confidence,
  page/row provenance. Surfaces existing `pdf_eda_utils.py` page-confidence as a first-class
  signal.
- [NEW] Layout analysis + table-structure extraction (for invoices/contracts/ERP tables).

### Step 3 — Cleaning + Normalization
- [HAVE] `clean_text()` (whitespace/control-char only).
- [NEW] `normalization.py`: encoding normalization, null normalization, unit/currency/temporal
  normalization, schema (column-name) normalization, duplicate cleaning. Adaptive rules table
  persisted under `data/normalization_rules.json`.
- Each normalization records before/after for lineage + explainability.

### Step 4 — Chunking + Structural Segmentation
- [HAVE] 400/60 word-window chunker + chunk-coverage validation report.
- [EXTEND] Add chunking *strategies* selectable per source: semantic (embedding-boundary),
  table-aware (keep rows intact), hierarchy-aware (headings/sections), lineage-aware (carry
  provenance). Keep current chunker as the default fallback.

### Step 5 — Metadata Intelligence Engine
- [HAVE] DB-side: `db_profiler.py` (null %, cardinality, Ollama semantic labels),
  `data_dictionary.py` (definitions, review workflow, versions).
- [NEW] `metadata_intelligence.py` unifying DB + document metadata:
  - PK/FK **prediction** (not just FK read) via cardinality + name + value-overlap heuristics.
  - column semantic labeling for absurd schemas (`TMP_X1`, `col_102`) using embeddings + value
    profiles.
  - table classification + business-meaning inference + per-field confidence + explainability
    trace.
- Output is a `metadata_audit` block reusing the audit contract from
  `plan-confidenceAuditLayer.prompt.md`.

### Step 6 — Entity + Relationship Extraction
- [HAVE] `entity_extraction.py` (spaCy NER + regex fallback + heuristic relations, chunk-grounded);
  `confidence_scoring.py` relation scoring.
- [EXTEND] Add **dependency-parse** relation extraction and optional **LLM-assisted** relation
  extraction (gated, cached) to lift precision beyond pairwise heuristics.
- [EXTEND] **Ontology-aware extraction**: once Step 10 exists, constrain relation labels to the
  ontology's allowed predicates; emit `extraction_observability` (per-relation method + score).

### Step 7 — Semantic Learning Layer  [largest net-new]
- [NEW] `semantic_learning.py`: semantic memory store, embedding-based clustering, term
  co-occurrence statistics, ontology alignment, and adaptive confidence priors that **update over
  time** as more sources arrive. Persisted under `data/semantic_memory.json`.
- Reuses existing `embedding.py` (all-MiniLM-L6-v2 + FAISS) and the SLM registry pattern.
- Feeds: better merge priors (Step 11), ontology suggestions (Step 10), drift detection (Step 8).

### Step 8 — EDA Intelligence Engine
- [HAVE] Strong traditional + graph-health EDA (`eda_engine.py`, `file_eda_service.py`, EDA
  viewers, `EDA_VISUALS2_METRIC_LOGIC.md`, `plan-edaVisualPhase1.prompt.md` in flight).
- [EXTEND] Add **semantic/graph/ontology/drift EDA** views on top of the existing chart contract:
  graph density/topology analytics, semantic heatmaps, confidence overlays, semantic cluster maps,
  semantic-drift-over-time (powered by Step 7 memory). Keep the normalized chart payload contract
  from the Phase-1 EDA plan.

### Step 9 — ML Validation & Accuracy Engine
- [HAVE] `kg_evaluator.py` (gold sets, P/R/F1, false-rel rate, evidence accuracy, calibration),
  `metrics.py` contracts, faithfulness/coverage at answer time.
- [EXTEND] Add **ROC-AUC, Recall@K, MRR** for retrieval; **OCR accuracy** (from Step 2);
  **ontology-consistency** metric (from Step 10); aggregate into a single graph-trust score
  surfaced via `/metrics/aggregate`.

### Step 10 — Ontology & Semantic Governance Layer  [largest net-new]
- [NEW] `ontology.py` + `governance.py`:
  - entity taxonomy + relationship constraints (allowed source/target types per predicate) +
    semantic inheritance + business hierarchy, persisted as `data/ontology.json`.
  - a **semantic rule engine** that validates a candidate (entity, relation) against the ontology
    and returns accept/review/reject + reason.
- Wired as the pre-insertion gate from section A. Replaces the current heuristic-only
  `semantic_quality_analyzer` checks with a declarative, extensible ruleset (keep the analyzer as a
  secondary statistical check).
- Ontology **evolution**: rules can be proposed by Step 7 and approved through the existing review
  queue UI.

### Step 11 — Canonicalization & Semantic Resolution
- [HAVE] `entity_resolution.py` (merge 0.72 / review 0.58, embedding+Jaccard+type),
  `cross_source_linker.py`, `knowledge_schema.py`. Strong — keep.
- [EXTEND] Add formal **alias/synonym dictionary** + ontology-driven type compatibility (from Step
  10) into the merge score.

### Step 12 — Knowledge Graph Construction
- [HAVE] `graph_builder.py` canonical upsert, confidence-weighted edges, lineage-aware nodes,
  suppress/restore/split repair.
- [EXTEND] Add **RDF/triple export** view and an optional **graph-DB backend** (Neo4j/Memgraph)
  behind the same `GraphBuilder` interface for scale. Keep JSON as default. Add graph indexing for
  faster traversal.

### Step 13 — Graph Validation & Consistency Engine
- [HAVE] `graph_validation_utils.py` (density, components, diameter), `semantic_quality_analyzer`.
- [NEW] `graph_consistency.py` running **continuously / on-demand**: orphan-node detection, invalid
  cycle detection, ontology-violation scan (uses Step 10), graph decay + relationship drift (uses
  Step 7 history). Emits a `graph_trust_score` + observability artifact; offers repairs via existing
  suppress/restore endpoints.

### Step 14 — Wiki + Explainability Generation
- [HAVE] `wiki_builder.py` (pages, key facts w/ citations, timeline, sources).
- [EXTEND] Add **relationship explanations, lineage explanations, confidence explanations** to each
  page (pull from audit/lineage/governance artifacts). Build the **wiki + graph dual view** in the UI.

---

## C. Carry-forward items the new plan omits (must NOT be lost)

These exist today and the 14-step plan doesn't mention them — explicitly keep them:

1. **GraphRAG retrieval & query layer** — `/query`, `/final-run`, density-aware planner, hybrid
   wiki+graph+vector retrieval, faithfulness/coverage explainability. (Add as a "Step 15 —
   Retrieval & Answer Intelligence" so the new plan stays a true GraphRAG engine.)
2. **SLM registry + Model Router + Decision engine** (`slm.py`, `router.py`, `decision.py`).
3. **Database ingestion branch** (`db_connector`, `db_profiler`, `db_processing`, `db_graphify`,
   `enterprise_data_inserter`) and **cross-source linking** (corpus<->DB).
4. **Human-in-the-loop review + repair** (merge/cross-link/dictionary review queues;
   suppress/restore/split endpoints).
5. **Answer-time hallucination/faithfulness scoring**.

---

## D. Cross-cutting "enterprise-grade" gaps in BOTH plans

Required for the "Operating System / enterprise governance" framing; track as a hardening track:

- Durable job system (replace FastAPI `BackgroundTasks` -> Celery/Dramatiq/RQ/Temporal).
- Transactional / locked state for canonical graph + registry + FAISS (atomic writes).
- Source **deletion / retraction** + FAISS compaction (currently append-only).
- AuthN/AuthZ + RBAC; tighten CORS; remove SSL-bypass in `embedding.py`; secret management.
- Stabilize `llm_client.py` (flagged structurally fragile) into clean provider adapters.
- Structured logging + central metrics/audit trail for all graph mutations.

---

## E. UI / visualization gaps

Current UI: Dashboard, Inject (role/direct + DB), Model, Prompt, Results, GraphRAG viewer, EDA
viewers (echarts/plotly/recharts/cytoscape already installed). Target adds:

- [NEW] Ontology Explorer, Metadata Intelligence Studio, Hallucination Risk Observatory, AI Trust
  Command Center, Semantic Embedding Universe, Lineage Explorer, Wiki+Graph dual view, Semantic
  Search Playground.
- [EXTEND] existing Graph viewer -> interactive KG explorer with glowing confidence edges; EDA
  dashboards -> semantic heatmaps/cluster maps.
- Design language: light mode + glassmorphism + graph-native overlays (matches existing
  `AI_Orchestrator_v3_light.html` mockups).

---

## F. Phased delivery sequence

**Phase 0 — Foundations (unblockers):** lineage registry (Step 1), parser-confidence + OCR (Step
2), normalization module (Step 3). Pure additive; no gating.

**Phase 1 — Intelligence layers:** Metadata Intelligence (5), Semantic Learning (7). Both
observe-only, feeding signals into existing scoring.

**Phase 2 — Governance gate:** Ontology + rule engine (10) in `observe_only`, then Graph
Consistency engine (13). Calibrate against current `semantic_quality_analyzer`, then flip to
`enforce` per relation-type. Extend Canonicalization (11) with ontology-aware merge.

**Phase 3 — Validation & extraction quality:** retrieval metrics + ontology-consistency (9);
dependency-parse / LLM-assisted relation extraction (6); semantic/drift EDA views (8).

**Phase 4 — Explainability & UI:** wiki explanations + dual view (14); new dashboards (Ontology
Explorer, Trust Command Center, Lineage Explorer, Hallucination Observatory).

**Phase 5 — Hardening (section D):** durable queue, transactional state, deletion/retraction,
auth, `llm_client` refactor, optional graph-DB backend (12).

Throughout: keep "Step 15" retrieval/SLM/routing layer and the DB branch as first-class, and ship
every gate behind the observe/enforce flag.

---

## G. Suggested new backend modules (additive)

- `lineage.py`, `normalization.py`, `metadata_intelligence.py`, `semantic_learning.py`,
  `ontology.py`, `governance.py`, `graph_consistency.py`, `ocr.py`.
- New data artifacts: `data/lineage/`, `data/ontology.json`, `data/semantic_memory.json`,
  `data/normalization_rules.json`.
- New endpoints (mirroring existing review/metrics style): `/lineage/{source_id}`,
  `/metadata/audit/{source_id}`, `/ontology`, `/ontology/validate`, `/ontology/reviews`,
  `/governance/decisions`, `/graph/consistency`, `/semantic/memory`.
</content>
</invoke>
