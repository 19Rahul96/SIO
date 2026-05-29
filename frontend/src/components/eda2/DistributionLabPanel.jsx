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
  // ...existing code...
  // --- State and derived variables (same as before) ---
  const [search, setSearch] = useState("");
  const [feature, setFeature] = useState("");
  const [compareFeature, setCompareFeature] = useState("");
  const [intelligenceTab, setIntelligenceTab] = useState("univariate");
  const columns = stats?.columns || {};
  const featureNames = useMemo(() => Object.keys(columns), [columns]);
  useEffect(() => {
    if (!feature && featureNames.length) setFeature(featureNames[0]);
  }, [feature, featureNames]);
  useEffect(() => {
    if (!compareFeature && featureNames.length > 1) setCompareFeature(featureNames[1]);
  }, [compareFeature, featureNames]);
  const stat = columns[feature] || {};
  const outlierRow = (outliers?.columns || []).find((r) => r.column === feature) || {};
  const outlierCount = safeNum(outlierRow.iqr_outliers) + safeNum(outlierRow.zscore_outliers);
  const corrLabels = corr?.labels || [];
  const pearson = corr?.pearson || [];
  const spearman = corr?.spearman || [];
  // --- Pair metrics for bivariate tab ---
  const pairMetrics = useMemo(() => {
    const i = corrLabels.indexOf(feature);
    const j = corrLabels.indexOf(compareFeature);
    if (i < 0 || j < 0) return { pearson: 0, spearman: 0, kendallProxy: 0, corrDelta: 0 };
    return {
      pearson: safeNum((pearson[i] || [])[j]),
      spearman: safeNum((spearman[i] || [])[j]),
      kendallProxy: 0,
      corrDelta: Math.abs(safeNum((pearson[i] || [])[j]) - safeNum((spearman[i] || [])[j])),
    };
  }, [feature, compareFeature, corrLabels, pearson, spearman]);

  // --- UI ---
  return (
    <div className="space-y-3">
      <div className="stabs flex gap-2 mb-2">
        <button className={`sb btn btn-sm ${intelligenceTab === 'univariate' ? 'on bg-amber-200 text-t1 font-semibold' : ''}`} onClick={() => setIntelligenceTab('univariate')}>Univariate</button>
        <button className={`sb btn btn-sm ${intelligenceTab === 'bivariate' ? 'on bg-amber-200 text-t1 font-semibold' : ''}`} onClick={() => setIntelligenceTab('bivariate')}>Bivariate</button>
        <button className={`sb btn btn-sm ${intelligenceTab === 'multivariate' ? 'on bg-amber-200 text-t1 font-semibold' : ''}`} onClick={() => setIntelligenceTab('multivariate')}>Multivariate</button>
      </div>

      {/* Univariate Tab */}
      {intelligenceTab === 'univariate' && (
        <div className="sp grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Histograms — frequency distribution</div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] text-t3">Column:</span>
                <select className="btn btn-xs" value={feature} onChange={e => setFeature(e.target.value)}>
                  {featureNames.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              </div>
              <div style={{height: 210}}><ChartRenderer chart={stats?.histograms?.[feature] || {}} /></div>
            </div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Box plots — spread & outliers</div>
              <div style={{height: 130}}><ChartRenderer chart={stats?.boxplots?.[feature] || {}} /></div>
            </div>
          </div>
          <div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Skewness & outlier scatter</div>
              <div style={{height: 210}}><ChartRenderer chart={stats?.skewOutlierScatter || {}} /></div>
            </div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Distribution profiles</div>
              {(stats?.profileCards || []).map((card, idx) => (
                <div key={idx} className={`ir ${card.type}`}> {/* type: iw, ird, ii, io */}
                  <div className="il font-semibold">{card.label}</div>
                  <div className="it text-[11px]">{card.text}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bivariate Tab */}
      {intelligenceTab === 'bivariate' && (
        <div className="sp grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Num vs num — scatter plot</div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] text-t3">X:</span>
                <select className="btn btn-xs" value={feature} onChange={e => setFeature(e.target.value)}>
                  {featureNames.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
                <span className="text-[11px] text-t3">Y:</span>
                <select className="btn btn-xs" value={compareFeature} onChange={e => setCompareFeature(e.target.value)}>
                  {featureNames.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              </div>
              <div style={{height: 210}}><ChartRenderer chart={corr?.bivariateScatter || {}} /></div>
            </div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Num vs categorical — violin / box</div>
              <div style={{height: 140}}><ChartRenderer chart={corr?.numCatViolin || {}} /></div>
            </div>
          </div>
          <div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Categorical vs categorical — stacked bar</div>
              <div style={{height: 160}}><ChartRenderer chart={corr?.catCatStacked || {}} /></div>
            </div>
            <div className="p card mb-4">
              <div className="pt font-semibold mb-2">Cross-tabulation</div>
              {/* Render a table if available */}
              {corr?.crossTab ? (
                <table className="w-full text-[11px] border-collapse">
                  <thead>
                    <tr>
                      <th className="text-left p-1">{corr.crossTab.rowLabel}</th>
                      {corr.crossTab.colLabels.map((col, idx) => (
                        <th key={idx} className="text-right p-1">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {corr.crossTab.rows.map((row, idx) => (
                      <tr key={idx}>
                        <td className="p-1 text-t2">{row.label}</td>
                        {row.values.map((val, j) => (
                          <td key={j} className="p-1 text-right">{val}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <div className="text-[11px] text-t3">No cross-tabulation data.</div>}
            </div>
          </div>
        </div>
      )}

      {/* Multivariate tab visuals */}
      {intelligenceTab === 'multivariate' && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 xl:col-span-12 space-y-3">
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
