# Semantic Intelligence OS

An AI-native semantic intelligence platform implementing the 14-layer **AI Data
Orchestrator** architecture as a clean, standalone service. Each layer progressively
increases semantic trust and validates relationships **before** they enter the
knowledge graph.

> Scope note: this folder implements the 14-step target architecture only. The
> carry-forward retrieval/SLM/DB items and the cross-cutting enterprise-hardening
> track (durable queue, auth, transactional storage) from
> `../plan-semanticIntelligenceOS.md` are intentionally **out of scope here**.

## The 14 layers (trust-building order)

| # | Layer | Module | Produces |
|---|-------|--------|----------|
| 1 | File Upload + Lineage | `s01_upload` | source record, fingerprint, lineage |
| 2 | Ingestion & Extraction | `s02_extraction` | corpus + parser confidence |
| 3 | Cleaning + Normalization | `s03_normalization` | normalized text + transform log |
| 4 | Chunking + Segmentation | `s04_chunking` | chunks + coverage validation |
| 5 | Metadata Intelligence | `s05_metadata` | semantic labels, PK/FK prediction |
| 6 | Entity + Relationship Extraction | `s06_entity_relation` | grounded entities/relations |
| 7 | Semantic Learning | `s07_semantic_learning` | semantic memory + adaptive priors |
| 8 | EDA Intelligence | `s08_eda` | graph/semantic/drift EDA |
| 9 | ML Validation & Accuracy | `s09_validation` | P/R/F1, calibration, trust score |
| 10 | Ontology & Governance (gate) | `s10_ontology` | ontology + accept/review/reject |
| 11 | Canonicalization | `s11_canonicalization` | canonical registry + alias merge |
| 12 | KG Construction | `s12_graph` | confidence-weighted graph + RDF triples |
| 13 | Graph Consistency | `s13_graph_consistency` | orphan/cycle/violation/trust report |
| 14 | Wiki + Explainability | `s14_wiki` | cited, explained entity pages |

## Design principles honored

- **Pre-insertion governance gate** (Step 10) — edges are validated against the
  ontology *before* graph construction (Step 12).
- **Observe vs enforce** — set `SIO_GOVERNANCE_MODE=observe_only` (default) or
  `enforce`. Observe annotates verdicts without blocking; enforce excludes
  rejects/reviews from auto-insertion.
- **Explainability everywhere** — a single `audit` contract (confidence/evidence/
  citations/trace/policy) flows through every layer.
- **Graceful degradation** — missing optional deps (spaCy, sentence-transformers,
  pypdf) fall back to regex / deterministic-hash paths so the pipeline always runs.
- **Adaptive learning** — semantic memory persists across ingestions and feeds merge
  priors, ontology, and drift detection.

## Run

```bash
cd semantic_intelligence_os
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: python -m spacy download en_core_web_sm
uvicorn app.main:app --reload --port 8020
```

### Key endpoints

- `POST /ingest` — multipart file upload → runs the full 14-layer pipeline, returns run report
- `GET /run/{source_id}` — full per-stage run report
- `GET /lineage|metadata|eda|validation|governance/{source_id}` — per-layer artifacts
- `GET /ontology` · `POST /ontology/predicate` — inspect / evolve the ontology
- `GET /graph` · `GET /graph/consistency` — canonical graph + continuous validation
- `GET /wiki/pages` · `GET /wiki/page/{canonical_id}` — explainable entity pages

## Smoke test

```bash
python -m app.smoke_test     # runs the pipeline on a synthetic document, no server needed
```

## Layout

```
app/
  config.py            # settings + GovernanceMode flag
  pipeline.py          # 14-layer orchestrator
  main.py              # FastAPI surface
  contracts/           # audit contract + embedding utility
  layers/s01..s14      # one module per architecture layer
  storage/jsonstore.py # atomic JSON persistence
data/                  # runtime artifacts (per-stage, traceable)
```

## Not yet built (future UI track)

The futuristic observability UI (KG explorer, ontology explorer, hallucination
observatory, trust command center, embedding universe, wiki+graph dual view) consumes
the endpoints above. Backend artifacts are shaped to feed those dashboards.
