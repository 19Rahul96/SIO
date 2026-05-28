# EDA Visuals2 Metric Logic Documentation

## Scope
This document covers implemented metric logic used by the Visuals2 dashboard in:
- `frontend/src/components/EDAVisualsViewer2.jsx`
- `backend/eda_engine.py`
- `backend/main.py` (`_build_eda_dashboard_payload`)
- `backend/processing.py` (`_build_file_phase1_blocks`, file run fallbacks)
- `backend/db_processing.py` (`get_eda_visuals`)

It reflects current behavior only.

## Global Rules (applies to all tabs)

| Metric/Rule | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Selected run | All | `EDAVisualsViewer2.jsx` / `runRichness`, `selectedRun` | `core_kpis`, `eda_summary`, `entity_distribution`, `top_tables`, `node_centrality` | Run with highest richness score is selected: `total_records + total_columns + entities_extracted + table_count + anomalous_table_count + list lengths` | Internal object | Chooses most information-dense run for display | Proxy selection heuristic |
| Number formatting | All | `EDAVisualsViewer2.jsx` / `num`, `pct`, `scorePct`, `fmtMs`, `fmtBytes` | Numeric values | Locale number, percent, rounded score, ms/s, byte units | Text | Display formatting only | N/A |
| Correlation heatmap tone | Correlation | `EDAVisualsViewer2.jsx` / `corrTone` | Correlation value `v` | Color thresholds: `>=0.7`, `>=0.35`, `<=-0.7`, `<=-0.35`, else neutral | Color cell | Visual severity coding | Proxy visual cue |

## 1) KPI & Health

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Total records | KPI & Health | `EDAVisualsViewer2.jsx` / `derived.kpisMerged.total_records` | `core_kpis.total_records` else entity/table fallback | DB: from `eda_engine core_kpis.total_records` (sum sample sizes). File: `max(text_block_count, table_row_count)` in `_build_file_phase1_blocks` | Integer | Approximate record volume | Proxy for corpus volume |
| Total columns | KPI & Health | `derived.kpisMerged.total_columns` | `core_kpis.total_columns` else top table fallback | DB: total profiled columns. File: entity type count | Integer | Schema/feature breadth | Proxy |
| Missing % | KPI & Health | `derived.kpisMerged.missing_pct` | `core_kpis.missing_pct` | DB: `(1 - completeness) * 100`; completeness = `1 - total_missing/total_columns`. File: `100 - chunk_coverage_pct` | Percent (2 dp) | Missingness level | Proxy data-quality signal |
| Duplicate rows | KPI & Health | `core_kpis.duplicate_rows` | DB: duplicate proxy from sample uniqueness; File: duplicate entity count | DB uses per-column `sample_size - unique_in_sample` aggregation | Integer | Potential duplication issue | Proxy |
| Anomaly count | KPI & Health | `core_kpis.anomaly_count` | DB anomaly columns; File semantic anomalies + ontology violations | DB: total columns flagged by anomaly rules; File: numeric anomaly count + ontology violation count | Integer | Volume of detected issues | Proxy |
| File size | KPI & Health | `core_kpis.file_size` | Status/file metadata | Pass-through | Bytes string | Input payload size | True raw metadata |
| Entities | KPI & Health | `core_kpis.entities_extracted` | Extraction counts | Pass-through/fallback | Integer | Entity extraction output size | True count (pipeline output) |
| Relationships | KPI & Health | `core_kpis.relationships_extracted` | Relationship evidence/count | Pass-through/fallback | Integer | Relationship extraction output size | True count (pipeline output) |
| Schema drift | KPI & Health | `core_kpis.schema_drift_count` | DB semantic labels unknown; File type conflicts | DB: count tables with unknown semantic label; File: semantic type conflict count | Integer | Schema inconsistency indicator | Proxy |
| Orphan relationships | KPI & Health | `core_kpis.orphan_relationships` | Joinability signals / orphan entities | DB: weak joinability count; File: orphan entity count | Integer | Connectivity weakness indicator | Proxy |
| Processing time | KPI & Health | `core_kpis.processing_time_ms` | uploaded/completed timestamps or runtime | Runtime or `(completed_at - uploaded_at)*1000` | ms/s text | Pipeline duration | True runtime metric |
| Timestamp coverage | KPI & Health | `core_kpis.timestamp_coverage_pct` | DB datetime-like columns / total columns, file temporal consistency score | DB: `100 * timestamp_detected_columns/total_columns`; File: `temporal_consistency_score * 100` | Percent (2 dp) | Temporal signal availability | Proxy |
| Completeness complete/missing | KPI & Health | `data_health.completeness` | completeness score | `complete_pct = completeness*100`, `missing_pct = (1-completeness)*100` | Percent | Completeness split | Proxy |
| Null matrix high/medium/low | KPI & Health | `data_health.completeness.null_matrix_summary` | per-column `null_rate` | High `>=0.5`, Medium `[0.2,0.5)`, Low `<0.2` | Integer counts | Null severity distribution | Proxy |
| Health score | KPI & Health | `eda_engine._health_score`; file analog in `_build_file_phase1_blocks` | completeness, consistency, uniqueness, validity, anomaly_ratio | `0.30*c + 0.22*cons + 0.20*u + 0.18*v + 0.10*(1-anomaly_ratio)` clipped `[0,1]` | Percent + gauge | Composite quality index | Proxy quality/trust signal |
| Duplicate distribution by table | KPI & Health | `data_health.completeness.duplicate_distribution` | Per-table duplicate proxy | Sum `(sample_size - unique_in_sample)` per table | Integer by table | Where duplication concentrates | Proxy |
| Datatype distribution | KPI & Health | `data_health.datatype_distribution` | semantic labels/entity types | Frequency count | Type + count + progress bar | Semantic/type makeup | True count over inferred labels |
| Schema tree columns count | KPI & Health | `data_health.schema_tree` | table metadata | count of column entries per table | Integer | Structural layout | True metadata count |

## 2) Correlation

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Pearson matrix | Correlation | `eda_engine.run_eda_engine` | top 10 ranked numeric columns | `_pearson(v1,v2)` pairwise | Matrix heatmap | Linear relation strength | True statistic on sampled values |
| Spearman matrix | Correlation | `run_eda_engine` | same | `_spearman(v1,v2)` pairwise | Matrix heatmap | Monotonic relation strength | True statistic on sampled values |
| Covariance matrix | Correlation | `run_eda_engine` | same | `_covariance(v1,v2)` pairwise | Matrix heatmap | Joint variation magnitude | True statistic |
| Strongest positive pair | Correlation | `run_eda_engine` | Pearson pair list | Max Pearson where `i<j` | Pair + value | Highest positive linkage | True statistic (from computed matrix) |
| Strongest negative pair | Correlation | `run_eda_engine` | Pearson pair list | Min Pearson where `i<j` | Pair + value | Strongest inverse linkage | True statistic |
| Pair explorer rows | Correlation | `run_eda_engine` | pairwise correlations | Sorted by `abs(pearson)` desc, top 40 | List rows | Investigable pair ranking | True computed stats |
| VIF analysis | Correlation | `run_eda_engine` | Pearson matrix rows | For each feature: `max_r2 = max(r^2)` against others, `vif = 1/(1-max_r2)`; status high if `vif>5` | Feature list + availability | Multicollinearity risk proxy | Proxy (VIF from pairwise max-r2, not full regression VIF) |
| Correlation capability flag | Correlation | `capabilities.supports_correlation` | count of corr labels | `len(labels) >= 2` | Boolean gating | Whether to show correlation analytics | Capability proxy |

## 3) Outliers

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Affected columns | Outliers | `outliers.summary.affected_columns` | columns with any outlier counts | count of outlier columns | Integer | Breadth of anomaly impact | Proxy anomaly breadth |
| Z-score anomalies | Outliers | `outliers.summary.zscore_anomaly_count` | per-column z outlier counts | sum of `outliers_zscore_count` | Integer | Tail anomaly volume | True count under threshold rule |
| IQR outliers | Outliers | `outliers.summary.iqr_outlier_count` | per-column IQR outlier counts | sum of `outliers_iqr_count` | Integer | IQR-rule anomaly volume | True count under threshold rule |
| Per-column zscore outliers | Outliers | `run_eda_engine` stats profile | numeric values | z-score outlier if `abs((x-mean)/std) >= 3` | Integer by column | Extreme tail points | True count under z-rule |
| Per-column IQR outliers | Outliers | `run_eda_engine` stats profile | numeric values | outlier if `x < Q1-1.5*IQR` or `x > Q3+1.5*IQR` | Integer by column | Distribution outliers | True count under IQR rule |
| Z-score bins | Outliers | `stats_profiles.zscore_bins` | z values | Bands: `<-3`, `-3..-2`, `-2..2`, `2..3`, `>3` | Bin counts | Tail composition | True binned counts |
| Top columns by burden chart | Outliers | `EDAVisualsViewer2.jsx` / `section3Charts` | per-column `iqr`, `z` | `total = iqr + z`; sort desc; top 12 | Bar chart | Prioritized anomaly workload | Proxy prioritization |
| Detection method split chart | Outliers | `section3Charts` | `iqr`, `zscore` | Stacked IQR vs Z-score by column | Stacked bar | Whether anomalies are distributional vs tail-driven | Proxy diagnostic |
| Burden share chart | Outliers | `section3Charts` | top totals | Share among top 6 + Others | Donut | Concentration of anomaly burden | Proxy concentration signal |
| Method disagreement trend | Outliers | `section3Charts` | `iqr`, `zscore` | `imbalance = abs(iqr-zscore)` | Line chart | Stability/disagreement indicator | Proxy confidence diagnostic |
| IQR vs Z scatter | Outliers | `section3Charts` | `iqr`, `zscore` | points `(iqr, z)` with reference `y=x` | Scatter | Compare detection methods per column | Proxy diagnostic |
| Severity badge (High/Medium/Low) | Outliers | `EDAVisualsViewer2.jsx` / `section3TopColumns` | top 8 totals | `ratio = total/maxTotal`; High `>=0.66`, Medium `>=0.33`, else Low | Badge text + color | Immediate triage level | Proxy thresholding |

## 4) Validation

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Invalid dates | Validation | `run_eda_engine` | datetime-like sample parsing | `invalid = sample_count - parsed_dates` | Integer | Date parse failures | True count on sampled values |
| Type mismatches | Validation | `run_eda_engine` | semantic numeric columns | if sample size>=6 and parse rate <0.8, mismatches count = non-parsable | Integer | Type conformity issue | True rule-based count |
| Enum violations | Validation | `run_eda_engine` | low-cardinality samples | if sample size>=8 and cardinality<=10 and rare labels>=2 then violation count=rare | Integer | Suspected enum noise | Proxy rule-based count |
| Null key violations | Validation | `run_eda_engine` | identifier/unknown semantic columns | if null rate >0 then count `round(null_rate*sample_size)` | Integer | Key nullability issue | Proxy rule-based count |
| Duplicate entity IDs | Validation | DB default 0; file uses duplicate entity count | entity duplicates | pass-through | Integer | Duplicate identifiers/entities | Proxy depending on source |
| Orphan relationships | Validation | DB weak joinability count; file orphan entities | relationship evidence | count of weak joinability/orphans | Integer | Connectivity consistency issue | Proxy graph-quality signal |
| Foreign key issues | Validation | DB = orphan_relationships; file=disconnected components | joinability / graph connectivity | pass-through derived value | Integer | Referential quality concern | Proxy |
| Schema drift | Validation | DB unknown table semantics; file type conflict count | schema semantic labels | count | Integer | Structural/semantic drift | Proxy |
| Inconsistent labels | Validation | DB default 0; file ontology violation count | semantic report | pass-through | Integer | Label inconsistency | Proxy |
| Validation error table | Validation | `consistency_checks.errors` | collected validation issues | list of `{table,column,check,count,severity}` | Row list | Detailed issue inventory | True captured events under rules |
| Schema drift timeline | Validation | `schemaTimeline` in UI | selected run completed_at, drift count | currently single-point timeline row | Timestamp + count | Temporal drift snapshot | Proxy (single-point) |

## 5) Statistics

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Min/Max/Mean/Median/Variance/Std | Statistics | `run_eda_engine` stats_profiles | sorted numeric values | standard descriptive statistics | Numeric text | Distribution centrality/spread | True descriptive stats |
| Q1/Q3/IQR/P10/P90 | Statistics | `run_eda_engine` | numeric values | percentile-based computations | Numeric text | Robust spread/tails | True descriptive stats |
| Skewness/Kurtosis | Statistics | `run_eda_engine` | moments m3/m4, std | skewness=`m3/std^3`; kurtosis=`m4/std^4 - 3` | Numeric text | Shape diagnostics | True descriptive stats |
| Histogram bins | Statistics | `run_eda_engine` | sorted numeric values | chunked by `bucket_size=max(1,n//8)` with min/max/count per chunk | Bin list + charts | Distribution profile | Approximation (chunk-based bins, not fixed-width) |
| QQ points | Statistics | `run_eda_engine` via sampled QQ | expected vs actual quantiles | sampled QQ pairs | Point list + scatter | Normality check | Approximation (sampled) |
| Distribution chart | Statistics | `section5Charts` | histogram bins | plot count by bin | Bar | Visual distribution | Same as source |
| Spread chart | Statistics | `section5Charts` | min,q1,median,q3,max | plot 5-point summary | Bar | Dispersion profile | Same as source |
| QQ chart | Statistics | `section5Charts` | qq points + y=x | scatter with reference line | Scatter | Deviation from normality | Same as source |
| Skewness vs kurtosis map | Statistics | `section5Charts` | each column skew/kurtosis/std | point size ~ `std_dev` clamped [6,14] | Scatter | Column shape comparison | Proxy visual map |
| Entity/relationship confidence histograms (fallback) | Statistics | file run fallback | confidence bins from visuals | bin counts by confidence range | Bar charts | Confidence distribution | Proxy quality signal |

## 6) Time Series

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Trend points | Time Series | `_build_time_series` | parsed datetime values | daily counts aggregated by date | Date/count list | Activity volume over time | True count from parsed samples |
| Moving average | Time Series | `_build_time_series` | trend counts | 3-point trailing window (`i-2..i`) average | Date/value list | Smoothed trend | True deterministic transform |
| Rolling volatility | Time Series | `_build_time_series` | trend counts | std dev over same trailing window | Date/value list | Local variability | True deterministic transform |
| Event spikes | Time Series | `_build_time_series` | count, window avg/std | spike if `abs(count-avg) >= 2*std`; z proxy=`abs(count-avg)/std` | Date/count/z-proxy list | Candidate temporal anomalies | Proxy anomaly signal |
| Change points (UI) | Time Series | `EDAVisualsViewer2.jsx` / `changePoints` | `trend_points.count` | point if `abs(delta vs previous) >= 3` | Count only in UI | Abrupt changes | Proxy thresholding |
| Time series capability | Time Series | DB/file capabilities | DB: any datetime cols; file: pdf date-like token flag | boolean gating | Boolean | Whether time tab is meaningful | Capability proxy |

## 7) KG Analytics

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Graph density | KG Analytics | DB `eda_engine` kg_analytics; file visuals | DB: relationship evidence and table count; file graph metrics | DB: `len(relationship_evidence) / (table_count*(table_count-1))` clipped by safe division | Percent text | Connectivity density | Proxy structural quality |
| Connected components | KG Analytics | DB/file run payload | DB: `len(table_stats)`; file: disconnected components from graph metrics | pass-through | Integer | Graph fragmentation/cohesion | Proxy structure indicator |
| Entity classes count | KG Analytics | UI counts list length | `entity_distribution` array length | `len(entity_distribution)` | Integer | Type diversity | True count over extracted categories |
| Entity frequency distribution | KG Analytics | run payload | entity type counters | frequency list | type/count rows | Entity type makeup | True count over extracted labels |
| Relationship type distribution | KG Analytics | run payload | relation counters or joinability | frequency list | relation/count rows | Relation makeup | True count over extracted relation labels |
| Centrality preview | KG Analytics | run payload | `node_centrality` list | top labels preview only | text list | Important nodes snapshot | Proxy (depends on underlying centrality routine) |

## 8) AI Summary

| Metric Name | Tab | File/Function | Input Fields | Formula/Rule/Threshold | Output Format | Meaning | Accuracy vs Proxy |
|---|---|---|---|---|---|---|---|
| Insight message | AI Summary | `executive_summary` from run; file/db generators | quality and rule triggers | rule-based message generation | Text | Human-readable finding | Proxy narrative summary |
| Insight severity | AI Summary | `executive_summary` | conditional thresholds in generators | examples: missing% bands, orphan>0, schema drift>0 | Label (high/medium/low) | Priority indicator | Proxy thresholding |
| Insight confidence | AI Summary | `executive_summary` | hardcoded confidences per rule | static values (e.g., 0.78, 0.8, 0.9) | Decimal | Confidence of narrative statement | Proxy (not model-calibrated) |
| Business impact | AI Summary | `executive_summary` | rule templates | templated string | Text | Why metric matters | Proxy narrative |
| Recommendation | AI Summary | `executive_summary` | rule templates | templated action | Text | Suggested next action | Proxy recommendation |
| LLM business summary | AI Summary | `selectedRun.llm_summary` | optional run field | pass-through, fallback text if absent | Text block | Optional model narrative | Proxy unless externally validated |

## Developer Notes

- Dashboard source selection:
  - API `/eda/dashboard` merges DB and file runs.
  - UI then selects one `selectedRun` using a richness heuristic, not necessarily latest run.

- Mixed metric semantics:
  - Some values are strict counts/statistics from sampled data (e.g., Pearson, IQR outlier counts).
  - Many are trust/quality proxies (health score, readiness, drift, severity labels).

- File vs DB asymmetry:
  - File runs use `_build_file_phase1_blocks` with several fallback placeholders (especially correlation/outliers/statistics details).
  - DB runs are richer due to `run_eda_engine` statistical and validation derivations.

- Capability flags gate visibility and chart fallback behavior:
  - `supports_correlation`, `supports_time_series`, `supports_kg_metrics`, `supports_feature_importance`.

- Outlier badge logic is UI-relative:
  - High/Medium/Low depends on ratio to the current top column in view, not a universal threshold.
