import { useEffect, useMemo, useState } from 'react'
import ChartRenderer from './charts/ChartRenderer'

function safeNum(v, d = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : d
}

function num(v, digits = 2) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function pct(v, digits = 1) {
  return `${(safeNum(v) * 100).toFixed(digits)}%`
}

function severityFor(value, high, medium) {
  if (value >= high) return 'high'
  if (value >= medium) return 'medium'
  return 'low'
}

function severityStyle(level) {
  if (level === 'high') {
    return { color: '#dc2626', background: 'rgba(220,38,38,.12)', border: '1px solid rgba(220,38,38,.25)' }
  }
  if (level === 'medium') {
    return { color: '#d97706', background: 'rgba(217,119,6,.12)', border: '1px solid rgba(217,119,6,.25)' }
  }
  return { color: '#16a34a', background: 'rgba(22,163,74,.12)', border: '1px solid rgba(22,163,74,.25)' }
}

function Sparkline({ values = [] }) {
  const pts = values.length ? values : [0.3, 0.4, 0.45, 0.5, 0.52, 0.48, 0.55]
  const max = Math.max(...pts, 1)
  const min = Math.min(...pts, 0)
  const span = Math.max(0.0001, max - min)
  const w = 120
  const h = 30
  const points = pts.map((v, i) => {
    const x = (i / Math.max(1, pts.length - 1)) * w
    const y = h - ((v - min) / span) * h
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width="100%" height="34" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="mt-1">
      <polyline fill="none" stroke="#2563eb" strokeWidth="2" points={points} />
    </svg>
  )
}

function buildInsights(feature, stat, corrDelta, outlierCount) {
  const insights = []
  const skew = safeNum(stat?.skewness)
  const kurt = safeNum(stat?.kurtosis)
  const cv = safeNum(stat?.std_dev) / Math.max(Math.abs(safeNum(stat?.mean)), 0.0001)
  const q1 = safeNum(stat?.q1)
  const q3 = safeNum(stat?.q3)
  const p10 = safeNum(stat?.p10)
  const p90 = safeNum(stat?.p90)

  if (Math.abs(skew) >= 1) {
    const side = skew > 0 ? 'right' : 'left'
    insights.push({
      title: 'Skewness Risk',
      severity: 'high',
      confidence: 0.89,
      message: `${feature} shows strong ${side} skew.`,
      business: 'Forecasting and threshold decisions can be biased by long asymmetric tails.',
      ml: 'Tree splits may over-focus on sparse tail regions; linear models may underperform without transformation.',
      action: 'Apply log/yeo-johnson transformation and compare model stability before promotion.',
    })
  }

  if (kurt >= 1.5 || outlierCount > 0) {
    insights.push({
      title: 'Heavy-Tail / Outlier Concentration',
      severity: 'medium',
      confidence: 0.82,
      message: `${feature} indicates heavy-tail behavior with elevated extreme values.`,
      business: 'Tail events can dominate financial risk and operational alert volumes.',
      ml: 'Regression loss can be unstable due to high-leverage points.',
      action: 'Consider robust scaling, winsorization policy, and tail monitoring controls.',
    })
  }

  if (cv < 0.08) {
    insights.push({
      title: 'Low Variability Signal',
      severity: 'low',
      confidence: 0.8,
      message: `${feature} has very low relative variance.`,
      business: 'Feature contributes limited segment discrimination.',
      ml: 'Potentially low predictive power and weak gain contribution.',
      action: 'Evaluate feature utility; drop or combine with interaction terms if low importance persists.',
    })
  }

  if ((p90 - p10) > Math.max(0.0001, (q3 - q1)) * 1.8) {
    insights.push({
      title: 'Tail Spread Alert',
      severity: 'medium',
      confidence: 0.77,
      message: `${feature} has broad tail spread versus core IQR.`,
      business: 'May represent niche high-risk cohorts or rare operational states.',
      ml: 'Model boundaries could drift under distribution shift.',
      action: 'Add percentile-based feature bins and monitor top-decile drift.',
    })
  }

  if (corrDelta > 0.18) {
    insights.push({
      title: 'Nonlinear Dependency Signal',
      severity: 'medium',
      confidence: 0.74,
      message: 'Weak linear but stronger rank dependency observed in selected pair.',
      business: 'Relationship may represent behavioral thresholds rather than linear effects.',
      ml: 'Consider interaction features or nonlinear models.',
      action: 'Benchmark GAM/GBM variants and inspect partial dependence.',
    })
  }

  if (!insights.length) {
    insights.push({
      title: 'Model-Ready Distribution',
      severity: 'low',
      confidence: 0.76,
      message: `${feature} appears stable with no dominant distribution risk signals.`,
      business: 'Lower operational uncertainty for KPI and forecast reporting.',
      ml: 'Suitable baseline feature candidate for production training.',
      action: 'Retain with periodic drift checks and monitor importance over releases.',
    })
  }

  return insights
}

export default function DistributionLabPanel({
  runs = [],
  selectedRun,
  stats = {},
  corr = {},
  outliers = {},
  kpis = {},
  checks = {},
  kg = {},
  insights = [],
  caps = {},
}) {
  const [search, setSearch] = useState('')
  const [feature, setFeature] = useState('')
  const [compareFeature, setCompareFeature] = useState('')
  const [range, setRange] = useState('all')
  const [segment, setSegment] = useState('all')
  const [view, setView] = useState('hist')
  // New: tab state for intelligence type
  const [intelligenceTab, setIntelligenceTab] = useState('univariate') // 'univariate' | 'bivariate' | 'multivariate'

  const columns = stats?.columns || {}
  const featureNames = useMemo(() => Object.keys(columns), [columns])

  useEffect(() => {
    if (!feature && featureNames.length) {
      setFeature(featureNames[0])
    }
  }, [feature, featureNames])

  useEffect(() => {
    if (!compareFeature && featureNames.length > 1) {
      setCompareFeature(featureNames[1])
    }
  }, [compareFeature, featureNames])

  const filteredFeatures = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return featureNames
    return featureNames.filter((name) => name.toLowerCase().includes(q))
  }, [featureNames, search])

  const stat = columns[feature] || {}
  const outlierRow = (outliers?.columns || []).find((r) => r.column === feature) || {}
  const outlierCount = safeNum(outlierRow.iqr_outliers) + safeNum(outlierRow.zscore_outliers)

  const corrLabels = corr?.labels || []
  const pearson = corr?.pearson || []
  const spearman = corr?.spearman || []

  // Derived variables for rendering
  const runLabel = selectedRun?.db_id || selectedRun?.file_id || 'current-run';
  // These should be defined or replaced with actual logic/data
  const executiveKpis = kpis?.executive || [];
  const featureRows = stats?.featureRows || [];
  const univariateChart = stats?.univariateChart || {};
  const aiInsights = buildInsights(feature, stat, 0, outlierCount); // Example usage
  const bivariateHeatmap = corr?.bivariateHeatmap || {};
  const bivariateScatter = corr?.bivariateScatter || {};
  const covHeatmap = corr?.covHeatmap || {};
  const outlierDensity = stats?.outlierDensity || 0;
  const maxCorr = corr?.maxCorr || 0;
  const featureCount = featureNames.length;
  const readiness = stats?.readiness || 0;
  const skewedCount = stats?.skewedCount || 0;
  const heavyTailCount = stats?.heavyTailCount || 0;
  const multiRisk = stats?.multiRisk || 0;
  const recommendationCards = stats?.recommendations || [];

  // Pair metrics for bivariate tab
  const pairMetrics = useMemo(() => {
    const i = corrLabels.indexOf(feature);
    const j = corrLabels.indexOf(compareFeature);
    if (i < 0 || j < 0) {
      return { pearson: 0, spearman: 0, kendallProxy: 0, corrDelta: 0 };
    }
    return {
      pearson: safeNum((pearson[i] || [])[j]),
      spearman: safeNum((spearman[i] || [])[j]),
      kendallProxy: 0, // Add kendall if available
      corrDelta: Math.abs(safeNum((pearson[i] || [])[j]) - safeNum((spearman[i] || [])[j])),
    };
  }, [feature, compareFeature, corrLabels, pearson, spearman]);

  // Export handler
  const onExport = () => {
    const payload = {
      run_id: runLabel,
      selected_feature: feature,
      range,
      segment,
      summary: executiveKpis,
      feature_stat: stat,
      pair_metrics: pairMetrics,
      insights: aiInsights,
      recommendations: recommendationCards,
      generated_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `distribution_lab_${runLabel}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Main render
  return (
    <div className="space-y-3">
      <div className="card" style={{ background: 'linear-gradient(125deg, rgba(37,99,235,.08), rgba(14,165,233,.06), rgba(217,119,6,.07))' }}>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="text-[14px] font-semibold text-t1">Distribution Lab</div>
            <div className="text-[11px] text-t3 mt-1">AI-powered statistical intelligence and distribution observability workspace.</div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <select className="btn btn-sm" value={runLabel} disabled title="Dataset selector">
              <option value={runLabel}>Dataset: {runLabel}</option>
            </select>
            <select className="btn btn-sm" value={feature} onChange={(e) => setFeature(e.target.value)} title="Feature selector">
              {(featureNames.length ? featureNames : ['n/a']).map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
            <select className="btn btn-sm" value={range} onChange={(e) => setRange(e.target.value)} title="Time-range selector">
              <option value="all">All Time</option>
              <option value="last_90d">Last 90 Days</option>
              <option value="last_30d">Last 30 Days</option>
              <option value="last_7d">Last 7 Days</option>
            </select>
            <select className="btn btn-sm" value={segment} onChange={(e) => setSegment(e.target.value)} title="Segment filter">
              <option value="all">All Segments</option>
              <option value="high_risk">High Risk</option>
              <option value="medium_risk">Medium Risk</option>
              <option value="low_risk">Low Risk</option>
            </select>
            <button className="btn btn-sm" onClick={onExport}>Export Analysis</button>
          </div>
        </div>
        <div className="mt-3 px-3 py-2 rounded-sm border border-dborder bg-bg4 text-[11px] text-t2">
          <span className="font-semibold text-t1">AI Insight Banner:</span> Statistical readiness is {pct(readiness)} with
          {' '}{num(skewedCount, 0)} skewed feature(s), {num(heavyTailCount, 0)} heavy-tail feature(s), and
          {' '}multicollinearity risk at {pct(multiRisk)}. Prioritize transformation and dependency controls before production retraining.
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
        {executiveKpis.map((card) => (
          <div key={card.name} className="card" title={card.tooltip}>
            <div className="flex items-center justify-between gap-2">
              <div className="text-[10px] uppercase tracking-wider text-t3">{card.name}</div>
              <span className="text-[9px] px-2 py-0.5 rounded-full" style={severityStyle(card.severity)}>{card.severity}</span>
            </div>
            <div className="text-[19px] font-sora text-t1 mt-1">{card.value}</div>
            <div className="text-[10px] text-t3">Trend {card.delta}</div>
            <Sparkline values={card.spark} />
          </div>
        ))}
      </div>
      {/* Intelligence Tabs */}
      <div className="flex gap-2 mt-2 mb-2">
        <button
          className={`btn btn-sm ${intelligenceTab === 'univariate' ? 'bg-amber-200 text-t1 font-semibold' : 'bg-bg4 text-t2'}`}
          onClick={() => setIntelligenceTab('univariate')}
        >
          Univariate Intelligence
        </button>
        <button
          className={`btn btn-sm ${intelligenceTab === 'bivariate' ? 'bg-amber-200 text-t1 font-semibold' : 'bg-bg4 text-t2'}`}
          onClick={() => setIntelligenceTab('bivariate')}
        >
          Bivariate Intelligence
        </button>
        <button
          className={`btn btn-sm ${intelligenceTab === 'multivariate' ? 'bg-amber-200 text-t1 font-semibold' : 'bg-bg4 text-t2'}`}
          onClick={() => setIntelligenceTab('multivariate')}
        >
          Multivariate Intelligence
        </button>
      </div>
      {/* Tab Content */}
      {intelligenceTab === 'univariate' && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 xl:col-span-9 space-y-3">
            <div className="card">
              <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                <div>
                  <div className="text-[12px] font-semibold text-t1">Univariate Intelligence</div>
                  <div className="text-[10px] text-t3">Feature-level distribution diagnostics with risk annotations.</div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search feature"
                    className="px-2 py-1 text-[11px] rounded-sm border border-dborder bg-bg4 text-t1"
                  />
                  <select className="btn btn-sm" value={view} onChange={(e) => setView(e.target.value)}>
                    <option value="hist">Histogram</option>
                    <option value="percentile">Percentiles</option>
                    <option value="qq">QQ Plot</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-12 md:col-span-3 bg-bg4 border border-dborder rounded-sm px-2 py-2 max-h-[340px] overflow-auto">
                  {featureRows.slice(0, 40).map((row) => {
                    const active = row.name === feature;
                    const sev = severityFor(row.risk / 3, 0.7, 0.35);
                    return (
                      <button
                        key={row.name}
                        className="w-full text-left px-2 py-1.5 rounded-sm mb-1 border"
                        style={active
                          ? { borderColor: '#2563eb', background: 'rgba(37,99,235,.1)' }
                          : { borderColor: 'rgba(148,163,184,.2)', background: 'transparent' }}
                        onClick={() => setFeature(row.name)}
                      >
                        <div className="text-[11px] text-t1 truncate" title={row.name}>{row.name}</div>
                        <div className="text-[10px] text-t3">skew {num(row.skew)} · kurt {num(row.kurt)} · outliers {num(row.outlierTotal, 0)}</div>
                        <div className="mt-1 inline-block text-[9px] px-1.5 py-0.5 rounded-full" style={severityStyle(sev)}>{sev} anomaly marker</div>
                      </button>
                    );
                  })}
                  {!featureRows.length && <div className="text-[11px] text-t3">No statistical profiles available.</div>}
                </div>
                <div className="col-span-12 md:col-span-6 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Primary visualization</div>
                  <ChartRenderer chart={univariateChart} />
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div className="text-[10px] text-t3">Mean {num(stat?.mean)} · Median {num(stat?.median)} · Mode {num(stat?.mode)}</div>
                    <div className="text-[10px] text-t3">Std {num(stat?.std_dev)} · Var {num(stat?.variance)} · CV {num(safeNum(stat?.std_dev) / Math.max(Math.abs(safeNum(stat?.mean)), 0.0001), 3)}</div>
                    <div className="text-[10px] text-t3">Skew {num(stat?.skewness)} · Kurtosis {num(stat?.kurtosis)} · Entropy {num(stat?.entropy)}</div>
                    <div className="text-[10px] text-t3">P10 {num(stat?.p10)} · Q1 {num(stat?.q1)} · Q3 {num(stat?.q3)} · P90 {num(stat?.p90)}</div>
                  </div>
                </div>
                <div className="col-span-12 md:col-span-3 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">AI Insights</div>
                  {aiInsights.map((it) => (
                    <details key={it.title} className="mb-2 border border-dborder rounded-sm px-2 py-1" open>
                      <summary className="text-[10px] font-semibold text-t1 cursor-pointer">{it.title}</summary>
                      <div className="text-[10px] text-t2 mt-1">{it.message}</div>
                      <div className="text-[10px] text-t3 mt-1"><span className="text-t2">Business:</span> {it.business}</div>
                      <div className="text-[10px] text-t3 mt-1"><span className="text-t2">ML:</span> {it.ml}</div>
                      <div className="text-[10px] text-t3 mt-1"><span className="text-t2">Action:</span> {it.action}</div>
                      <div className="mt-1 inline-block text-[9px] px-1.5 py-0.5 rounded-full" style={severityStyle(it.severity)}>
                        {it.severity} · confidence {num(it.confidence * 100, 0)}%
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {intelligenceTab === 'bivariate' && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 xl:col-span-9 space-y-3">
            <div className="card">
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <div>
                  <div className="text-[12px] font-semibold text-t1">Bivariate Intelligence</div>
                  <div className="text-[10px] text-t3">Relationship observability with linear and nonlinear dependency cues.</div>
                </div>
                <div className="flex items-center gap-2">
                  <select className="btn btn-sm" value={feature} onChange={(e) => setFeature(e.target.value)}>
                    {(featureNames.length ? featureNames : ['n/a']).map((name) => (
                      <option key={`a-${name}`} value={name}>{name}</option>
                    ))}
                  </select>
                  <select className="btn btn-sm" value={compareFeature} onChange={(e) => setCompareFeature(e.target.value)}>
                    {(featureNames.length ? featureNames : ['n/a']).map((name) => (
                      <option key={`b-${name}`} value={name}>{name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-12 gap-2">
                <div className="col-span-12 lg:col-span-8 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Correlation Heatmap</div>
                  <ChartRenderer chart={bivariateHeatmap} />
                </div>
                <div className="col-span-12 lg:col-span-4 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Dependency Intelligence</div>
                  <div className="text-[10px] text-t3">Pearson: {num(pairMetrics.pearson, 3)}</div>
                  <div className="text-[10px] text-t3">Spearman: {num(pairMetrics.spearman, 3)}</div>
                  <div className="text-[10px] text-t3">Kendall (proxy): {num(pairMetrics.kendallProxy, 3)}</div>
                  <div className="text-[10px] text-t3">Interaction strength: {num(Math.abs(pairMetrics.pearson) * 100)}%</div>
                  <div className="text-[10px] text-t3">Linearity score: {num((1 - pairMetrics.corrDelta) * 100)}%</div>
                  <div className="text-[10px] text-t3">Nonlinear signal delta: {num(pairMetrics.corrDelta, 3)}</div>
                  <div className="mt-2 text-[10px] text-t2">Business interpretation: {Math.abs(pairMetrics.pearson) >= 0.7 ? 'Strong dependency may indicate shared business driver.' : 'Moderate/weak dependency suggests segmented behavior.'}</div>
                  <div className="mt-1 text-[10px] text-t2">ML interpretation: {pairMetrics.corrDelta > 0.18 ? 'Nonlinear candidate; interaction features recommended.' : 'Linear relation likely sufficient as first baseline.'}</div>
                </div>
                <div className="col-span-12 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Linear vs Rank Dependency Map</div>
                  <ChartRenderer chart={bivariateScatter} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {intelligenceTab === 'multivariate' && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 xl:col-span-9 space-y-3">
            <div className="card">
              <div className="text-[12px] font-semibold text-t1">Multivariate Intelligence</div>
              <div className="text-[10px] text-t3 mb-2">Hidden interaction structure, covariance concentration, and segmentation proxies.</div>
              <div className="grid grid-cols-12 gap-2">
                <div className="col-span-12 lg:col-span-8 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Covariance Heatmap</div>
                  <ChartRenderer chart={covHeatmap} />
                </div>
                <div className="col-span-12 lg:col-span-4 bg-bg4 border border-dborder rounded-sm px-2 py-2">
                  <div className="text-[11px] font-semibold text-t1 mb-1">Cluster Quality Summary</div>
                  <div className="text-[10px] text-t3">KMeans readiness: {num(Math.max(0, 1 - (safeNum(checks?.schema_drift) / Math.max(1, featureCount))), 2)}</div>
                  <div className="text-[10px] text-t3">DBSCAN viability: {num(Math.min(1, outlierDensity / 3 + 0.25), 2)}</div>
                  <div className="text-[10px] text-t3">Hierarchical separation (proxy): {num(Math.max(0, Math.min(1, maxCorr)), 2)}</div>
                  <div className="text-[10px] text-t2 mt-2">Segment discovery: {num(Math.max(1, Math.min(6, safeNum(kg?.connected_components) + 1)), 0)} high-confidence segment candidate(s).</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
