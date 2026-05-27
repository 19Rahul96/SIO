import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'
import ChartRenderer from './eda2/charts/ChartRenderer'

function pct(n, digits = 1) {
  return `${(Number(n || 0) * 100).toFixed(digits)}%`
}

function num(n) {
  return Number(n || 0).toLocaleString()
}

function fmtMs(ms) {
  const value = Number(ms || 0)
  if (value < 1000) return `${Math.round(value)} ms`
  return `${(value / 1000).toFixed(2)} s`
}

function fmtBytes(n) {
  const value = Number(n || 0)
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let size = value
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${size.toFixed(idx === 0 ? 0 : 2)} ${units[idx]}`
}

function scorePct(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function safeNum(v, d = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : d
}

function corrTone(v) {
  const value = Number(v || 0)
  if (value >= 0.7) return 'rgba(22,163,74,.75)'
  if (value >= 0.35) return 'rgba(217,119,6,.75)'
  if (value <= -0.7) return 'rgba(220,38,38,.75)'
  if (value <= -0.35) return 'rgba(244,114,182,.75)'
  return 'rgba(100,116,139,.35)'
}

function HeatmapTable({ labels = [], matrix = [] }) {
  if (!labels.length || !matrix.length) {
    return <div className="text-[11px] text-t3">No matrix data available for this run.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px] border-collapse">
        <thead>
          <tr>
            <th className="text-left text-t3 p-1">Feature</th>
            {labels.map((l) => (
              <th key={l} className="text-left text-t3 p-1 truncate" title={l}>{l.split('.').pop()}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, i) => (
            <tr key={label}>
              <td className="p-1 text-t2 truncate" title={label}>{label.split('.').pop()}</td>
              {(matrix[i] || []).map((v, j) => (
                <td key={`${label}-${j}`} className="p-1">
                  <div
                    className="rounded-sm text-center text-white"
                    style={{ background: corrTone(v), minWidth: '38px', padding: '2px 4px' }}
                    title={Number(v || 0).toFixed(4)}
                  >
                    {Number(v || 0).toFixed(2)}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const SECTION_TABS = [
  ['section1', '1. KPI & Health'],
  ['section2', '2. Correlation'],
  ['section3', '3. Outliers'],
  ['section4', '4. Validation'],
  ['section5', '5. Statistics'],
  ['section6', '6. Time Series'],
  ['section7', '7. KG Analytics'],
  ['section8', '8. AI Summary'],
]

export default function EDAVisualsViewer2({ fileIds = [], dbIds = [], onClose, onOpenGraph }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('section1')

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getEdaDashboard({ fileIds, dbIds })
      .then((res) => {
        setData(res)
      })
      .catch((e) => setError(e.message || 'Failed to load EDA visuals'))
      .finally(() => setLoading(false))
  }, [dbIds.join(','), fileIds.join(',')])

  const dbRuns = data?.db_eda?.runs || []
  const fileRuns = data?.file_eda?.runs || []
  const runs = useMemo(() => {
    const db = dbRuns.map((r) => ({ ...r }))
    const file = fileRuns.map((r) => ({ ...r }))
    const merged = [...db, ...file]
    merged.sort((a, b) => Number(b.completed_at || 0) - Number(a.completed_at || 0))
    return merged
  }, [dbRuns, fileRuns])

  const runRichness = (run) => {
    const k = run?.core_kpis || {}
    const scoreA = safeNum(k.total_records) + safeNum(k.total_columns) + safeNum(k.entities_extracted)
    const scoreB = safeNum(run?.eda_summary?.table_count) + safeNum(run?.eda_summary?.anomalous_table_count)
    const scoreC = (run?.entity_distribution || []).length + (run?.top_tables || []).length + (run?.node_centrality || []).length
    return scoreA + scoreB + scoreC
  }

  const selectedRun = useMemo(
    () => {
      if (!runs.length) return null
      const ranked = [...runs].sort((a, b) => runRichness(b) - runRichness(a))
      return ranked[0] || runs[0]
    },
    [runs]
  )

  const derived = useMemo(() => {
    const run = selectedRun || {}
    const core = run.core_kpis || {}

    const entityDist = run.entity_distribution || []
    const relationDist = run.relation_distributions || []
    const relationEvidence = run.top_relationship_evidence || []
    const topTables = run.top_tables || []

    const entitiesExtracted = entityDist.reduce((a, x) => a + safeNum(x.count), 0)
    const relationshipsExtracted = relationDist.reduce((a, x) => a + safeNum(x.count), 0) || relationEvidence.length
    const totalColumns = safeNum(core.total_columns) || topTables.reduce((a, t) => a + safeNum(t.column_count), 0) || safeNum(run?.eda_summary?.table_count)
    const totalRecords = safeNum(core.total_records) || entitiesExtracted || safeNum(run?.eda_summary?.table_count)
    const anomalyCount = safeNum(core.anomaly_count) || safeNum(run.anomaly_table_count) || safeNum(run?.eda_summary?.anomalous_table_count)
    const orphanRelationships = safeNum(core.orphan_relationships) || relationEvidence.filter((r) => String(r.joinability_signal || '').toLowerCase() === 'weak').length

    const missingPct = safeNum(core.missing_pct)
    const completePct = Math.max(0, Math.min(100, 100 - missingPct))

    const avgRisk = topTables.length
      ? topTables.reduce((a, t) => a + safeNum(t.high_risk_ratio), 0) / topTables.length
      : 0
    const healthScore = Math.max(0, Math.min(1, (safeNum(run.overall_kg_quality_score) + safeNum(run.confidence_score) + (1 - avgRisk)) / 3))

    const schemaTree = topTables.map((t) => ({ table: t.table_name, schema: 'db', columns: new Array(Math.max(0, safeNum(t.column_count))).fill(null) }))
    const datatypeDistribution = entityDist.length ? entityDist : relationDist.map((r) => ({ type: r.relation || 'relation', count: safeNum(r.count) }))

    const kpisMerged = {
      total_records: totalRecords,
      total_columns: totalColumns,
      missing_pct: safeNum(core.missing_pct),
      duplicate_rows: safeNum(core.duplicate_rows),
      anomaly_count: anomalyCount,
      file_size: safeNum(core.file_size),
      entities_extracted: safeNum(core.entities_extracted) || entitiesExtracted,
      relationships_extracted: safeNum(core.relationships_extracted) || relationshipsExtracted,
      schema_drift_count: safeNum(core.schema_drift_count),
      orphan_relationships: orphanRelationships,
      processing_time_ms: safeNum(core.processing_time_ms),
      timestamp_coverage_pct: safeNum(core.timestamp_coverage_pct),
    }

    const capsMerged = {
      supports_time_series: Boolean(run?.capabilities?.supports_time_series || (run?.time_series?.trend_points || []).length),
      supports_correlation: Boolean(run?.capabilities?.supports_correlation || (run?.correlation?.labels || []).length > 1),
      supports_kg_metrics: true,
      supports_feature_importance: Boolean(run?.capabilities?.supports_feature_importance),
    }

    const healthMerged = {
      ...(run.data_health || {}),
      schema_tree: (run.data_health?.schema_tree || schemaTree),
      datatype_distribution: (run.data_health?.datatype_distribution || datatypeDistribution),
      completeness: {
        complete_pct: safeNum(run.data_health?.completeness?.complete_pct, completePct),
        missing_pct: safeNum(run.data_health?.completeness?.missing_pct, missingPct),
        null_matrix_summary: run.data_health?.completeness?.null_matrix_summary || {
          high_null_columns: 0,
          medium_null_columns: anomalyCount,
          low_null_columns: Math.max(0, totalColumns - anomalyCount),
        },
        duplicate_distribution: run.data_health?.completeness?.duplicate_distribution || topTables.map((t) => ({ table: t.table_name, duplicate_proxy: safeNum(t.high_risk_column_count) })),
      },
      health_score: run.data_health?.health_score || { score: healthScore },
    }

    const outliersMerged = run.outliers || {
      summary: {
        affected_columns: anomalyCount,
        zscore_anomaly_count: anomalyCount,
        iqr_outlier_count: anomalyCount,
      },
      columns: topTables.map((t) => ({
        column: t.table_name,
        iqr_outliers: safeNum(t.high_risk_column_count),
        zscore_outliers: safeNum(t.high_risk_column_count),
        box: {},
        zscore_bins: [],
      })),
    }

    const checksMerged = run.consistency_checks || {
      invalid_dates: 0,
      broken_schema_entries: anomalyCount,
      type_mismatches: anomalyCount,
      enum_violations: 0,
      null_key_violations: 0,
      duplicate_entity_ids: safeNum(kpisMerged.duplicate_rows),
      orphan_relationships: orphanRelationships,
      foreign_key_issues: relationEvidence.length,
      schema_drift: safeNum(kpisMerged.schema_drift_count),
      inconsistent_category_labels: 0,
      errors: [],
    }

    const runStats = run.statistical_profiles || {}
    const statsColumns = runStats.columns || {}
    const statsHistograms = runStats.histograms || run.confidence_histograms || {}
    const statsAvailable = Boolean(
      runStats.available
      || Object.keys(statsColumns).length
      || Object.keys(statsHistograms).length
    )
    const statsMerged = {
      ...runStats,
      available: statsAvailable,
      columns: statsColumns,
      histograms: statsHistograms,
    }

    const kgMerged = run.kg_analytics || {
      graph_density: safeNum(run.graph_density),
      connected_components: 0,
      entity_distribution: entityDist,
      relationship_distribution: relationDist,
      degree_centrality: run.node_centrality || [],
    }

    const insightsMerged = (run.executive_summary && run.executive_summary.length)
      ? run.executive_summary
      : [
          {
            message: `Dataset run quality ${scorePct(run.overall_kg_quality_score)} with confidence ${scorePct(run.confidence_score)}.`,
            severity: safeNum(run.overall_kg_quality_score) < 0.5 ? 'high' : 'medium',
            business_impact: 'Data readiness may impact retrieval and graph trust.',
            recommendation: 'Review anomaly-heavy tables/entities and rerun ingestion if needed.',
            confidence: 0.78,
          },
        ]

    return {
      caps: capsMerged,
      kpis: kpisMerged,
      health: healthMerged,
      corr: run.correlation || {},
      outliers: outliersMerged,
      checks: checksMerged,
      stats: statsMerged,
      series: run.time_series || { available: false, trend_points: [], moving_average: [], rolling_volatility: [], event_spikes: [] },
      kg: kgMerged,
      insights: insightsMerged,
    }
  }, [selectedRun])

  const caps = derived.caps
  const kpis = derived.kpis
  const health = derived.health
  const corr = derived.corr
  const outliers = derived.outliers
  const checks = derived.checks
  const stats = derived.stats
  const series = derived.series
  const kg = derived.kg
  const insights = derived.insights

  const contractChartsBySection = useMemo(() => {
    const dashboardCharts = data?.charts_contract?.sections || []
    const runCharts = selectedRun?.charts_contract?.charts || []
    const charts = dashboardCharts.length
      ? dashboardCharts.flatMap((section) => section?.charts || [])
      : runCharts
    const fallbackCharts = [
      {
        chart_id: 'fallback.kpi.health.gauge',
        section: 'kpi_health',
        chart_type: 'gauge',
        library_hint: 'recharts',
        title: 'Health Score',
        description: 'Composite health index from quality and consistency signals.',
        data: { value: safeNum(health?.health_score?.score, safeNum(selectedRun?.overall_kg_quality_score, 0)) },
        options: { min: 0, max: 1 },
        meta: { source: selectedRun?.file_id ? 'file' : 'db', empty_reason: null },
      },
      {
        chart_id: 'fallback.kpi.completeness.donut',
        section: 'kpi_health',
        chart_type: 'donut',
        library_hint: 'recharts',
        title: 'Completeness',
        description: 'Share of complete vs missing values.',
        data: {
          series: [
            { name: 'complete', value: Math.max(0, 100 - safeNum(kpis?.missing_pct, 0)) },
            { name: 'missing', value: safeNum(kpis?.missing_pct, 0) },
          ],
        },
        options: { legend: true },
        meta: { source: selectedRun?.file_id ? 'file' : 'db', empty_reason: null },
      },
      {
        chart_id: 'fallback.correlation.pearson',
        section: 'correlation',
        chart_type: 'heatmap',
        library_hint: 'echarts',
        title: 'Pearson Correlation',
        description: 'Linear correlation across numeric features.',
        data: {
          x: corr?.labels || [],
          y: corr?.labels || [],
          values: corr?.pearson || [],
        },
        options: { legend: true },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: (corr?.labels || []).length > 1 ? null : 'Insufficient numeric dimensions',
        },
      },
      {
        chart_id: 'fallback.correlation.spearman',
        section: 'correlation',
        chart_type: 'heatmap',
        library_hint: 'echarts',
        title: 'Spearman Correlation',
        description: 'Rank correlation across numeric features.',
        data: {
          x: corr?.labels || [],
          y: corr?.labels || [],
          values: corr?.spearman || [],
        },
        options: { legend: true },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: (corr?.labels || []).length > 1 ? null : 'Insufficient numeric dimensions',
        },
      },
      {
        chart_id: 'fallback.timeseries.trend',
        section: 'time_series',
        chart_type: 'line',
        library_hint: 'recharts',
        title: 'Trend Over Time',
        description: 'Record/activity trend by timestamp buckets.',
        data: { series: series?.trend_points || [] },
        options: { xKey: 'date', yKey: 'count' },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: (series?.trend_points || []).length ? null : 'No timestamp trend points available',
        },
      },
    ]

    const sourceCharts = charts.length ? charts : fallbackCharts
    const map = {
      kpi_health: [],
      correlation: [],
      time_series: [],
    }
    for (const c of sourceCharts) {
      const sec = String(c.section || '')
      if (map[sec]) map[sec].push(c)
    }
    return map
  }, [selectedRun, health, kpis, corr, series])

  const schemaTimeline = useMemo(() => {
    if (!selectedRun) return []
    const dt = Number(selectedRun.completed_at || 0)
    return [{
      at: dt ? new Date(dt * 1000).toISOString().slice(0, 19).replace('T', ' ') : 'n/a',
      schema_drift: Number(kpis.schema_drift_count || checks.schema_drift || 0),
    }]
  }, [selectedRun, kpis.schema_drift_count, checks.schema_drift])

  const changePoints = useMemo(() => {
    const values = (series.trend_points || []).map((p) => Number(p.count || 0))
    const points = []
    for (let i = 1; i < values.length; i += 1) {
      const delta = Math.abs(values[i] - values[i - 1])
      if (delta >= 3) points.push({ index: i, delta })
    }
    return points
  }, [series.trend_points])

  const section3Outliers = useMemo(() => {
    const currentCols = outliers?.columns || []
    if (currentCols.length > 0) {
      return outliers
    }

    const bestRun = runs.find((r) => {
      const nativeCols = (r?.outliers?.columns || []).length
      const fallbackCols = (r?.top_tables || []).length
      return nativeCols > 0 || fallbackCols > 0
    })

    if (!bestRun) {
      return outliers
    }

    const nativeOutliers = bestRun.outliers || {}
    if ((nativeOutliers.columns || []).length > 0) {
      return nativeOutliers
    }

    const topTables = bestRun.top_tables || []
    const anomalyCount = safeNum(bestRun.anomaly_table_count) || safeNum(bestRun?.eda_summary?.anomalous_table_count)
    return {
      summary: {
        affected_columns: anomalyCount || topTables.length,
        zscore_anomaly_count: anomalyCount || topTables.length,
        iqr_outlier_count: anomalyCount || topTables.length,
      },
      columns: topTables.map((t) => ({
        column: t.table_name,
        iqr_outliers: safeNum(t.high_risk_column_count),
        zscore_outliers: safeNum(t.high_risk_column_count),
        box: {},
        zscore_bins: [],
      })),
    }
  }, [runs, outliers])

  const section5Charts = useMemo(() => {
    const columns = Object.entries(stats.columns || {}).slice(0, 6)
    const out = []

    for (const [name, s] of columns) {
      const histogramSeries = (s.histogram || []).map((h, idx) => ({
        bin: `${Number(h.min ?? 0).toFixed(1)}-${Number(h.max ?? 0).toFixed(1)}`,
        count: Number(h.count || 0),
        idx,
      }))

      out.push({
        chart_id: `stats.hist.${name}`,
        chart_type: 'bar',
        library_hint: 'recharts',
        title: `${name} · Distribution`,
        description: 'Histogram of observed values for this numeric field.',
        data: { series: histogramSeries },
        options: { xKey: 'bin', yKey: 'count', color: '#2563eb' },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: histogramSeries.length ? null : 'No histogram bins available',
        },
      })

      const spreadSeries = [
        { metric: 'Min', value: Number(s.min ?? s.box?.lower_whisker ?? 0) },
        { metric: 'Q1', value: Number(s.q1 ?? s.box?.q1 ?? 0) },
        { metric: 'Median', value: Number(s.median ?? s.box?.median ?? 0) },
        { metric: 'Q3', value: Number(s.q3 ?? s.box?.q3 ?? 0) },
        { metric: 'Max', value: Number(s.max ?? s.box?.upper_whisker ?? 0) },
      ]

      out.push({
        chart_id: `stats.spread.${name}`,
        chart_type: 'bar',
        library_hint: 'recharts',
        title: `${name} · Spread`,
        description: 'Min/Q1/Median/Q3/Max profile to visualize dispersion.',
        data: { series: spreadSeries },
        options: { xKey: 'metric', yKey: 'value', color: '#d97706' },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: spreadSeries.length ? null : 'No spread statistics available',
        },
      })

      const qqPoints = (s.qq_points || []).map((q) => ({
        x: Number(q.expected || 0),
        y: Number(q.actual || 0),
        label: name,
        size: 7,
        color: '#0ea5e9',
      }))
      if (qqPoints.length) {
        const allVals = qqPoints.flatMap((p) => [p.x, p.y])
        const minV = Math.min(...allVals)
        const maxV = Math.max(...allVals)
        out.push({
          chart_id: `stats.qq.${name}`,
          chart_type: 'scatter',
          library_hint: 'plotly',
          title: `${name} · QQ Plot`,
          description: 'Normal QQ scatter to assess distributional normality.',
          data: {
            points: qqPoints,
            referenceLine: {
              name: 'y = x',
              x: [minV, maxV],
              y: [minV, maxV],
            },
          },
          options: {
            xTitle: 'Expected Quantiles',
            yTitle: 'Observed Values',
          },
          meta: {
            source: selectedRun?.file_id ? 'file' : 'db',
            empty_reason: null,
          },
        })
      }
    }

    const skewKurtPoints = Object.entries(stats.columns || {})
      .filter(([, s]) => s && (s.skewness != null || s.kurtosis != null))
      .map(([name, s]) => ({
        x: Number(s.skewness || 0),
        y: Number(s.kurtosis || 0),
        label: name,
        size: Math.max(6, Math.min(14, Number(s.std_dev || 0) * 1.8)),
        color: '#16a34a',
      }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
      .slice(0, 50)

    if (skewKurtPoints.length) {
      out.push({
        chart_id: 'stats.skew-kurtosis.map',
        chart_type: 'scatter',
        library_hint: 'plotly',
        title: 'Skewness vs Kurtosis Map',
        description: 'Column shape map (point size tracks standard deviation).',
        data: { points: skewKurtPoints },
        options: {
          xTitle: 'Skewness',
          yTitle: 'Kurtosis (Excess)',
        },
        meta: {
          source: selectedRun?.file_id ? 'file' : 'db',
          empty_reason: null,
        },
      })
    }

    if (out.length) return out

    const confidence = stats.histograms || {}
    const confidenceCharts = []
    const buildConfidenceSeries = (bins = []) => bins.map((b, idx) => ({
      bin: `${Number(b.bin_start ?? 0).toFixed(1)}-${Number(b.bin_end ?? 0).toFixed(1)}`,
      count: Number(b.count || 0),
      idx,
    }))

    const entitySeries = buildConfidenceSeries(confidence.entities || [])
    const relSeries = buildConfidenceSeries(confidence.relationships || [])

    confidenceCharts.push({
      chart_id: 'stats.conf.entities',
      chart_type: 'bar',
      library_hint: 'recharts',
      title: 'Entity Confidence Distribution',
      description: 'Confidence spread for extracted entities (file-oriented fallback).',
      data: { series: entitySeries },
      options: { xKey: 'bin', yKey: 'count', color: '#16a34a' },
      meta: {
        source: selectedRun?.file_id ? 'file' : 'db',
        empty_reason: entitySeries.length ? null : 'No entity confidence histogram available',
      },
    })

    confidenceCharts.push({
      chart_id: 'stats.conf.relationships',
      chart_type: 'bar',
      library_hint: 'recharts',
      title: 'Relationship Confidence Distribution',
      description: 'Confidence spread for extracted relationships (file-oriented fallback).',
      data: { series: relSeries },
      options: { xKey: 'bin', yKey: 'count', color: '#0ea5e9' },
      meta: {
        source: selectedRun?.file_id ? 'file' : 'db',
        empty_reason: relSeries.length ? null : 'No relationship confidence histogram available',
      },
    })

    return confidenceCharts
  }, [selectedRun, stats.columns, stats.histograms])

  const hasRuns = dbRuns.length > 0 || fileRuns.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(10,12,22,.72)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-card2 border border-dborder rounded-card flex flex-col" style={{ width: '1080px', maxWidth: '96vw', maxHeight: '90vh' }}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-dborder flex-shrink-0">
          <div>
            <div className="font-sora text-[15px] font-semibold text-t1">EDA Visuals2 Enterprise Dashboard</div>
            <div className="text-[11px] text-t3 mt-0.5">Section-wise EDA analytics generated from ingested data and KG artifacts.</div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn btn-sm" onClick={() => onOpenGraph && onOpenGraph()}>Open GraphRAG</button>
            <button className="btn btn-sm" onClick={onClose}>✕ Close</button>
          </div>
        </div>

        <div className="flex border-b border-dborder flex-shrink-0 overflow-x-auto">
          {SECTION_TABS.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="px-4 py-2.5 text-[11px] font-medium border-b-2 whitespace-nowrap"
              style={{
                borderBottomColor: tab === key ? 'var(--color-amber, #d97706)' : 'transparent',
                color: tab === key ? '#d97706' : 'var(--color-t2, #5a6077)',
                background: 'transparent',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="px-6 py-3 border-b border-dborder flex items-center gap-2 flex-shrink-0">
          <div className="text-[11px] text-t3">
            Showing visuals for current ingested scope ({fileIds.length} file IDs, {dbIds.length} DB IDs). Latest run is selected automatically.
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && <div className="text-[12px] text-t3 text-center py-8">Loading EDA Visuals2...</div>}
          {error && <div className="text-[12px] text-coral text-center py-8">Error: {error}</div>}
          {!loading && !error && !hasRuns && <div className="text-[12px] text-t2 text-center py-10">No EDA artifacts found yet.</div>}

          {!loading && !error && hasRuns && selectedRun && tab === 'section1' && (
            <div className="space-y-4">
              {contractChartsBySection.kpi_health.length > 0 && (
                <div className="grid grid-cols-2 gap-3">
                  {contractChartsBySection.kpi_health.map((chart) => (
                    <div key={chart.chart_id} className="card">
                      <div className="text-[12px] font-semibold text-t1 mb-2">{chart.title}</div>
                      {chart.description && <div className="text-[10px] text-t3 mb-2">{chart.description}</div>}
                      <ChartRenderer chart={chart} />
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-4 gap-3">
                <div className="mcard"><div className="text-[10px] text-t3">Total records</div><div className="text-[20px] font-sora text-t1">{num(kpis.total_records)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Total columns</div><div className="text-[20px] font-sora text-t1">{num(kpis.total_columns)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Missing %</div><div className="text-[20px] font-sora text-t1">{Number(kpis.missing_pct || 0).toFixed(2)}%</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Duplicate rows</div><div className="text-[20px] font-sora text-t1">{num(kpis.duplicate_rows)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Anomaly count</div><div className="text-[20px] font-sora text-t1">{num(kpis.anomaly_count)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">File size</div><div className="text-[20px] font-sora text-t1">{fmtBytes(kpis.file_size)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Entities</div><div className="text-[20px] font-sora text-t1">{num(kpis.entities_extracted)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Relationships</div><div className="text-[20px] font-sora text-t1">{num(kpis.relationships_extracted)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Schema drift</div><div className="text-[20px] font-sora text-t1">{num(kpis.schema_drift_count)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Orphan relationships</div><div className="text-[20px] font-sora text-t1">{num(kpis.orphan_relationships)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Processing time</div><div className="text-[20px] font-sora text-t1">{fmtMs(kpis.processing_time_ms)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Timestamp coverage</div><div className="text-[20px] font-sora text-t1">{Number(kpis.timestamp_coverage_pct || 0).toFixed(2)}%</div></div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-2">Dataset schema tree</div>
                  {(health.schema_tree || []).slice(0, 10).map((t) => (
                    <div key={`${t.schema || 'schema'}.${t.table || 'table'}`} className="mb-2 bg-bg4 border border-dborder rounded-sm px-3 py-2">
                      <div className="text-[11px] text-t1 font-semibold">{t.table || 'table'} <span className="text-t3">({t.schema || 'n/a'})</span></div>
                      <div className="text-[10px] text-t3 mt-1">Columns: {(t.columns || []).length}</div>
                    </div>
                  ))}
                  {!health.schema_tree?.length && <div className="text-[11px] text-t3">Schema tree unavailable for this source.</div>}
                </div>

                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-2">Datatype distribution</div>
                  {(health.datatype_distribution || []).slice(0, 10).map((d) => (
                    <div key={d.type} className="mb-2">
                      <div className="flex justify-between text-[11px] text-t2"><span>{d.type}</span><span>{num(d.count)}</span></div>
                      <div className="prog-bar"><div className="prog-fill" style={{ width: `${Math.min(100, Number(d.count || 0) * 8)}%`, background: '#2563eb' }} /></div>
                    </div>
                  ))}
                  {!health.datatype_distribution?.length && <div className="text-[11px] text-t3">Datatype distribution unavailable.</div>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-2">Completeness and null matrix</div>
                  <div className="text-[11px] text-t2 mb-1">Complete: {Number(health.completeness?.complete_pct || 0).toFixed(2)}%</div>
                  <div className="text-[11px] text-t2 mb-1">Missing: {Number(health.completeness?.missing_pct || 0).toFixed(2)}%</div>
                  <div className="text-[11px] text-t3">Null matrix: high {num(health.completeness?.null_matrix_summary?.high_null_columns)} · medium {num(health.completeness?.null_matrix_summary?.medium_null_columns)} · low {num(health.completeness?.null_matrix_summary?.low_null_columns)}</div>
                </div>
                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-2">Health score gauge and duplicate distribution</div>
                  <div className="text-[22px] font-sora text-t1 mb-2">{scorePct(health.health_score?.score || 0)}</div>
                  {(health.completeness?.duplicate_distribution || []).slice(0, 6).map((d, idx) => (
                    <div key={`${d.table || 'table'}-${idx}`} className="text-[10px] text-t3">{d.table}: {num(d.duplicate_proxy)}</div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section2' && (
            <div className="space-y-4">
              {contractChartsBySection.correlation.length > 0 && (
                <div className="space-y-3">
                  {contractChartsBySection.correlation.map((chart) => (
                    <div key={chart.chart_id} className="card">
                      <div className="text-[12px] font-semibold text-t1 mb-2">{chart.title}</div>
                      {chart.description && <div className="text-[10px] text-t3 mb-2">{chart.description}</div>}
                      <ChartRenderer chart={chart} />
                    </div>
                  ))}
                </div>
              )}

              {contractChartsBySection.correlation.length === 0 && !caps.supports_correlation && <div className="card text-[11px] text-t3">Correlation analytics are not available for this selected run.</div>}
              {contractChartsBySection.correlation.length === 0 && caps.supports_correlation && (
                <>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Pearson correlation heatmap</div>
                    <HeatmapTable labels={corr.labels || []} matrix={corr.pearson || []} />
                  </div>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Spearman correlation heatmap</div>
                    <HeatmapTable labels={corr.labels || []} matrix={corr.spearman || []} />
                  </div>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Covariance matrix</div>
                    <HeatmapTable labels={corr.labels || []} matrix={corr.covariance || []} />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="mcard">
                      <div className="text-[10px] text-t3">Strongest positive</div>
                      <div className="text-[11px] text-t1 mt-1">{corr?.strongest_positive?.pair?.join(' ↔ ') || 'n/a'}</div>
                      <div className="text-[10px] text-t3">{Number(corr?.strongest_positive?.value || 0).toFixed(3)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3">Strongest negative</div>
                      <div className="text-[11px] text-t1 mt-1">{corr?.strongest_negative?.pair?.join(' ↔ ') || 'n/a'}</div>
                      <div className="text-[10px] text-t3">{Number(corr?.strongest_negative?.value || 0).toFixed(3)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3">VIF analysis</div>
                      <div className="text-[11px] text-t1 mt-1">{corr?.vif?.available ? `${(corr?.vif?.values || []).length} features` : 'Not applicable'}</div>
                    </div>
                  </div>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Correlation pair explorer</div>
                    {(corr.pair_explorer || []).slice(0, 20).map((p, idx) => (
                      <div key={`${p.left}-${p.right}-${idx}`} className="text-[11px] text-t2 mb-1">
                        {p.left} ↔ {p.right} | Pearson {Number(p.pearson || 0).toFixed(3)} | Spearman {Number(p.spearman || 0).toFixed(3)}
                      </div>
                    ))}
                  </div>
                </>
              )}
              <div className="card text-[11px] text-t3">Feature importance framework (Random Forest/XGBoost/Mutual Information) is queued for Phase 2 and exposed via capability flags.</div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section3' && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="mcard"><div className="text-[10px] text-t3">Affected columns</div><div className="text-[20px] font-sora text-t1">{num(section3Outliers?.summary?.affected_columns)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Z-score anomalies</div><div className="text-[20px] font-sora text-t1">{num(section3Outliers?.summary?.zscore_anomaly_count)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">IQR outliers</div><div className="text-[20px] font-sora text-t1">{num(section3Outliers?.summary?.iqr_outlier_count)}</div></div>
              </div>
              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">Box plots and z-score distributions</div>
                {(section3Outliers.columns || []).slice(0, 15).map((c) => (
                  <div key={c.column} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                    <div className="text-[11px] text-t1 truncate">{c.column}</div>
                    <div className="text-[10px] text-t3 mt-1">Box: min {Number(c.box?.lower_whisker || 0).toFixed(2)} · q1 {Number(c.box?.q1 || 0).toFixed(2)} · med {Number(c.box?.median || 0).toFixed(2)} · q3 {Number(c.box?.q3 || 0).toFixed(2)} · max {Number(c.box?.upper_whisker || 0).toFixed(2)}</div>
                    <div className="text-[10px] text-t3">Z bins: {(c.zscore_bins || []).map((z) => `${z.band}:${z.count}`).join(' | ')}</div>
                  </div>
                ))}
                {!section3Outliers.columns?.length && <div className="text-[11px] text-t3">No outlier visuals available for this run.</div>}
              </div>
              <div className="card text-[11px] text-t3">Multivariate projections (PCA/t-SNE) are enabled as adaptive Phase 2 enhancements based on dataset suitability.</div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section4' && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="mcard"><div className="text-[10px] text-t3">Invalid dates</div><div className="text-[20px] font-sora text-t1">{num(checks.invalid_dates)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Type mismatches</div><div className="text-[20px] font-sora text-t1">{num(checks.type_mismatches)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Enum violations</div><div className="text-[20px] font-sora text-t1">{num(checks.enum_violations)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Null key violations</div><div className="text-[20px] font-sora text-t1">{num(checks.null_key_violations)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Duplicate entity IDs</div><div className="text-[20px] font-sora text-t1">{num(checks.duplicate_entity_ids)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Orphan relationships</div><div className="text-[20px] font-sora text-t1">{num(checks.orphan_relationships)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Foreign key issues</div><div className="text-[20px] font-sora text-t1">{num(checks.foreign_key_issues)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Schema drift</div><div className="text-[20px] font-sora text-t1">{num(checks.schema_drift)}</div></div>
                <div className="mcard"><div className="text-[10px] text-t3">Inconsistent labels</div><div className="text-[20px] font-sora text-t1">{num(checks.inconsistent_category_labels)}</div></div>
              </div>

              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">Validation error table</div>
                {(checks.errors || []).slice(0, 20).map((e, idx) => (
                  <div key={`${e.table || 't'}-${e.column || 'c'}-${idx}`} className="text-[11px] text-t2 mb-1">
                    {e.table}.{e.column} · {e.check} · count {num(e.count)} · severity {e.severity}
                  </div>
                ))}
                {!checks.errors?.length && <div className="text-[11px] text-t3">No validation errors captured for this run.</div>}
              </div>

              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">Schema drift timeline</div>
                {schemaTimeline.map((p, idx) => (
                  <div key={`${p.at}-${idx}`} className="text-[11px] text-t2">{p.at} · drift count {num(p.schema_drift)}</div>
                ))}
              </div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section5' && (
            <div className="space-y-4">
              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">Statistical distributions and spread</div>
                {!stats.available && <div className="text-[11px] text-t3">Statistical analysis unavailable for this run.</div>}
                {stats.available && section5Charts.length > 0 && (
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    {section5Charts.map((chart) => (
                      <div key={chart.chart_id} className="bg-bg4 border border-dborder rounded-sm px-3 py-2">
                        <div className="text-[11px] text-t1 font-semibold mb-1">{chart.title}</div>
                        {chart.description && <div className="text-[10px] text-t3 mb-2">{chart.description}</div>}
                        <ChartRenderer chart={chart} />
                      </div>
                    ))}
                  </div>
                )}
                {stats.available && Object.entries(stats.columns || {}).slice(0, 14).map(([name, s]) => (
                  <div key={name} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                    <div className="text-[11px] text-t1 truncate">{name}</div>
                    <div className="text-[10px] text-t3 mt-1">mean {Number(s.mean || 0).toFixed(3)} · median {Number(s.median || 0).toFixed(3)} · var {Number(s.variance || 0).toFixed(3)} · std {Number(s.std_dev || 0).toFixed(3)}</div>
                    <div className="text-[10px] text-t3">skewness {Number(s.skewness || 0).toFixed(3)} · kurtosis {Number(s.kurtosis || 0).toFixed(3)} · p10 {Number(s.p10 || 0).toFixed(3)} · p90 {Number(s.p90 || 0).toFixed(3)}</div>
                    <div className="text-[10px] text-t3">Histogram bins: {(s.histogram || []).map((h) => `[${Number(h.min || 0).toFixed(1)}..${Number(h.max || 0).toFixed(1)}:${h.count}]`).join(' ')}</div>
                    <div className="text-[10px] text-t3">QQ points: {(s.qq_points || []).slice(0, 6).map((q) => `(${Number(q.expected || 0).toFixed(2)}, ${Number(q.actual || 0).toFixed(2)})`).join(' ')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section6' && (
            <div className="space-y-4">
              {contractChartsBySection.time_series.length > 0 && (
                <div className="space-y-3">
                  {contractChartsBySection.time_series.map((chart) => (
                    <div key={chart.chart_id} className="card">
                      <div className="text-[12px] font-semibold text-t1 mb-2">{chart.title}</div>
                      {chart.description && <div className="text-[10px] text-t3 mb-2">{chart.description}</div>}
                      <ChartRenderer chart={chart} />
                    </div>
                  ))}
                </div>
              )}

              {!caps.supports_time_series && <div className="card text-[11px] text-t3">Timestamp coverage is insufficient for time-series analytics on this run.</div>}
              {caps.supports_time_series && (
                <>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Trend, moving average and rolling volatility</div>
                    <div className="text-[11px] text-t3 mb-1">Trend points: {num((series.trend_points || []).length)}</div>
                    <div className="text-[11px] text-t3 mb-1">Moving average points: {num((series.moving_average || []).length)}</div>
                    <div className="text-[11px] text-t3">Rolling volatility points: {num((series.rolling_volatility || []).length)}</div>
                  </div>
                  <div className="card">
                    <div className="text-[12px] font-semibold text-t1 mb-2">Event spikes and change points</div>
                    <div className="text-[11px] text-t3 mb-2">Event spikes: {num((series.event_spikes || []).length)}</div>
                    {(series.event_spikes || []).slice(0, 12).map((s, idx) => (
                      <div key={`${s.date || 'spike'}-${idx}`} className="text-[11px] text-t2 mb-1">{s.date} · count {num(s.count)} · z-proxy {Number(s.z_proxy || 0).toFixed(2)}</div>
                    ))}
                    <div className="text-[11px] text-t3 mt-2">Change points detected: {num(changePoints.length)}</div>
                  </div>
                </>
              )}
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section7' && (
            <div className="space-y-4">
              <div className="card">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[12px] font-semibold text-t1">Knowledge graph analytics</div>
                  <button className="btn btn-sm" onClick={() => onOpenGraph && onOpenGraph()}>Open full graph</button>
                </div>
                <div className="grid grid-cols-3 gap-3 mb-3">
                  <div className="mcard"><div className="text-[10px] text-t3">Graph density</div><div className="text-[20px] font-sora text-t1">{pct(kg.graph_density || selectedRun.graph_density || 0)}</div></div>
                  <div className="mcard"><div className="text-[10px] text-t3">Connected components</div><div className="text-[20px] font-sora text-t1">{num(kg.connected_components)}</div></div>
                  <div className="mcard"><div className="text-[10px] text-t3">Entity classes</div><div className="text-[20px] font-sora text-t1">{num((kg.entity_distribution || selectedRun.entity_distribution || []).length)}</div></div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[11px] text-t3 mb-1 uppercase tracking-wider font-semibold">Entity frequency distribution</div>
                    {(kg.entity_distribution || selectedRun.entity_distribution || []).slice(0, 10).map((e) => (
                      <div key={e.type} className="mb-1 text-[11px] text-t2">{e.type}: {num(e.count)}</div>
                    ))}
                  </div>
                  <div>
                    <div className="text-[11px] text-t3 mb-1 uppercase tracking-wider font-semibold">Relationship type distribution</div>
                    {(kg.relationship_distribution || selectedRun.relation_distributions || []).slice(0, 10).map((r, idx) => (
                      <div key={`${r.relation || r.joinability || 'rel'}-${idx}`} className="mb-1 text-[11px] text-t2">{r.relation || r.joinability}: {num(r.count)}</div>
                    ))}
                  </div>
                </div>

                <div className="text-[11px] text-t3 mt-3">Centrality preview (degree/betweenness/PageRank proxy): {(kg.degree_centrality || selectedRun.node_centrality || []).slice(0, 5).map((n) => n.label || n.id).join(', ') || 'n/a'}</div>
              </div>
              <div className="card text-[11px] text-t3">Community detection and suspicious subgraph intelligence are planned in Phase 2 with capability-driven rollout.</div>
            </div>
          )}

          {!loading && !error && hasRuns && selectedRun && tab === 'section8' && (
            <div className="space-y-4">
              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">Deterministic executive insights</div>
                {insights.map((i, idx) => (
                  <div key={`insight-${idx}`} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                    <div className="text-[11px] text-t1">{i.message}</div>
                    <div className="text-[10px] text-t3 mt-1">Severity: {i.severity || 'n/a'} · Confidence: {Number(i.confidence || 0).toFixed(2)}</div>
                    <div className="text-[10px] text-t3">Impact: {i.business_impact || 'n/a'}</div>
                    <div className="text-[10px] text-t3">Recommendation: {i.recommendation || 'n/a'}</div>
                  </div>
                ))}
                {!insights.length && <div className="text-[11px] text-t3">No deterministic insights were generated for this run.</div>}
              </div>

              <div className="card">
                <div className="text-[12px] font-semibold text-t1 mb-2">LLM business summary</div>
                <div className="text-[11px] text-t3">
                  {selectedRun?.llm_summary
                    ? selectedRun.llm_summary
                    : 'LLM summary is optional and not enabled for this run. Deterministic insights are active.'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
