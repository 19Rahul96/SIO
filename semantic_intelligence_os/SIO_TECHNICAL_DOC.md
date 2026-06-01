# Semantic Intelligence OS (SIO) — Technical Understanding Document

> Internal engineering document. Every statement below is grounded in the actual code of
> the `semantic_intelligence_os/` app and the `frontend/src` Observatory UI. Where the
> task brief asked about a capability that **does not exist** in this codebase, it is marked
> **`NOT FOUND IN CURRENT CODEBASE`** rather than described generically.

## Files inspected

**SIO backend (`semantic_intelligence_os/app/`)**
- `config.py`, `pipeline.py`, `main.py`, `smoke_test.py`
- `contracts/audit.py`, `contracts/embedding.py`
- `storage/jsonstore.py`
- `layers/s00_db.py`, `s01_upload.py`, `s02_extraction.py`, `s03_normalization.py`,
  `s04_chunking.py`, `s05_metadata.py`, `s06_entity_relation.py`, `s07_semantic_learning.py`,
  `s08_eda.py`, `s09_validation.py`, `s10_ontology.py`, `s11_canonicalization.py`,
  `s12_graph.py`, `s13_graph_consistency.py`, `s14_wiki.py`
- `layers/_stats.py`, `layers/extraction_observability.py`, `layers/confidence_ledger.py`

**Frontend (`frontend/src/`)**
- `pages/ObservatoryPage.jsx`, `pages/SemanticOSPage.jsx`
- `services/sioApi.js`, `App.jsx`, `components/Topbar.jsx`, `vite.config.js`
- `components/eda/charts.jsx`, `components/eda/utils/{confidenceColorScale.js, useObserveOnly.js, EDAEmptyState.jsx, chartAdapter.js}`
- `components/sio/KGGraph.jsx`, `components/sio/charts.jsx`
- `components/eda2/charts/{ChartRenderer, EChartsPanel, PlotlyPanel, RechartsPanel, CytoscapePanel}.jsx`, `components/eda2/DistributionLabPanel.jsx`

**Legacy backend (for contrast only)** — `backend/main.py`, `backend/eda_engine.py`, `backend/pdf_eda_utils.py`, `backend/db_connector.py` (the numeric-stats and PDF logic in SIO was ported from these).

---

# 1. Project Overview

**Semantic Intelligence OS (SIO)** is a standalone FastAPI + React application that turns raw
enterprise files and databases into a **validated, explainable knowledge graph** through a fixed
**14-layer pipeline**. Each layer increases "semantic trust" and every artifact carries an audit
trail (confidence, evidence, trace, policy).

- **Problem it solves:** raw documents/tables have no machine-usable semantics. SIO extracts
  entities/relationships, resolves duplicates, validates relationships against an ontology
  *before* inserting them into a graph, and surfaces trust/quality metrics so a user can judge how
  reliable the result is.
- **Input it accepts:** files `PDF, DOCX, TXT, MD, CSV, XLSX/XLS, JSON, HTML` (multiple at once, or a
  folder), and live databases `PostgreSQL, MySQL, SQLite` (schema is introspected and ingested).
  Defined in `s01_upload.SUPPORTED_EXTS` and `main.ingest` / `main.ingest_database`.
- **Output it produces:** a canonical knowledge graph (`data/graph/canonical_graph.json`), per-entity
  wiki pages, per-source EDA/validation/governance artifacts, a per-entity×per-layer confidence
  matrix, and aggregate trust metrics — all served as JSON over HTTP and rendered in two React pages.
- **Backend↔frontend connection:** the React SPA calls the backend through a `/sio` prefix.
  In dev, `vite.config.js` proxies `/sio` → `http://127.0.0.1:8020`. In production the same FastAPI
  process serves the built SPA *and* the API (routes are mounted at both `/` and `/sio` in
  `main.py`). The frontend client is `frontend/src/services/sioApi.js` (`SIO_BASE = '/sio'`).

### Legacy backend vs SIO app
Two separate apps exist in the repo:

| | Legacy backend | SIO app |
|---|---|---|
| Path | `backend/` | `semantic_intelligence_os/` |
| Entrypoint | `main:app` (title "AI Orchestrator API") | `app.main:app` (title "Semantic Intelligence OS") |
| Intended port | 8010 | 8020 |
| Routes | `/upload`, `/status`, `/db/connect`, `/eda/visuals`, … | `/sio/ingest`, `/sio/eda/*`, `/sio/graph/*`, `/sio/metrics/aggregate`, … |
| Used by Semantic OS / Observatory UI | **No** | **Yes** |

SIO **reused logic** from the legacy backend by *porting* (not importing) the numeric-stats engine
(`backend/eda_engine.py` → `app/layers/_stats.py`), PDF page-confidence (`backend/pdf_eda_utils.py`
→ `app/layers/extraction_observability.py`), and the DB connector (`backend/db_connector.py` →
`app/layers/s00_db.py`). The two apps share no running code.

### Architecture (text diagram)
```
User upload / folder / DB connection            (frontend SemanticOSPage → /sio/ingest | /sio/ingest/database)
        │
        ▼
 s01 Upload + lineage          (fingerprint, dedup, data/sources, data/lineage)
        ▼
 s02 Ingestion & Extraction    (adapters per ext, parser confidence, data/corpus)
        ▼
 s03 Normalization             (encoding/whitespace/currency/temporal cleanup)
        ▼
 s04 Chunking                  (word-window or table-aware, coverage validation, data/chunks)
        ▼
 s05 Metadata Intelligence     (datatype, semantic label, PK/FK prediction, data/metadata)
        ▼
 s06 Entity + Relationship     (spaCy/regex NER + co-occurrence relations, data/entities)
        ▼
 s07 Semantic Learning         (persistent embedding memory + adaptive priors)
        ▼
 s08 EDA Intelligence          (graph + semantic EDA + numeric stats/correlation, data/eda)
        ▼
 s09 ML Validation             (P/R/F1, calibration, hallucination risk, graph trust, data/validation)
        ▼
 s10 Ontology & Governance     (taxonomy + relationship constraints gate, data/governance)
        ▼
 s11 Canonicalization          (entity resolution / merge, data/canonical/registry.json)
        ▼
 s12 Knowledge Graph           (confidence-weighted nodes/edges + RDF triples, data/graph)
        ▼  (s12b confidence_ledger → data/confidence/matrix.json)
 s13 Graph Consistency         (orphans, cycles, ontology violations, trust score)
        ▼
 s14 Wiki + Explainability     (per-entity cited pages, data/wiki)
        │
        ▼
 Observatory UI / Semantic OS UI   (frontend reads /sio/eda/*, /sio/graph/*, /sio/metrics/aggregate, …)
```
Orchestrated by `app/pipeline.py:run_pipeline`. Every stage is wrapped in a `stage()` helper so a
non-foundational failure is recorded (`report["stages"][name]="failed: …"`) but does not abort
ingestion.

---

# 5. Ingestion Process

### What can be ingested
- **Files** (`main.ingest`, accepts `List[UploadFile]`): extensions in `s01_upload.SUPPORTED_EXTS`
  = `.pdf .docx .txt .md .csv .xlsx .xls .json`. The frontend also offers HTML; unknown extensions
  fall back to a raw text decode.
- **Folders:** the browser sends a folder as many files to the same `/sio/ingest` endpoint
  (`SemanticOSPage.jsx`, `webkitdirectory` input).
- **Databases** (`main.ingest_database` → `s00_db`): PostgreSQL / MySQL / SQLite. The schema is
  introspected and rendered as a corpus-text blob, then run through the same pipeline.

### Step-by-step (code-level)
| Step | File · function | What it does | Output artifact |
|---|---|---|---|
| Register source | `s01_upload.register_source` | SHA-256 `fingerprint`, dedup scan vs existing sources, stores raw bytes, writes lineage record | `data/sources/{id}.json`, `data/lineage/{id}.json` |
| Extract | `s02_extraction.extract_corpus` → `_extract_pdf` (pypdf) / `_extract_docx` (python-docx) / `_extract_table` (pandas) / `_extract_text` | builds `{plain_text, text_blocks[], table_rows[], columns[]}`; computes per-block `confidence` and a parser-confidence `audit`; sets `needs_ocr` if PDF parser confidence < 0.4 | `data/corpus/{id}.json` |
| Normalize | `s03_normalization.normalize_corpus` | NFKC, control-char strip, whitespace collapse, currency→ISO, date→`YYYY-MM-DD`; records `normalization.applied[]` | (in-memory, persisted into corpus) |
| Chunk | `s04_chunking.chunk_corpus` → `_window_chunks` / `_table_chunks` | 400-word window (60 overlap, from `config.chunk_size_words/chunk_overlap_words`) for text; 25-row groups for tables; computes coverage | `data/chunks/{id}.json` |
| Metadata | `s05_metadata.build_metadata` | tabular only: datatype + semantic label per column, PK/FK prediction, table classification | `data/metadata/{id}.json` |

### Metadata / schema / column detection (`s05_metadata.py`)
- **Datatype** (`_infer_datatype`): regex-based — `numeric`, `date`, `email`, `text`, `unknown`.
- **Semantic label** (`_label_column`): name-token lookup table `_NAME_HINTS` (e.g. `id/key/ref→identifier`,
  `email→email`, `amount/price/revenue→monetary`, `date/time→temporal`, `city/country→location`) plus a
  value-profile fallback. Produces a confidence 0.40–0.82 in an `audit` block.
- **PK/FK prediction** (`_predict_keys`): a column is a **PK candidate** if `uniqueness ≥ 0.98` and
  near-non-null; **FK candidate** if its name matches `(_id$|_ref$|_key$|_code$)` and `uniqueness < 0.9`.
  These are *predictions*, not read from real constraints (for file sources).
- **Table classification** (`_classify_table`): `transactional` / `reference/dimension` /
  `entity_master` / `generic`, from the mix of semantic labels.

### Noisy / empty / duplicate / invalid handling
- **Duplicate sources:** `s01_upload.register_source` flags `duplicate_of` when a fingerprint already
  exists (does **not** block — additive).
- **Coverage / data loss:** `s04_chunking` reports `coverage_pct` and `data_loss_suspected`
  (coverage < 0.98).
- **Low-quality extraction:** `s02_extraction` per-block `confidence` (alphanumeric ratio for PDF
  pages); `needs_ocr` flag.
- **Per-chunk warnings:** `extraction_observability.build` flags `low_parser_confidence` (<0.6) and
  `no_entities_extracted`.
- **Tabular data quality:** `_stats.consistency_checks` counts `invalid_dates`, `type_mismatches`,
  `null_key_violations`, `duplicates` (duplicate full rows). *(Note: `enum_violations` is a defined
  key but is always 0 — no enum rule engine exists.)*
- **OCR engine:** **NOT FOUND IN CURRENT CODEBASE** — only a `needs_ocr` flag + page confidence; no
  Tesseract/OCR step runs.

### Where ingestion results are stored
All under `semantic_intelligence_os/data/` (gitignored, atomic JSON via
`storage/jsonstore.write_json`): `sources/`, `lineage/`, `corpus/`, `chunks/`, `metadata/`,
`entities/`, `eda/`, `validation/`, `governance/`, `canonical/`, `graph/`, `wiki/`,
`semantic_memory/`, `confidence/`, `extraction/`. A full run report is `data/sources/{id}_run.json`.

---

# 6. EDA Process

EDA in SIO has **two parts**, both produced by `s08_eda.run_eda(extraction, corpus, metadata)` and
stored in `data/eda/{id}.json`:

1. **Semantic / graph EDA** (always, for any source) — computed in `run_eda`.
2. **Numeric / statistical EDA** (tabular sources only) — computed in `s08_eda._numeric_eda` which
   calls `app/layers/_stats.py` (ported from `backend/eda_engine.py`).

The Observatory reads these through aggregate endpoints in `main.py`: `/eda/summary`, `/eda/columns`,
`/eda/validation`, `/eda/correlation`, `/eda/outliers` (plus `/eda/confidence`, `/eda/extraction`).
Each endpoint returns `{empty: true, reason}` when nothing is ingested (no fake data).

### EDA metrics actually computed

| Metric | Where | Meaning | How computed | Interpretation | Type |
|---|---|---|---|---|---|
| chunk count | `s04 validation.chunk_count` | # processing units | `len(chunks)` | — | True statistic |
| coverage % | `s04 validation.coverage_pct` | % of words/rows captured in chunks | covered/total ×100 | <98% ⇒ `data_loss_suspected` | True statistic |
| node/edge count, density, avg_degree | `s08 graph_eda` | per-source graph shape | counts; density = edges / (n(n−1)/2); avg_degree = Σdeg/n | high density = richly linked | True statistic |
| orphan_node_count | `s08 graph_eda` | entities with no relation in this source | degree==0 | high = sparse extraction | True statistic |
| avg_confidence, band_distribution | `s08 confidence_eda` | entity confidence summary | mean of entity audit scores; bucket high/med/low | low avg = weak extraction | Proxy/trust score |
| entity type distribution | `s08 semantic_cluster_map` | counts per `entity_type` | `Counter(entity_type)` | — | True statistic (over AI-inferred labels) |
| relation distribution | `s08 relation_distribution` | counts per predicate | `Counter(relation)` | many `related_to` = weak typing | True statistic |
| semantic drift | `s08 semantic_drift` | terms whose current confidence diverges from learned prior | `|prior − current| > 0.3` | high = inconsistent signals | Proxy score |
| per-column numeric stats | `_stats.column_stats` | mean, median, std, variance, q1/q3, iqr, p10, p90, **skewness, kurtosis**, histogram(8), qq_points, box, zscore_bins, outliers (IQR & z) | pure-Python formulas | skew≠0 = asymmetric; |z|>3 = outlier | True statistic |
| null_rate, cardinality, most_common | `_stats.column_stats` | completeness & diversity | null/total; `len(set)`; `Counter.most_common(5)` | high null = incomplete | True statistic |
| correlation | `_stats.correlation` | pearson_matrix, spearman_matrix, pair_explorer, strongest_pos/neg | `_pearson`, `_spearman` (≤10 numeric cols) | |r|→1 strong | True statistic |
| consistency checks | `_stats.consistency_checks` | invalid_dates, type_mismatches, null_key_violations, duplicates | per-rule counts | >0 = quality issue | True statistic |

### Requested EDA metrics **NOT** in the codebase
`top keywords`, `duplicate chunk rate`, `empty/noisy chunk rate` (only per-chunk warning flags exist),
`generic entity ratio` (only a generic **relation** rate inside `hallucination_risk`),
`source contribution` (only `provenance` source counts per node — not an EDA chart),
`data type distribution` chart (datatype is per-column in metadata, not aggregated). A separate
**"Text EDA"** section is **NOT FOUND** — text sources get only the semantic/graph EDA above.

### How EDA reaches the UI
`/sio/eda/columns|validation|correlation|outliers` → consumed by `ObservatoryPage.jsx` Sections 2 & 3
(`DataQuality`, `CorrelationOutliers`), rendered with `components/sio/charts.jsx` (Bars/Donut) and
`components/eda/charts.jsx` (`BoxPlot`); the correlation heatmap reuses
`components/eda2/charts/ChartRenderer` via `components/eda/utils/chartAdapter.correlationHeatmap`.

---

# 7. Semantic Extraction Process

File: `app/layers/s06_entity_relation.py` (+ `s07_semantic_learning.py`).

- **Entity extraction** (`_ner`): primary path is **spaCy** (`en_core_web_sm`, lazy-loaded in `_nlp()`).
  If spaCy is unavailable, a **regex fallback** runs (`_MONEY`, `_DATE`, `_PROPER`) with lightweight
  type heuristics in `_guess_proper_label` (org-suffix → `ORG`, gazetteer → `GPE`, two-token caps →
  `PERSON`). Labels are mapped to types via `_LABEL_TO_TYPE` (organization/person/location/monetary/
  temporal/concept).
- **Entity confidence** (per entity `audit.confidence.score`): `0.40·freq_sig + 0.35·label_sig +
  0.25·len_sig` — a **proxy score**, not a model probability.
- **Relationship extraction** (`_classify_relation`): sentence-level **co-occurrence** of entities;
  the predicate is chosen by lexical cue lists `_PREDICATES` (`has_revenue, employs, owns, located_in,
  occurred_at`), constrained to ontology-allowed predicates passed from `s10`. Default predicate is
  `related_to`. Method recorded as `lexical_cooccurrence`.
- **Keyword extraction:** **NOT FOUND IN CURRENT CODEBASE** (no TF-IDF/keyword step).
- **Table/column understanding & business meaning:** done in `s05_metadata` (semantic labels, table
  classification) — heuristic + name lookups, not LLM.
- **AI-based inference:** the only "AI" is **spaCy NER** (statistical model) and
  **sentence-transformer embeddings** (`contracts/embedding.py`, `all-MiniLM-L6-v2`, with a
  deterministic hash-embedding fallback when offline). **No LLM is called anywhere in the SIO
  pipeline.** Everything else (relations, confidence, ontology checks) is deterministic/heuristic.
- **Semantic learning** (`s07`): maintains `data/semantic_memory/memory.json` — per-term embedding,
  `observations` count, and an adaptive `prior = min(0.95, 0.5 + 0.05·observations)`; plus pairwise
  `cooccurrence` counts. `prior_for(term)` and `nearest_terms()` feed later layers.

**Deterministic/statistical vs AI-inferred:** entity *spans* come from a model (spaCy) → AI-inferred;
entity *types*, *relations*, *confidence*, *labels* are rule/heuristic → deterministic. Embedding
similarity (used in canonicalization) is model-based when sentence-transformers is installed.

---

# 8. Ontology Generation

File: `app/layers/s10_ontology.py`. Persisted at `data/governance/ontology.json`.

**What "ontology" means here:** a small, declarative, **seeded** schema (`_DEFAULT_ONTOLOGY`) with:
- a **taxonomy** (entity types → parent): `organization/person → agent`, `location → place`,
  `monetary/temporal → value`, etc.
- **relationship constraints**: allowed `(source_type, target_type)` pairs per predicate
  (e.g. `has_revenue: [[organization, monetary]]`, `employs: [[organization, person]]`,
  `located_in: [[organization, location],[person, location]]`, `related_to: "ANY"`).

It is **not generated by learning** — it is a hand-seeded ontology that can **evolve** via
`update_ontology(predicate, allowed_pairs)` (endpoint `POST /ontology/predicate`), which bumps
`version`. Entity *classes* therefore are the fixed taxonomy keys; *properties/attributes* per class
are **NOT modeled** (no attribute schema exists).

**How it is used before the graph:** `s10.govern(extraction, validation)` validates every candidate
relationship against the constraints (`_pair_ok` walks the taxonomy via `_is_a`) and assigns
`auto_accept` / `review_required` / `reject`. This is the **pre-insertion gate**. Behavior depends on
`config.GovernanceMode`:
- `observe_only` (default): annotate verdicts but still pass everything downstream (nothing dropped).
- `enforce`: rejects/reviews are excluded from auto-insertion.

### Ontology metrics
| Requested metric | Status |
|---|---|
| ontology_consistency | **EXISTS** — `s10.govern`: `1 − rejects/total_verdicts`. Appears in run summary + `SemanticOSPage` Governance tab + `eda/summary.ontology_violations` (count). Low ⇒ many relationships violate type constraints (often because weak entity typing produced `concept`–`concept` pairs). True/derived statistic over heuristic verdicts. |
| verdict distribution | **EXISTS** — `verdicts_summary {auto_accept, review_required, reject}`. |
| ontology score, ontology coverage, ontology density, entity coverage, relationship coverage, semantic completeness, schema alignment, trust/confidence score | **NOT FOUND IN CURRENT CODEBASE** — these named metrics are not computed. The only ontology quality signal is `ontology_consistency`. |

---

# 9. Relationship Discovery / Relationship Health Matrix

**Relationship Health Matrix (table.column ↔ table.column overlap, joinability, cardinality type,
orphan count, joinability signal): NOT FOUND IN CURRENT CODEBASE.** This was a *legacy backend*
concept (`backend/db_profiler.py` implicit-relationship detection) and was **not** ported into SIO.

What SIO actually does for relationships:
- **Discovery:** sentence co-occurrence of entities within a chunk (`s06`), producing
  `{source, source_type, target, target_type, relation, chunk_idx, method, evidence_sentence}`.
- **Validation:** ontology gate (`s10`) → accept/review/reject per relationship (section 8).
- **Edge confidence** (`s12._edge_confidence`): base `0.4` for `related_to`, else `0.7`, plus a
  co-occurrence boost `min(0.2, 0.02·cooccurrence_count)` from semantic memory.
- **Classification surfaced in UI:** edges are colored by confidence band in `KGGraph.jsx`
  (`≥0.75` green / `≥0.45` amber / else red) and counted as `low_confidence_edges` (<`band_low`=0.45)
  in `/graph/stats` and `s13`. There is **no** "strong/weak/review-needed" join classification or
  overlap-percentage / cardinality-type computation.

---

# 10. Knowledge Graph Creation

File: `app/layers/s12_graph.py`. Persisted at `data/graph/canonical_graph.json` (+ per-source
`data/graph/{id}_triples.json`).

- **Nodes** = canonical entities (one per resolved concept). Built from the canonical registry
  (`s11`). Node fields: `canonical_id, label, entity_type, aliases[], provenance[]` (source ids).
- **Edges** = ontology-accepted relationships. Edge fields: `edge_id (src|relation|tgt), source,
  target, relation, confidence, governance (action), provenance[], suppressed`.
- **Entities → nodes:** `s11_canonicalization.resolve` maps each raw entity text to a `canonical_id`
  (`text_to_canonical`); `s12.construct` upserts those nodes, appending `provenance`.
- **Relationships → edges:** for each `governance.accepted_relationships`, `s12` looks up
  source/target canonical ids, skips self-loops/missing, computes confidence, and `MERGE`-style
  upserts the edge.
- **Metadata attached:** governance action, confidence, provenance source list, suppressed flag.
- **Graph data creation/return:** written as one JSON file; returned to the frontend by `GET /graph`
  (full), and the Observatory uses `GET /graph/stats|entities|relationships` (aggregates).
- **Visualization:** `frontend/src/components/sio/KGGraph.jsx` — an **interactive Cytoscape** graph
  (drag/zoom/pan, node color by `entity_type`, edge width by confidence, dashed if suppressed,
  click-to-inspect). Used in the Semantic OS "Graph" tab and the Observatory "Graph Trust" tab. Large
  graphs are capped to the top-120 highest-degree nodes for responsiveness.

**Schema / node types / edge types:** node types = ontology taxonomy types (organization, person,
location, monetary, temporal, concept). Edge types = predicates (`has_revenue, employs, owns,
located_in, occurred_at, related_to`). **RDF triples** are also exported per source.

- **Confidence scores:** node confidence comes from the registry (set at creation = entity extraction
  score); edge confidence per `_edge_confidence` (proxy).
- **AI-inferred vs true relationships:** all relationships are heuristic (co-occurrence) — there are
  no "true"/curated relationships except the bootstrapped gold set used only for scoring (`s09`).
- **Duplicate entities:** merged in `s11` (see §below) — aliases are aggregated onto one node.
- **Isolated nodes:** kept in the graph; detected as `orphan_nodes` by `s13` and `/graph/stats`.

### Entity resolution (`s11_canonicalization.py`)
Match score against existing canonical nodes of the same type:
`0.45·exact_norm + 0.35·lexical_jaccard + 0.20·embedding_cosine`, then a learned-prior nudge
`+0.1·(prior − 0.5)`. Thresholds from `config`: **merge ≥ 0.72**, **review 0.58–0.72** (queued in
`registry.pending_reviews`), else create a new canonical node. Registry at
`data/canonical/registry.json`.

---

# 11. Graph Metrics Explanation

Sources: `s08_eda.graph_eda` (per source), `s13_graph_consistency.validate_graph` (global), and
`main._graph_stats` / `/graph/entities` (global, Observatory).

| Metric | Exists? | Meaning · calculation · interpretation · type |
|---|---|---|
| node count | ✅ `_graph_stats.node_count` | # canonical nodes; `len(nodes)`. True statistic |
| edge count | ✅ `edge_count` | # active (non-suppressed) edges. True statistic |
| graph density | ✅ `density` | edges / (n(n−1)/2); higher = more interconnected. True statistic |
| connected components | ✅ `connected_components` (`main._components`, union-find) | # disjoint subgraphs; many = fragmented. True statistic |
| isolated / orphan nodes | ✅ `orphan_count` / `s13.orphan_nodes` | nodes with no active edge; high = weak linking. True statistic |
| average degree | ✅ `s08 graph_eda.avg_degree` (per source) | Σdeg/n. True statistic |
| degree centrality | ✅ `/graph/entities.degree_centrality` | incident-edge count per node; used to rank "top connected entities". True statistic |
| low-confidence edges | ✅ `low_confidence_edges` | edges with confidence < 0.45. True statistic over proxy confidences |
| ontology violations | ✅ `s13.ontology_violations` | edges breaking type constraints. True statistic over heuristic rules |
| cycles | ✅ `s13.cycles` (DFS, capped) | directed cycles sample. True statistic |
| graph trust / health score | ✅ `s13.graph_trust_score` | `1 − 0.4·(violations/edges) − 0.2·(orphans/nodes) − 0.2·(low_conf/edges) − 0.2·min(1,cycles/5)`; band high/med/low. **Proxy/trust score** |
| relationship confidence | ✅ edge `confidence` (`s12`) + Observatory histogram (frontend buckets in `ObservatoryPage.KGAnalytics`) | base + co-occurrence boost. Proxy score |
| betweenness centrality | ❌ NOT FOUND |
| closeness centrality | ❌ NOT FOUND |
| clustering coefficient | ❌ NOT FOUND |
| average path length | ⚠️ key exists in `/graph/stats` but returns **`null`** (explicitly deferred — too expensive) |
| graph completeness / dependency score / weak-link / strong-link scores | ❌ NOT FOUND (only the confidence-band coloring exists) |

---

# 12. Observatory UI / Dashboard

File: `frontend/src/pages/ObservatoryPage.jsx` (nav entry `◇ Observatory`, `App.jsx` index 6). It is a
separate page from `◆ Semantic OS` (`SemanticOSPage.jsx`). Design: glassmorphism cards (`GLASS`
style), light mode, confidence colors from `components/eda/utils/confidenceColorScale.js`. Four tabs
carry a **[Preview]** pill driven by `useObserveOnly()` (Vite env `VITE_EDA_PREVIEW`).

The Observatory has exactly **8 tabs** (constant `TABS`). Each section fetches lazily via the
`useFetch` hook and shows `EDAEmptyState` when its endpoint returns `{empty:true}`.

| # | Tab | Feeds (endpoint → sioApi) | Shows | Metric classification |
|---|---|---|---|---|
| 1 | **KPI & Health** | `/eda/summary` → `edaSummary` | trust gauge + stat tiles (nodes, edges, density, sources, orphans, ontology violations, avg hallucination, low-conf edges) | True statistics + one Proxy (trust) |
| 2 | **Data Quality** (Validation / Statistics / Distributions sub-tabs) | `/eda/validation`, `/eda/columns` | consistency-check tiles; per-column stats table + histograms; box plot + z-score bins + QQ plot per selected column | True statistics |
| 3 | **Correlation & Outliers** | `/eda/correlation`, `/eda/outliers` | Pearson heatmap (reuses eda2 `ChartRenderer`) + pair list; outlier-burden bars + box plots | True statistics |
| 4 | **KG Analytics** | `/graph/stats`, `/graph/entities`, `/graph/relationships` | graph stat tiles; relationship-confidence histogram (frontend-bucketed); **Top connected entities** table; **Entity growth → empty state (deferred)** | True statistics + Frontend-derived histogram |
| 5 | **Semantic Heatmap** [Preview] | `/eda/confidence` → `edaConfidence` | entity × 5-layer confidence heatmap (`components/eda/charts.ConfidenceHeatmap`), click-to-inspect drawer | Proxy/trust scores (per-layer) |
| 6 | **Graph Trust** [Preview] | `/graph` + `/graph/stats` | interactive `KGGraph` overlay with a client-side trust-threshold slider + metrics strip | True statistics + Proxy edge confidence |
| 7 | **Extraction Quality** [Preview] | `/eda/extraction` → `edaExtraction` | parser-confidence bars per source, PDF page/OCR-confidence bars, **extraction lineage table** (chunk_id, source, adapter, confidence, page/row, entity_count, warnings) | True statistics + Proxy (parser confidence) |
| 8 | **AI Trust Center** [Preview] | `/metrics/aggregate` + `/eda/summary` | 4 radial gauges (Graph Trust, Metadata Coverage, Hallucination Risk, Retrieval `(proxy)`), **Enterprise AI Readiness** score + tier, **Active alerts**, **Graph stability → empty state (deferred)** | Mix: True, Proxy, and one frontend-computed readiness score |

**Enterprise AI Readiness** (Section 8, computed in the frontend `AITrustCenter`):
`round(graphTrust·0.3 + metadataCoverage·0.2 + (100−hallucinationRisk)·0.3 + retrieval·0.2)`; tier:
≤40 Not Ready, ≤65 Developing, ≤85 Production Ready, else Enterprise Grade. **Frontend-derived.**

### Requested Observatory tabs that **do NOT exist**
`Intelligence Brief`, `Trust & Quality` (as a named tab — trust shows in KPI & AI Trust Center),
`Text EDA`, `Dependency Map`, `Anomaly Radar`, `Temporal Signal`, `Distribution Lab` (the
`eda2/DistributionLabPanel.jsx` component exists in the repo but is **not** wired into the
Observatory; Section 2 "Distributions" uses custom charts), `AI Brief` (no LLM narrative is
generated), `Relationship Health Matrix`. All **NOT FOUND IN CURRENT CODEBASE**.

> The `◆ Semantic OS` page (`SemanticOSPage.jsx`) is a second dashboard with its own tabs —
> Pipeline, Graph, EDA, Validation, Governance, Consistency, Metadata, Ontology, Wiki — driven by the
> per-source endpoints (`/eda/{id}`, `/validation/{id}`, `/governance/{id}`, `/metadata/{id}`,
> `/graph`, `/graph/consistency`, `/ontology`, `/wiki/*`). It also hosts the ingestion UI.

---

# 13. Metric Dictionary

Type legend: **TS** = True Statistic, **PX** = Proxy/Trust score, **AI** = AI/model-inferred (spaCy/
embeddings), **FE** = Frontend-derived.

| Metric | Tab / layer | Meaning | Calculation logic | Input data | Range | Good | Bad | Type | Code location |
|---|---|---|---|---|---|---|---|---|---|
| coverage_pct | Ingest / s04 | % of source captured in chunks | covered/total ×100 | chunks vs words/rows | 0–100 | ~100 | <98 | TS | `s04_chunking.chunk_corpus` |
| parser_confidence | Extraction Quality / s02 | extraction quality per source | mean block confidence | text_blocks | 0–1 | ≥0.6 | <0.45 | PX | `s02_extraction`, `extraction_observability.build` |
| needs_ocr | Extraction Quality / s02 | PDF likely scanned | parser_conf < 0.4 | PDF blocks | bool | false | true | TS | `s02_extraction.extract_corpus` |
| null_rate | Data Quality / _stats | column incompleteness | nulls/total | column values | 0–1 | low | high | TS | `_stats.column_stats` |
| cardinality | Data Quality / _stats | distinct values | `len(set)` | column values | ≥0 | context | — | TS | `_stats.column_stats` |
| mean/median/std/variance | Data Quality / _stats | central tendency & spread | standard formulas | numeric column | ℝ | — | — | TS | `_stats.column_stats` |
| skewness / kurtosis | Data Quality / _stats | distribution shape | 3rd/4th moments | numeric column | ℝ | ~0 / ~0 | large | TS | `_stats.column_stats` |
| iqr / outliers_iqr_count / outliers_zscore_count | Data Quality / _stats | dispersion & outliers | Q3−Q1; 1.5·IQR fence; |z|>3 | numeric column | ≥0 | low | high | TS | `_stats.column_stats` |
| pearson / spearman | Correlation / _stats | linear / rank correlation | covariance-normalized; rank pearson | ≥2 numeric cols | −1..1 | context | — | TS | `_stats._pearson/_spearman/correlation` |
| invalid_dates / type_mismatches / null_key_violations / duplicates | Data Quality / _stats | tabular quality issues | per-rule counts | rows + labels | ≥0 | 0 | high | TS | `_stats.consistency_checks` |
| semantic_label | Metadata / s05 | inferred column meaning | name-hint lookup + value profile | column name+values | enum | high conf | `free_text` | AI/heuristic | `s05_metadata._label_column` |
| predicted PK/FK | Metadata / s05 | likely keys | uniqueness + name regex | column stats | list | — | — | PX | `s05_metadata._predict_keys` |
| entity confidence | s06 / Heatmap(Extraction layer) | trust in an extracted entity | 0.4·freq+0.35·label+0.25·len | entity | 0–1 | ≥0.75 | <0.45 | PX | `s06_entity_relation.extract` |
| entity type distribution | EDA / s08 | counts per type | `Counter` | entities | counts | — | — | TS (over AI labels) | `s08_eda.run_eda` |
| semantic drift | EDA / s08 | prior vs current divergence | `|prior−current|>0.3` | memory + entities | count | low | high | PX | `s08_eda.run_eda` |
| entity/relationship P/R/F1 | Validation / s09 | extraction accuracy vs gold | precision/recall/F1 | pred vs gold set | 0–1 | high | low | TS (vs bootstrapped gold) | `s09_validation._prf` |
| recall@5 / MRR | Validation / s09 | retrieval proxy | rank of gold entities by confidence | ranked entities | 0–1 | high | low | PX (bootstrapped) | `s09_validation.validate` |
| calibration_error | Validation / s09 | confidence calibration | `|mean_conf − high_band_rate|` | entity confidences | 0–1 | low | high | PX | `s09_validation._calibration_error` |
| hallucination_risk | Validation / AI Trust | risk of unsupported output | `0.6·generic_rel_rate + 0.4·min(1,drift/10)` | relations + drift | 0–1 | low | high | PX | `s09_validation.validate` |
| graph_trust_score | Validation & s13 / KPI, AI Trust | overall graph reliability | weighted blend (see §11) | metrics | 0–1 | ≥0.75 | <0.45 | PX | `s09_validation.validate`, `s13_graph_consistency.validate_graph` |
| ontology_consistency | Governance / Semantic OS | share of valid relationships | `1 − rejects/total` | verdicts | 0–1 | ~1 | low | TS (over heuristic verdicts) | `s10_ontology.govern` |
| verdicts_summary | Governance | accept/review/reject counts | per-action count | verdicts | counts | high accept | high reject | TS | `s10_ontology.govern` |
| per-layer confidence (Extraction/Resolution/Canonicalization/Graph Insert/EDA Validation) | Semantic Heatmap / confidence_ledger | entity trust at each stage | extraction score / `prior_for` / registry conf / mean incident edge conf / drift-or-trust | artifacts join | 0–1 or null | high | low/null | PX | `confidence_ledger.build` |
| density / connected_components / orphan_count / low_confidence_edges / degree_centrality | KG Analytics / Graph | graph shape & linking | see §11 | graph | ≥0 | context | — | TS | `main._graph_stats`, `/graph/entities`, `s13` |
| metadata_coverage | AI Trust | how well columns are labeled | mean column label confidence | metadata audits | 0–1 | high | low | PX | `main.metrics_aggregate` |
| retrieval_accuracy (proxy) | AI Trust | retrieval proxy | mean recall@5 | validations | 0–1 | high | low | PX (flagged proxy) | `main.metrics_aggregate` |
| Enterprise AI Readiness | AI Trust | composite readiness | `gt·.3+mc·.2+(100−hr)·.3+ra·.2` | aggregate metrics | 0–100 | ≥86 | ≤40 | FE | `ObservatoryPage.AITrustCenter` |
| relationship confidence histogram | KG Analytics | edge-confidence distribution | client-side bucketing 0–0.2…0.8–1.0 | `/graph/relationships` | counts | right-skewed | left-skewed | FE | `ObservatoryPage.KGAnalytics` |

---

# 15. Data Flow Example

**Input file `sales.csv`:**
```
region,revenue,units,year
North,4200000,120,2021
South,5300000,95,2022
East,2800000,210,2021
West,9100000,60,2023
```

| Stage | What happens (concrete) |
|---|---|
| Raw input | `POST /sio/ingest` (multipart `files`) → `s01.register_source` writes `data/sources/{id}.json` with SHA-256 fingerprint |
| Parsed data | `s02._extract_table` (pandas) → `columns=[region,revenue,units,year]`, 4 `table_rows`, `source_type="csv"`, parser audit ≈1.0 |
| Chunks / metadata | `s04._table_chunks` → 1 table-aware chunk (4 rows). `s05` → `revenue` datatype `numeric` label `monetary`; PK candidate none (no near-unique col); table_classification `transactional` (monetary + temporal) |
| EDA metrics | `s08._numeric_eda` → revenue: mean ≈ 5,350,000, median 4,750,000, skewness ≈ +0.3, histogram(8), IQR outliers 0; correlation matrix over `revenue/units/year` (e.g. revenue↔units ≈ −0.x); consistency_checks all 0 |
| Entity extraction | `s06` over the row-text chunk: `North/South/East/West → location`, `2021…2023 → temporal`, revenue figures → `monetary` (regex/spaCy); each with a confidence audit |
| Relationship detection | co-occurrence inside the chunk → e.g. `(South)-[related_to]->(5300000 USD)`; predicate constrained by ontology |
| Ontology | `s10.govern` checks each pair; `related_to` is `ANY` ⇒ `auto_accept`; a mis-typed `has_revenue(location→monetary)` would be `reject` ⇒ lowers `ontology_consistency` |
| Knowledge graph | `s11` resolves/creates canonical nodes; `s12` upserts nodes + confidence-weighted edges into `data/graph/canonical_graph.json`; triples to `data/graph/{id}_triples.json` |
| Confidence ledger | `confidence_ledger.build` records each node's score across the 5 layers → `data/confidence/matrix.json` |
| Observatory UI | KPI tiles (nodes/edges/density/trust), Data Quality → revenue histogram/box/QQ, Correlation heatmap, KG Analytics top-entities table, Semantic Heatmap row per entity, AI Trust gauges |

---

# 17. Assumptions and Limitations

- **Exact/true statistics:** all `_stats` numeric metrics (mean/median/std/skew/kurtosis/iqr/
  histogram/qq/correlation/outliers), graph counts (nodes/edges/density/components/orphans), chunk
  coverage, consistency-check counts. These are deterministic and reproducible.
- **Proxy/trust scores (not probabilities):** entity confidence, edge confidence, `graph_trust_score`,
  `hallucination_risk`, `calibration_error`, `metadata_coverage`, per-layer confidence ledger,
  `recall@5`/`MRR` (**bootstrapped** from high-confidence extractions when no curated gold exists,
  `s09.validate gold_bootstrapped=true`). Treat as relative indicators, not guarantees.
- **AI-inferred:** entity spans (spaCy) and embedding similarity (sentence-transformers). Both have a
  deterministic fallback (regex NER / hash embeddings) that **silently reduces quality** when the
  models aren't installed — a key correctness caveat. **No LLM is used**, so there is no generative
  hallucination, but relation extraction is shallow (co-occurrence) and can create spurious edges →
  this is exactly what `hallucination_risk` (generic-relation rate) and the ontology gate are meant
  to flag.
- **Needs human review:** anything routed to `review_required` by `s10`; canonical merges in
  `registry.pending_reviews` (score 0.58–0.72); low-confidence edges; high `hallucination_risk`.
- **Known limitations:** no real OCR (flag only); no keyword extraction; ontology is hand-seeded (no
  learned classes/attributes); relationships are co-occurrence-based (no dependency parsing in the
  default path); `average_path_length` and cross-run history (entity/relationship growth, graph
  stability) are **deferred** (empty states); retrieval accuracy is a proxy (no real query engine);
  the **Relationship Health Matrix / table-join discovery** from the legacy backend is **not** ported.

---

# 19. Beginner-Friendly Summary

- **What it does:** you give SIO documents or a database; it reads them, pulls out the important
  "things" (people, organizations, places, money, dates) and the links between them, checks those
  links make sense, and builds a **knowledge graph** you can explore — with dashboards that tell you
  how trustworthy the result is.
- **Why ingestion:** raw files come in many shapes (PDF, CSV, DB). Ingestion turns all of them into
  one consistent internal format (text + tables + chunks) so the rest of the pipeline can work
  uniformly.
- **Why EDA:** before trusting any analysis you must know your data — how complete each column is,
  how values are distributed, whether there are outliers or duplicates, and how dense the resulting
  graph is. EDA computes those facts.
- **Why ontology:** a graph is only useful if its links are *meaningful*. The ontology is a rulebook
  ("a company can have revenue; a city cannot") that filters out nonsense links **before** they enter
  the graph, which is how SIO keeps quality high.
- **Why a knowledge graph:** it connects scattered facts from many sources into one queryable,
  explainable structure — each node and edge remembers where it came from (provenance).
- **Why the Observatory:** it's the cockpit. It shows the statistics (Data Quality, Correlation),
  the graph itself (KG Analytics, Graph Trust), per-stage confidence (Semantic Heatmap), extraction
  quality, and one "are we production-ready?" score (AI Trust Center) — always computed from real
  ingested data, never placeholders.
- **How it connects:** upload → 14 backend layers (`pipeline.py`) → JSON artifacts under `data/` →
  served via `/sio/*` endpoints (`main.py`) → rendered by the React Observatory & Semantic OS pages.
