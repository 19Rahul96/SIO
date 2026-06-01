// Scope-aware Observatory analytics sections, shared by the unified Semantic OS page.
// Every section accepts a `scope` prop = source_id ('' = all sources) and threads it
// into its sioApi calls + useFetch deps so the same component serves both views.
import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import sioApi from '../../services/sioApi'
import { Donut, Bars, Gauge, StatTiles } from '../sio/charts'
import { ConfidenceHeatmap, BoxPlot } from './charts'
import ChartRenderer from '../eda2/charts/ChartRenderer'
import KGGraph from '../sio/KGGraph'
import EDAEmptyState from './utils/EDAEmptyState'
import { getConfidenceColor } from './utils/confidenceColorScale'
import { correlationHeatmap } from './utils/chartAdapter'

export const GLASS = {
  backdropFilter: 'blur(12px)', background: 'rgba(255,255,255,0.7)',
  border: '1px solid rgba(255,255,255,0.6)', borderRadius: 12, boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
}

export function useFetch(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  useEffect(() => {
    let alive = true
    setState({ loading: true, data: null, error: null })
    fn().then((d) => alive && setState({ loading: false, data: d, error: null }))
      .catch((e) => alive && setState({ loading: false, data: null, error: e.message }))
    return () => { alive = false }
  }, deps) // eslint-disable-line
  return state
}

export function Panel({ title, children, sub }) {
  return (
    <div style={GLASS} className="p-5 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-t2">{title}</div>
        {sub && <div className="text-[10px] text-t3">{sub}</div>}
      </div>
      {children}
    </div>
  )
}

export function Body({ state, children, emptyMsg }) {
  if (state.loading) return <div className="text-[11px] text-t3 py-8 text-center">Loading…</div>
  if (state.error) return <div className="text-[11px] text-coral py-8 text-center">{state.error}</div>
  if (!state.data || state.data.empty) return <EDAEmptyState message={state.data?.reason || emptyMsg} />
  return children(state.data)
}

export function SubTabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1.5 mb-4">
      {tabs.map((t) => (
        <button key={t} onClick={() => onChange(t)}
          className={`px-3 py-1 rounded-full text-[11px] font-medium border ${active === t ? 'bg-accent text-white border-accent' : 'bg-transparent text-t3 border-dborder hover:bg-bg4'}`}>{t}</button>
      ))}
    </div>
  )
}

/* Section 1 — KPI & Health */
export function KPIHealth({ scope = '' }) {
  const s = useFetch(() => sioApi.edaSummary(scope), [scope])
  return (
    <Panel title="KPI & Health">
      <Body state={s}>
        {(d) => (
          <div className="grid md:grid-cols-[260px_1fr] gap-4 items-center">
            <Gauge value={d.graph_trust_score} title={d.trust_band || 'trust'} />
            <StatTiles tiles={[
              { label: 'Graph nodes', value: d.graph.node_count, color: '#4f46e5' },
              { label: 'Edges', value: d.graph.edge_count, color: '#0d9488' },
              { label: 'Density', value: d.graph.density, color: '#d97706' },
              { label: 'Sources', value: d.sources_count, color: '#7c3aed' },
              { label: 'Orphan nodes', value: d.graph.orphan_count, color: '#d97706' },
              { label: 'Ontology violations', value: d.ontology_violations, color: '#e11d48' },
              { label: 'Avg hallucination', value: d.avg_hallucination_risk, color: '#e11d48' },
              { label: 'Low-conf edges', value: d.graph.low_confidence_edges, color: '#d97706' },
            ]} />
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* Section 2 — Data Quality */
export function DataQuality({ scope = '' }) {
  const [sub, setSub] = useState('Validation')
  return (
    <div>
      <SubTabs tabs={['Validation', 'Statistics', 'Distributions']} active={sub} onChange={setSub} />
      {sub === 'Validation' && <DQValidation scope={scope} />}
      {sub === 'Statistics' && <DQStatistics scope={scope} />}
      {sub === 'Distributions' && <DQDistributions scope={scope} />}
    </div>
  )
}
function DQValidation({ scope }) {
  const s = useFetch(() => sioApi.edaValidation(scope), [scope])
  return (
    <Panel title="Validation — consistency checks">
      <Body state={s} emptyMsg="No issues detected in current ingestion.">
        {(d) => (
          <StatTiles tiles={[
            { label: 'Invalid dates', value: d.totals.invalid_dates, color: '#e11d48' },
            { label: 'Type mismatches', value: d.totals.type_mismatches, color: '#d97706' },
            { label: 'Null key violations', value: d.totals.null_key_violations, color: '#e11d48' },
            { label: 'Duplicates', value: d.totals.duplicates, color: '#d97706' },
          ]} />
        )}
      </Body>
    </Panel>
  )
}
function DQStatistics({ scope }) {
  const s = useFetch(() => sioApi.edaColumns(scope), [scope])
  return (
    <Panel title="Per-column statistics">
      <Body state={s} emptyMsg="No numeric columns found in ingested data.">
        {(d) => {
          const numeric = d.columns.filter((c) => c.is_numeric)
          if (!numeric.length) return <EDAEmptyState message="No numeric columns found in ingested data." />
          return (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead><tr className="text-t3 text-left">
                  {['Column', 'Mean', 'Median', 'Std', 'P10', 'P90', 'Skew', 'Kurtosis'].map((h) => <th key={h} className="py-1 pr-4">{h}</th>)}
                </tr></thead>
                <tbody>
                  {numeric.map((c) => (
                    <tr key={c.source_id + c.column} className="border-t border-dborder">
                      <td className="py-1 pr-4 font-medium text-t1">{c.column}</td>
                      <td className="py-1 pr-4">{c.mean}</td><td className="py-1 pr-4">{c.median}</td>
                      <td className="py-1 pr-4">{c.std_dev}</td><td className="py-1 pr-4">{c.p10}</td>
                      <td className="py-1 pr-4">{c.p90}</td><td className="py-1 pr-4">{c.skewness}</td>
                      <td className="py-1 pr-4">{c.kurtosis}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-4 grid md:grid-cols-2 gap-4">
                {numeric.slice(0, 4).map((c) => (
                  <div key={c.column}>
                    <div className="text-[10px] text-t3 mb-1">{c.column} — histogram</div>
                    <Bars data={Object.fromEntries((c.histogram || []).map((b) => [`${b.min}`, b.count]))} color="#4f46e5" height={180} />
                  </div>
                ))}
              </div>
            </div>
          )
        }}
      </Body>
    </Panel>
  )
}
function DQDistributions({ scope }) {
  const s = useFetch(() => sioApi.edaColumns(scope), [scope])
  const [sel, setSel] = useState(null)
  const numeric = (s.data?.columns || []).filter((c) => c.is_numeric)
  const col = numeric.find((c) => c.column === sel) || numeric[0]
  return (
    <Panel title="Distribution lab">
      <Body state={s} emptyMsg="No numeric columns found in ingested data.">
        {() => !col ? <EDAEmptyState message="No numeric columns found." /> : (
          <div>
            <select value={col.column} onChange={(e) => setSel(e.target.value)}
              className="bg-bg3 border border-dborder2 rounded-sm px-3 py-1.5 text-xs mb-4">
              {numeric.map((c) => <option key={c.column}>{c.column}</option>)}
            </select>
            <div className="grid md:grid-cols-3 gap-4">
              <div><div className="text-[10px] text-t3 mb-1">Box plot</div><BoxPlot box={col.box} name={col.column} /></div>
              <div><div className="text-[10px] text-t3 mb-1">Z-score distribution</div><Bars data={col.zscore_bins} color="#7c3aed" height={220} /></div>
              <div><div className="text-[10px] text-t3 mb-1">Q–Q plot</div><QQ col={col} /></div>
            </div>
            <div className="mt-3 text-[11px] text-t2">IQR outliers: <b>{col.outliers_iqr_count}</b> · Z-score outliers: <b>{col.outliers_zscore_count}</b></div>
          </div>
        )}
      </Body>
    </Panel>
  )
}
function QQ({ col }) {
  const pts = (col.qq_points || []).map((p) => [p.expected, p.actual])
  const lo = Math.min(...pts.flat()), hi = Math.max(...pts.flat())
  const option = {
    grid: { left: 40, right: 16, top: 16, bottom: 30 },
    xAxis: { type: 'value', axisLabel: { fontSize: 9 } }, yAxis: { type: 'value', axisLabel: { fontSize: 9 } },
    series: [
      { type: 'scatter', symbolSize: 6, data: pts, itemStyle: { color: '#4f46e5' } },
      { type: 'line', data: [[lo, lo], [hi, hi]], lineStyle: { color: '#94a3b8', type: 'dashed' }, symbol: 'none' },
    ],
  }
  return <ReactECharts option={option} style={{ height: 220 }} notMerge />
}

/* Section 3 — Correlation & Outliers */
export function CorrelationOutliers({ scope = '' }) {
  const [sub, setSub] = useState('Correlation')
  return (
    <div>
      <SubTabs tabs={['Correlation', 'Outliers']} active={sub} onChange={setSub} />
      {sub === 'Correlation' ? <Correlation scope={scope} /> : <Outliers scope={scope} />}
    </div>
  )
}
function Correlation({ scope }) {
  const s = useFetch(() => sioApi.edaCorrelation(scope), [scope])
  return (
    <Panel title="Correlation matrix" sub="reuses eda2 ChartRenderer">
      <Body state={s} emptyMsg="At least 2 numeric columns required to compute correlations.">
        {(d) => (
          <>
            <ChartRenderer chart={correlationHeatmap(d)} />
            <div className="mt-3 text-[11px]">
              <div className="text-t3 uppercase tracking-wider mb-1">Strongest pairs</div>
              {(d.pair_explorer || []).slice(0, 8).map((p, i) => (
                <div key={i} className="flex justify-between border-t border-dborder py-1">
                  <span>{p.left} ↔ {p.right}</span>
                  <span style={{ color: p.pearson >= 0 ? '#1D9E75' : '#E24B4A' }}>r={p.pearson}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </Body>
    </Panel>
  )
}
function Outliers({ scope }) {
  const s = useFetch(() => sioApi.edaOutliers(scope), [scope])
  return (
    <Panel title="Outlier burden">
      <Body state={s} emptyMsg="No numeric data available.">
        {(d) => (
          <>
            <Bars data={Object.fromEntries(d.columns.map((c) => [c.column, c.outliers_iqr_count + c.outliers_zscore_count]))}
                  color="#e11d48" horizontal height={Math.max(160, d.columns.length * 28)} />
            <div className="mt-4 grid md:grid-cols-3 gap-4">
              {d.columns.slice(0, 6).map((c) => (
                <div key={c.column}><div className="text-[10px] text-t3 mb-1">{c.column}</div><BoxPlot box={c.box} name={c.column} /></div>
              ))}
            </div>
          </>
        )}
      </Body>
    </Panel>
  )
}

/* Section 4 — KG Analytics (graph stats + relationship histogram + top entities) */
export function KGAnalytics({ scope = '' }) {
  const stats = useFetch(() => sioApi.graphStats(scope), [scope])
  const ents = useFetch(() => sioApi.graphEntities('', scope), [scope])
  const rels = useFetch(() => sioApi.graphRelationships(scope), [scope])
  const histo = useMemo(() => {
    const buckets = { '0–0.2': 0, '0.2–0.4': 0, '0.4–0.6': 0, '0.6–0.8': 0, '0.8–1.0': 0 }
    ;(rels.data?.relationships || []).forEach((r) => {
      const c = r.confidence || 0
      const k = c < 0.2 ? '0–0.2' : c < 0.4 ? '0.2–0.4' : c < 0.6 ? '0.4–0.6' : c < 0.8 ? '0.6–0.8' : '0.8–1.0'
      buckets[k] += 1
    })
    return buckets
  }, [rels.data])
  return (
    <div>
      <Panel title="Knowledge graph analytics">
        <Body state={stats}>
          {(d) => (
            <StatTiles tiles={[
              { label: 'Nodes', value: d.node_count, color: '#4f46e5' },
              { label: 'Edges', value: d.edge_count, color: '#0d9488' },
              { label: 'Density', value: d.density, color: '#d97706' },
              { label: 'Components', value: d.connected_components, color: '#7c3aed' },
              { label: 'Orphan nodes', value: d.orphan_count, color: '#d97706' },
              { label: 'Low-conf edges', value: d.low_confidence_edges, color: '#e11d48' },
            ]} />
          )}
        </Body>
      </Panel>
      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Relationship confidence histogram"><Body state={rels}>{() => <Bars data={histo} color="#0d9488" />}</Body></Panel>
        <Panel title="Entity growth"><EDAEmptyState message="Ingest more data across runs to see growth trend." /></Panel>
      </div>
      <Panel title="Top connected entities">
        <Body state={ents}>
          {(d) => (
            <table className="w-full text-[11px]">
              <thead><tr className="text-t3 text-left">{['Entity', 'Type', 'Degree', 'Confidence', 'Sources'].map((h) => <th key={h} className="py-1 pr-4">{h}</th>)}</tr></thead>
              <tbody>
                {d.entities.slice(0, 10).map((e) => (
                  <tr key={e.canonical_id} className="border-t border-dborder">
                    <td className="py-1 pr-4 font-medium text-t1">{e.label}</td>
                    <td className="py-1 pr-4">{e.entity_type}</td>
                    <td className="py-1 pr-4">{e.degree_centrality}</td>
                    <td className="py-1 pr-4"><span style={{ color: getConfidenceColor(e.confidence) }}>{e.confidence ?? '—'}</span></td>
                    <td className="py-1 pr-4">{e.source_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Body>
      </Panel>
    </div>
  )
}

/* Section 5 — Semantic Confidence Heatmap */
export function SemanticHeatmap({ scope = '' }) {
  const s = useFetch(() => sioApi.edaConfidence(scope), [scope])
  const [cell, setCell] = useState(null)
  return (
    <Panel title="Semantic confidence heatmap" sub="entity × pipeline layer">
      <Body state={s} emptyMsg="No confidence data available. Ingest data and run the full pipeline to populate this view.">
        {(d) => (
          <div className="grid md:grid-cols-[1fr_220px] gap-3">
            <ConfidenceHeatmap matrix={d} onCell={setCell} />
            <div style={GLASS} className="p-3">
              <div className="text-[10px] uppercase tracking-widest text-t3 mb-2">Cell detail</div>
              {!cell ? <div className="text-[11px] text-t3">Click a cell to inspect the entity's confidence at that layer.</div> : (
                <div className="text-[11px] space-y-1">
                  <div className="text-sm font-bold text-t1">{cell.entity.label}</div>
                  <div className="text-t2">Layer: <b>{cell.layer}</b></div>
                  <div className="text-t2">Score: <span style={{ color: getConfidenceColor(cell.score) }}>{cell.score ?? '— (no signal)'}</span></div>
                  <div className="text-t2">Type: {cell.entity.entity_type}</div>
                </div>
              )}
            </div>
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* Section 6 — Graph Trust Overlay (interactive graph) */
export function GraphTrust({ scope = '' }) {
  const g = useFetch(() => sioApi.graph(), [])
  const stats = useFetch(() => sioApi.graphStats(scope), [scope])
  const [thr, setThr] = useState(0)
  const inScope = (e) => !scope || (e.provenance || []).includes(scope)
  const nodeInScope = (n) => !scope || (n.provenance || []).includes(scope)
  const nodes = useMemo(() => Object.values(g.data?.nodes || {}).filter(nodeInScope), [g.data, scope])
  const edges = useMemo(() => Object.values(g.data?.edges || {}).filter((e) => inScope(e) && (e.confidence || 0) >= thr), [g.data, thr, scope])
  return (
    <Panel title="Graph trust overlay" sub="node color ~ type · edge color ~ confidence">
      <Body state={g}>
        {() => nodes.length ? (
          <div>
            <div className="flex items-center gap-3 mb-3 text-[11px]">
              <span className="text-t3">Trust threshold</span>
              <input type="range" min="0" max="1" step="0.05" value={thr} onChange={(e) => setThr(Number(e.target.value))} />
              <span>{thr.toFixed(2)}</span>
              {stats.data && !stats.data.empty && (
                <span className="ml-auto text-t3">density {stats.data.density} · components {stats.data.connected_components} · orphans {stats.data.orphan_count}</span>
              )}
            </div>
            <KGGraph nodes={nodes} edges={edges} />
          </div>
        ) : <EDAEmptyState message="No knowledge graph data available. Ingest data to build the graph." />}
      </Body>
    </Panel>
  )
}

/* Section 7 — Extraction Quality */
export function ExtractionQuality({ scope = '' }) {
  const s = useFetch(() => sioApi.edaExtraction(scope), [scope])
  return (
    <Panel title="Extraction quality">
      <Body state={s} emptyMsg="No extraction data available. Upload files or connect a database to see extraction quality.">
        {(d) => (
          <>
            <div className="grid md:grid-cols-2 gap-4 mb-4">
              <div><div className="text-[10px] text-t3 mb-1">Parser confidence by source</div>
                <Bars data={Object.fromEntries((d.parser_confidence || []).map((p) => [p.source_id, p.confidence]))} color="#4f46e5" horizontal /></div>
              {d.pdf_quality?.length > 0 && (
                <div><div className="text-[10px] text-t3 mb-1">OCR / page confidence</div>
                  <Bars data={Object.fromEntries((d.pdf_quality[0].page_confidence || []).map((p) => [`p${p.page}`, p.confidence]))} color="#d97706" /></div>
              )}
            </div>
            <div className="text-[10px] text-t3 mb-1">Extraction lineage</div>
            <div className="overflow-x-auto" style={{ maxHeight: 320 }}>
              <table className="w-full text-[11px]">
                <thead><tr className="text-t3 text-left">{['Chunk', 'Source', 'Adapter', 'Confidence', 'Page/Row', 'Entities', 'Warnings'].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}</tr></thead>
                <tbody>
                  {d.lineage.slice(0, 200).map((r, i) => (
                    <tr key={i} className="border-t border-dborder">
                      <td className="py-1 pr-3">{r.chunk_id}</td><td className="py-1 pr-3">{r.source_file}</td>
                      <td className="py-1 pr-3">{r.adapter}</td>
                      <td className="py-1 pr-3"><span style={{ color: getConfidenceColor(r.confidence) }}>{r.confidence}</span></td>
                      <td className="py-1 pr-3">{r.page_or_row}</td><td className="py-1 pr-3">{r.entity_count}</td>
                      <td className="py-1 pr-3 text-amber">{(r.warnings || []).join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Body>
    </Panel>
  )
}

/* Section 8 — AI Trust Command Center */
export function AITrustCenter({ scope = '' }) {
  const m = useFetch(() => sioApi.metricsAggregate(scope), [scope])
  return (
    <div>
      <Panel title="AI trust command center">
        <Body state={m}>
          {(d) => {
            const gt = (d.graph_trust ?? 0) * 100, mc = (d.metadata_coverage ?? 0) * 100
            const hr = (d.hallucination_risk ?? 0) * 100, ra = (d.retrieval_accuracy ?? 0) * 100
            const readiness = Math.round(gt * 0.3 + mc * 0.2 + (100 - hr) * 0.3 + ra * 0.2)
            const tier = readiness <= 40 ? 'Not Ready' : readiness <= 65 ? 'Developing' : readiness <= 85 ? 'Production Ready' : 'Enterprise Grade'
            return (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <GaugeCard title="Graph Trust" value={d.graph_trust} />
                  <GaugeCard title="Metadata Coverage" value={d.metadata_coverage} />
                  <GaugeCard title="Hallucination Risk" value={d.hallucination_risk} invert />
                  <GaugeCard title={`Retrieval${d.retrieval_accuracy_proxy ? ' (proxy)' : ''}`} value={d.retrieval_accuracy} />
                </div>
                <div style={GLASS} className="p-4 text-center">
                  <div className="text-[10px] uppercase tracking-widest text-t3">Enterprise AI Readiness</div>
                  <div className="text-3xl font-bold text-t1 my-1">{readiness}</div>
                  <span className="pill-b">{tier}</span>
                </div>
              </>
            )
          }}
        </Body>
      </Panel>
      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Graph stability"><EDAEmptyState message="Ingest more data across runs to see the stability trend." /></Panel>
        <Panel title="Active alerts"><AlertsCard scope={scope} /></Panel>
      </div>
    </div>
  )
}
function GaugeCard({ title, value, invert }) {
  if (value == null) return (
    <div style={GLASS} className="p-3 text-center">
      <div className="text-[10px] uppercase tracking-widest text-t3 mb-1">{title}</div>
      <div className="text-t3 text-xs py-6 border-2 border-dashed border-dborder2 rounded-full mx-auto" style={{ width: 90, height: 90, lineHeight: '78px' }}>Pending</div>
    </div>
  )
  return <div style={GLASS} className="p-1"><Gauge value={value} title={title} invert={invert} height={150} /></div>
}
function AlertsCard({ scope }) {
  const s = useFetch(() => sioApi.edaSummary(scope), [scope])
  return (
    <Body state={s}>
      {(d) => (
        <div className="space-y-2 text-[11px]">
          <Alert label="Ontology violations" value={d.ontology_violations} />
          <Alert label="Orphan nodes" value={d.graph?.orphan_count} />
          <Alert label="Low-confidence edges" value={d.graph?.low_confidence_edges} />
        </div>
      )}
    </Body>
  )
}
function Alert({ label, value }) {
  const tone = value > 0 ? '#e11d48' : '#16a34a'
  return (
    <div className="flex items-center justify-between border-t border-dborder py-1.5">
      <span className="text-t2">{label}</span>
      <span className="font-semibold px-2 py-0.5 rounded-lg" style={{ color: tone, background: `${tone}14` }}>{value ?? 0}</span>
    </div>
  )
}
