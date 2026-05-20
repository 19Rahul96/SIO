## Plan: Cross-Source DB-Corpus Linking via Graphify

Add a dedicated cross-source linker stage so DB schema entities (from Graphify + profiling) and corpus entities (from document extraction) are connected even without column descriptions. Reuse existing canonical graph, embedding, review, and wiki systems; add conservative confidence gating and review lifecycle to keep reliability high.

**Steps**
1. Phase 1: Add a new linker service module [backend/cross_source_linker.py](backend/cross_source_linker.py) with deterministic + semantic matching for DB↔corpus entities. Output accepted edges, review-needed candidates, and rejection reasons. 
Depends on: existing canonical graph and embeddings.
2. In linker matching logic, use three gates in order: normalized lexical match, semantic-label compatibility (from DB profile/dictionary), and embedding similarity threshold. 
Parallel with step 3.
3. Add confidence policy constants and score breakdown payloads (exactly like existing merge-review style), including low-confidence routing to a pending review queue artifact under processed data.
Parallel with step 2.
4. Phase 2: Wire linker into DB pipeline in [backend/db_processing.py](backend/db_processing.py) after map_graphify_to_canonical and before merge_into_canonical. Ensure accepted cross-links are merged as canonical edges and report is attached to DB status/summary.
Depends on: steps 1-3.
5. Wire linker into corpus pipeline in [backend/processing.py](backend/processing.py) after resolve_canonical_graph and before upsert_canonical_graph, so both directions (DB-first and corpus-first) create links.
Depends on: steps 1-3.
6. Persist cross-link artifacts: add data/processed/{source_id}_cross_links.json with accepted/review/rejected sets, score stats, and source coverage metrics.
Depends on: steps 4-5.
7. Add API endpoints for discoverability and governance in [backend/main.py](backend/main.py):
- GET /links/cross-source/{source_id}
- GET /links/reviews
- POST /links/review/{review_id}
- GET /links/metrics
Depends on: steps 4-6.
8. Integrate cross-link metrics into [backend/main.py](backend/main.py) quality snapshot (/quality/metrics): link coverage, approved ratio, pending backlog, and rejected ratio.
Depends on: step 6.
9. Phase 3: Extend wiki integration in [backend/wiki_builder.py](backend/wiki_builder.py) so cross-source relations appear as cited facts and enrich nanoWiki explanations.
Depends on: steps 4-6.
10. Add safety controls: keep only high-confidence links active, send medium-confidence to review, allow suppress/restore through existing repair patterns in [backend/graph_builder.py](backend/graph_builder.py).
Depends on: steps 4-8.

**Relevant files**
- [backend/db_processing.py](backend/db_processing.py) — primary DB pipeline hook for linker insertion and status/summary reporting.
- [backend/processing.py](backend/processing.py) — corpus pipeline hook for reciprocal cross-link generation.
- [backend/db_graphify.py](backend/db_graphify.py) — DB graph mapping inputs to linker (canonical nodes/edges and provenance).
- [backend/entity_resolution.py](backend/entity_resolution.py) — threshold and review-decision patterns to reuse for confidence routing.
- [backend/embedding.py](backend/embedding.py) — embedding function reuse for semantic similarity scoring.
- [backend/graph_builder.py](backend/graph_builder.py) — canonical edge persistence and suppression controls.
- [backend/wiki_builder.py](backend/wiki_builder.py) — nanoWiki enrichment from accepted cross-source links.
- [backend/main.py](backend/main.py) — API endpoints and quality metrics exposure.
- [backend/data_dictionary.py](backend/data_dictionary.py) — semantic label/business-definition source for missing column descriptions.
- [backend/db_profiler.py](backend/db_profiler.py) — column/table semantics used as linking priors.
- [backend/cross_source_linker.py](backend/cross_source_linker.py) — new module to implement.

**Verification**
1. Run DB ingestion with real credentials and verify status includes cross-link report summary in DB status response.
2. Upload at least one corpus file with related domain terms; verify cross-link artifact file is generated for both DB and corpus source IDs.
3. Call GET /links/cross-source/{source_id} and confirm accepted links include score breakdown + provenance.
4. Call GET /links/reviews and POST /links/review/{review_id}; verify lifecycle transition reflected in metrics.
5. Verify /quality/metrics includes cross-link coverage and pending backlog.
6. Run /query and /db/query and verify responses include relations drawn from approved cross-source links.
7. Check wiki pages for linked entities and confirm citations include both DB and corpus provenance where available.

**Decisions**
- Included scope: robust DB↔corpus relation linking without relying on human-provided descriptions.
- Included scope: conservative precision-first acceptance with review workflow.
- Excluded scope: automatic self-learning threshold retraining (deferred to phase 2 optimization).
- Excluded scope: full scheduler/daemon for continuous validation; this stays event-driven by ingestion for now.

**Further Considerations**
1. Threshold policy recommendation: Option A strict (fewer false links), Option B balanced default, Option C aggressive discovery mode.
2. Review queue storage recommendation: Option A keep in processed artifacts, Option B integrate into canonical registry reviews for a single moderation surface.
3. Provenance recommendation: enforce dual-source provenance fields on every accepted cross-link to improve auditability and hallucination defense.