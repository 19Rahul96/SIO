## Code Creator Ready Prompt (Phase 1 triggered from EDA Visual button)

Implement Phase 1 of the enterprise EDA Dashboard in the existing AI-Orchestrator codebase, with the user journey starting when the EDA Visual button is clicked in Inject flow.

Primary trigger and UX flow
- Trigger from EDA Visual button in /home/neelam/AI-Orchestrator/frontend/src/pages/InjectPage.jsx.
- Open EDA modal viewer and fetch merged analytics using existing API path through /home/neelam/AI-Orchestrator/frontend/src/services/api.js getEdaDashboard.
- Keep behavior non-blocking: if any EDA subsection fails or is missing, render partial sections with clear empty states.

Do not break existing contracts
- Additive schema only in backend responses. Do not rename or remove existing fields already used by Dashboard/Results/EDA viewer.
- Preserve existing ingestion and processing flow; EDA failures must never block ingestion completion.

Unified Chart Data Contract Layer (highest priority)
- Add a normalized chart payload contract between backend analytics and frontend chart rendering.
- Sections must request charts by semantic purpose, not by direct library-specific config.
- Frontend wrappers choose renderer by chart_type and library_hint.

Normalized chart payload shape
- {
  "chart_id": "correlation.pearson",
  "section": "correlation",
  "chart_type": "heatmap",
  "library_hint": "echarts",
  "title": "Pearson Correlation",
  "description": "Pairwise linear correlation across selected numeric fields",
  "data": {
    "x": [],
    "y": [],
    "values": []
  },
  "options": {
    "tooltip": true,
    "legend": true,
    "xAxisLabelRotate": 0,
    "yAxisLabelRotate": 0
  },
  "meta": {
    "source": "db|file|combined",
    "supports_drilldown": false,
    "empty_reason": null
  }
}

Contract rules
- Keep existing summary/file_eda/db_eda blocks untouched for backward compatibility.
- Add a new additive block charts_contract at run-level and top-level.
- Every section should return chart cards even when empty, with meta.empty_reason populated.
- Use capability flags plus chart availability to support progressive rendering.

Phase 1 scope to implement now
0. Contract-first foundation
- Introduce charts_contract payload builder in backend aggregation.
- Add frontend chart registry that maps chart_type/library_hint to wrapper components.
- Keep legacy fields as fallback source while contract adoption rolls out.

1. KPI and Data Health section
- Add cards for total records, total columns, missing percent, duplicate rows, anomaly count, file size, entities extracted, relationships extracted, schema drift count, orphan relationships, processing time, timestamp coverage percent.
- Add visuals: schema tree, datatype distribution, completeness donut, null matrix summary, completeness heatmap summary, health score gauge, duplicate distribution.
- Health score formula must be deterministic and documented as weighted combination of completeness, consistency, uniqueness, validity, anomaly ratio.

2. Correlation and dependency section (bounded)
- Pearson heatmap and Spearman heatmap for numeric columns.
- Covariance matrix summary.
- Correlation pair explorer list with strongest positive and strongest negative pairs.
- Add VIF only when enough numeric features exist; otherwise show not applicable state.

3. Outlier and anomaly section (deterministic)
- Z-score anomalies and IQR outlier detection.
- Summary cards for anomaly counts and affected columns/tables.
- Visuals: box plot summaries, z-score distribution bins, anomaly scatter summary.
- Do not implement Isolation Forest in Phase 1.

4. Consistency and validation section
- Detect invalid dates, broken schema/type mismatches, enum violations, null key violations, duplicate entity IDs, orphan relationships, foreign key issues, schema drift, inconsistent labels.
- Render validation error table plus consistency summary cards.

5. Statistical analysis section
- Histograms, KDE-like distribution approximation, box and violin style summaries, QQ summary points, skewness and kurtosis indicators, percentile spread.
- Compute and return mean, median, variance, standard deviation, skewness, kurtosis, percentile distribution.

6. Time series section (only when timestamps exist)
- Trend chart data, moving averages, rolling volatility, spike detection.
- If insufficient timestamp quality/coverage, return capability false and render smart empty state.
- Do not implement forecasting or decomposition in Phase 1.

7. Knowledge graph analytics section (basic)
- Reuse existing KG data sources and graph viewer integration.
- Show entity/relationship distributions and graph metrics: degree centrality, betweenness centrality, pagerank, connected components, graph density.
- Embed mini preview and provide open-full-graph action using existing graph modal flow.

8. Executive summary section
- Deterministic rule-based insights generated from actual computed EDA findings.
- Include severity, business impact hint, recommendation, and confidence score per insight.
- No mandatory LLM dependency in Phase 1.

Backend implementation targets
- /home/neelam/AI-Orchestrator/backend/main.py
- /home/neelam/AI-Orchestrator/backend/processing.py
- /home/neelam/AI-Orchestrator/backend/db_processing.py
- /home/neelam/AI-Orchestrator/backend/file_eda_service.py
- /home/neelam/AI-Orchestrator/backend/eda_engine.py
- /home/neelam/AI-Orchestrator/backend/db_profiler.py
- Optional new helper only if needed: /home/neelam/AI-Orchestrator/backend/ai_summary_engine.py

Frontend chart/runtime targets
- /home/neelam/AI-Orchestrator/frontend/src/components/EDAVisualsViewer2.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/eda2/charts/ChartRenderer.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/eda2/charts/RechartsPanel.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/eda2/charts/EChartsPanel.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/eda2/charts/PlotlyPanel.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/eda2/charts/CytoscapePanel.jsx

Frontend implementation targets
- /home/neelam/AI-Orchestrator/frontend/src/components/EDAVisualsViewer.jsx
- /home/neelam/AI-Orchestrator/frontend/src/services/api.js
- /home/neelam/AI-Orchestrator/frontend/src/pages/InjectPage.jsx
- /home/neelam/AI-Orchestrator/frontend/src/components/GraphRAGViewer.jsx
- Optional split components if needed: EDAOverviewTab.jsx, CorrelationPanel.jsx, TimeSeriesPanel.jsx, KGAnalyticsPanel.jsx, AIInsightsPanel.jsx, ValidationPanel.jsx

Library recommendation mapping
- Recharts: KPI cards, compact trend lines, moving averages, section-level summary bars.
- ECharts: correlation/null/completeness heatmaps and dense matrix visuals.
- Plotly: box/violin/QQ/histogram/scatter plots for advanced stats and outlier analysis.
- Cytoscape.js: interactive graph panel for section 7.

Contract requirements
- Extend /eda/dashboard response with additive nested blocks:
  - capabilities
  - core_kpis
  - data_health
  - correlation
  - outliers
  - consistency_checks
  - statistical_profiles
  - time_series
  - kg_analytics
  - executive_summary
- Add charts_contract block:
  - top-level charts_contract.sections[]
  - per-run charts_contract.sections[]
  - each section contains chart cards in normalized format using chart_type + library_hint
- Keep existing summary, file_eda, db_eda fields intact.
- Include per-run capabilities flags: supports_time_series, supports_correlation, supports_kg_metrics, supports_feature_importance.

Performance and resilience constraints
- Cap correlation matrix dimensions to top numeric columns by completeness and variance.
- Return summarized bins/aggregates, not raw high-volume vectors.
- Keep API payload lightweight enough for modal rendering.
- Ensure graceful degradation for non-tabular sources like PDF/text.
- Lazy-load chart libraries by section tab to avoid heavy initial bundle cost.
- Keep one chart registry layer so chart-library swaps do not require section rewrites.

Acceptance criteria
1. Clicking EDA Visual opens modal and displays Phase 1 sections from real computed data.
2. Existing EDA and dashboard cards continue working without regressions.
3. Ingestion and processing complete even if one EDA sub-analysis fails.
4. Smart empty states appear where source data does not support a section.
5. UI is responsive on desktop and mobile widths.
6. Backend and frontend remain backward compatible.
7. Section rendering depends on unified chart contract cards, not direct library-specific mappings.
8. Library migration or replacement can be done by updating chart wrappers only.

Validation steps
- Run backend from /home/neelam/AI-Orchestrator/backend and frontend from /home/neelam/AI-Orchestrator/frontend.
- Test with at least one file ingest and one DB ingest.
- Verify /eda/dashboard includes new additive blocks and existing fields.
- Verify EDA Visual modal renders each section conditionally based on capabilities.
- Confirm no blocking failure in ingestion status when EDA section errors are injected.
- Verify chart cards render through chart registry using chart_type + library_hint.
- Verify each section still renders when charts_contract is missing by using legacy fallback mapping.

Out of scope for this task
- Feature importance models, Isolation Forest, DBSCAN, autoencoder, seasonality decomposition, forecasting, Louvain community detection, suspicious subgraph detection.
- Keep these as explicit Phase 2 backlog placeholders only.

Phase 1 execution order (updated)
1. Add charts_contract schema and builder utilities in backend (additive only).
2. Add frontend chart registry + wrapper components.
3. Migrate Section 1, 2, 6 to contract-driven charts first.
4. Migrate Section 3 and 5 advanced charts via Plotly wrappers.
5. Migrate Section 7 to Cytoscape wrapper with GraphRAG deep-link fallback.
6. Keep deterministic section cards as fallback for any chart with empty_reason.
