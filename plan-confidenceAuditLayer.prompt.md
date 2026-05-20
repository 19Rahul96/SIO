## Plan: End-Of-Ingestion Confidence Audit Layer

Add a complete audit layer (confidence, evidence, citations, trace) for entities, relationships, retrieved chunks, and final answers, without breaking current functionality. Surface the audit output through a new View Confidence Audit button at the end of ingestion (next to the existing View GraphRAG action), opening a modal/dashboard that explains confidence and policy decisions.

**Steps**
1. Scope lock and non-regression guardrails
Freeze these constraints:
- No changes to existing endpoint request schemas.
- No removal/rename of current response fields.
- No changes to ingestion, embedding/FAISS logic, router scoring, Graphify execution, or page-step flow.
- Additive fields and optional UI rendering only.
- Introduce a backend mode flag:
  - observe_only (default): annotate confidence and policy actions only.
  - enforce: apply accept/review/reject decisions.
Depends on: none.

2. Audit schema definition (single contract)
Define reusable audit objects used across artifacts:
- confidence: score (0..1), band (high/medium/low), formula_version.
- evidence: component inputs and counts used for scoring.
- citations: list of source references (file_id, chunk_idx, excerpt/provenance).
- trace: scorer name/version, stage, timestamp, optional decision path.
- policy: action (auto_accept/review_required/reject), reason summary.
Apply to:
- entity_audit
- relationship_audit
- chunk_audit
- answer_audit
Depends on: step 1.

3. Confidence model and normalization policy
Use weighted relationship formula v1:
Final Edge Confidence =
0.30 x LLM relation score +
0.25 x Evidence support +
0.20 x Entity confidence +
0.15 x Schema validity +
0.10 x Cross-source support.
Add safeguards:
- Normalize every component to 0..1.
- Missing-signal renormalization over available components.
- Minimum evidence floor to prevent unjustified high confidence.
- Confidence bands:
  - high >= 0.75
  - medium >= 0.50 and < 0.75
  - low < 0.50
Map to policy actions:
- high -> auto_accept
- medium -> review_required
- low -> reject
Depends on: step 2.

4. Backend signal mapping table
Map formula inputs to existing computed signals:
- LLM relation score from graph relevance scoring in [backend/graph_builder.py](backend/graph_builder.py).
- Evidence support from provenance, citation counts, retrieval overlap in [backend/main.py](backend/main.py) and [backend/wiki_builder.py](backend/wiki_builder.py).
- Entity confidence from canonical node confidence in [backend/graph_builder.py](backend/graph_builder.py).
- Schema validity from ingestion/quality signals in [backend/main.py](backend/main.py).
- Cross-source support from db cross-linking outputs in [backend/db_graphify.py](backend/db_graphify.py).
Document fallback behavior when any signal is unavailable.
Depends on: step 3.

5. Backend confidence computation utilities
Add internal helper functions (no external contract break):
- compute_relationship_confidence(...)
- compute_entity_confidence(...)
- compute_chunk_confidence(...)
- compute_answer_confidence(...)
- assign_policy_action(...)
Return audit payloads as additive metadata only.
Depends on: step 4.

6. API augmentation (additive fields only)
Attach audit metadata to existing responses:
- query and final-run responses in [backend/main.py](backend/main.py): answer_audit + per-item audits.
- graph and canonical graph responses: relationship/entity audit blocks.
- ingestion status/report payloads: ingestion-level audit summary.
Ensure old consumers still work unchanged if they ignore new keys.
Depends on: step 5.

7. Review queue integration for medium-confidence relationships
In observe_only mode:
- annotate medium relationships with review_required and push summary into review payloads.
In enforce mode:
- medium remains pending review.
- low is marked reject path.
- high auto-accepted.
Reuse existing review endpoints/workflows and keep backward compatibility.
Depends on: step 6.

8. End-of-ingestion UX entry point (button)
In [frontend/src/pages/InjectPage.jsx](frontend/src/pages/InjectPage.jsx):
- Keep existing View GraphRAG button unchanged.
- Add adjacent View Confidence Audit button on the same completed-ingestion card.
- Button visibility condition: same as completed-ingestion state (completedFileIds length > 0).
- On click open new audit modal/viewer.
No change to Continue to prompt flow.
Depends on: step 6.

9. New confidence audit viewer modal
Add a new component similar to Graph viewer pattern:
- Proposed file: [frontend/src/components/ConfidenceAuditViewer.jsx](frontend/src/components/ConfidenceAuditViewer.jsx).
- Tabs/sections:
  - Summary (overall confidence, distribution, decision counts)
  - Relationships (score, band, action, why)
  - Entities (confidence and evidence)
  - Chunks (retrieval confidence and citations)
  - Answers (answer confidence, faithfulness context, trace)
- Drill-down panel for why and evidence sources.
- Graceful empty/error states.
Depends on: step 8.

10. Frontend API and store extension (optional fields)
Update [frontend/src/services/api.js](frontend/src/services/api.js) with additive methods if needed:
- getIngestionAudit or equivalent endpoint fetcher.
Store optional audit payloads in [frontend/src/store/index.js](frontend/src/store/index.js) without altering existing state consumers.
Use defensive optional reads throughout UI.
Depends on: steps 6 and 9.

11. Visual language and usability
Use existing UI primitives from [frontend/src/index.css](frontend/src/index.css):
- confidence chips (high/medium/low)
- policy badges (auto_accept/review_required/reject)
- expandable why/evidence rows
Keep the modal readable on desktop and mobile.
Depends on: step 9.

12. Observability and calibration
Add backend logs/metrics:
- score distributions by artifact type
- policy decision counts
- missing-signal frequency
- high-confidence but low-evidence anomalies
Calibrate thresholds with sampled historical sessions before enabling enforce mode.
Depends on: step 6.

13. Rollout plan
Phase 1: observe_only + UI display only (safe).
Phase 2: medium-confidence review workflow visible and active.
Phase 3: optional enforce mode for selected pipelines.
Feature-flag each phase for quick rollback.
Depends on: steps 7, 10, 12.

**Relevant files**
- [backend/main.py](backend/main.py) — additive audit assembly in query/final-run and ingestion-level outputs.
- [backend/graph_builder.py](backend/graph_builder.py) — relationship/entity scoring inputs.
- [backend/wiki_builder.py](backend/wiki_builder.py) — citations/evidence support.
- [backend/db_graphify.py](backend/db_graphify.py) — cross-source support features.
- [backend/entity_resolution.py](backend/entity_resolution.py) — review integration path.
- [frontend/src/pages/InjectPage.jsx](frontend/src/pages/InjectPage.jsx) — new end-of-ingestion View Confidence Audit button.
- [frontend/src/components/GraphRAGViewer.jsx](frontend/src/components/GraphRAGViewer.jsx) — reference modal pattern to mirror.
- [frontend/src/components/ConfidenceAuditViewer.jsx](frontend/src/components/ConfidenceAuditViewer.jsx) — new modal for audit output.
- [frontend/src/services/api.js](frontend/src/services/api.js) — additive audit fetch methods.
- [frontend/src/store/index.js](frontend/src/store/index.js) — optional audit state.
- [frontend/src/index.css](frontend/src/index.css) — confidence/policy badges.

**Verification**
1. Backward compatibility
Existing ingestion, prompt, model, and final-run UI flows still function with no required field changes.
2. End-of-ingestion button behavior
After at least one file is completed, View Confidence Audit appears and opens modal successfully.
3. Artifact coverage
Entities, relationships, chunks, and answers all carry audit metadata.
4. Policy correctness
Band-to-action mapping works and is visible in UI.
5. Observe-only safety
No merge/retrieval behavior changes in observe_only mode.
6. Enforce-mode readiness
When toggled in test env, medium routes to review and low routes to reject paths as designed.
7. Performance
Confidence computation adds acceptable latency and no blocking regressions.

**Decisions**
- Include full audit layer now, enforce later.
- Preserve all current functionality through additive metadata.
- Use end-of-ingestion button entry to make confidence output discoverable at the exact user moment requested.
- Keep policy actions visible immediately, but behavior-changing enforcement behind flag.

**Further Considerations**
1. Confidence threshold ownership
Option A: global thresholds. Option B: per-domain thresholds.
Recommendation: start global, tune per-domain later.
2. Review queue coupling
Option A: reuse current review API payloads. Option B: dedicated audit review endpoint.
Recommendation: reuse existing first for lower risk.
3. Modal complexity
Option A: compact summary + expandable details. Option B: full table-first view.
Recommendation: compact summary first for usability.