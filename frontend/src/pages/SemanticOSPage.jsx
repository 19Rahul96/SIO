import { useEffect, useMemo, useState } from 'react'
import {
  UploadCloud, FileText, ListTree, Sparkles, Network, ShieldCheck, Boxes, Activity,
  BookOpen, Layers, Workflow, Gauge as GaugeIcon, AlertTriangle, FileSearch, Grid3x3, GitBranch,
} from 'lucide-react'
import sioApi from '../services/sioApi'
import { Donut, Bars, Gauge, StatTiles, ConfBars, TaxonomyGraph } from '../components/sio/charts'
import EDAEmptyState from '../components/eda/utils/EDAEmptyState'
import { getConfidenceColor } from '../components/eda/utils/confidenceColorScale'
import {
  useFetch, Panel, Body, SubTabs,
  KPIHealth, DataQuality, CorrelationOutliers, KGAnalytics, SemanticHeatmap, GraphTrust,
  ExtractionQuality, AITrustCenter,
} from '../components/eda/sections'

const DB_ENGINES = ['postgresql', 'mysql', 'sqlite']

// Unified tabs — every one of the 14 layers appears exactly once (no Observatory/Semantic-OS overlap).
const TABS = [
  { key: 'pipeline', label: 'Pipeline', icon: Workflow },         // 14-layer run status (last run)
  { key: 'overview', label: 'Overview', icon: Activity },          // KPI & health
  { key: 'extraction', label: 'Extraction', icon: FileSearch },    // parser/OCR + lineage (layers 1–4)
  { key: 'metadata', label: 'Metadata', icon: Layers },            // column semantics, PK/FK (layer 5)
  { key: 'eda', label: 'EDA', icon: GitBranch },                   // semantic + statistics + correlation (6–8)
  { key: 'graph', label: 'Knowledge Graph', icon: Network },       // graph + analytics (11–13)
  { key: 'confidence', label: 'Confidence', icon: Grid3x3 },       // per-layer heatmap
  { key: 'trust', label: 'Validation & Trust', icon: GaugeIcon },  // validation + AI trust (9)
  { key: 'governance', label: 'Governance & Ontology', icon: ShieldCheck }, // gate (10)
  { key: 'wiki', label: 'Wiki', icon: BookOpen },                  // explainability (14)
]

function band(score) {
  if (score == null) return 'apill'
  if (score >= 0.75) return 'pill-g'
  if (score >= 0.45) return 'pill-a'
  return 'inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-lg bg-coral/10 text-coral border border-coral/30'
}
function Field({ label, children }) {
  return <div className="flex flex-col gap-1"><label className="text-[10px] font-semibold uppercase tracking-wider text-t3">{label}</label>{children}</div>
}
function DbInput({ v, on, ph, type = 'text' }) {
  return <input type={type} value={v} placeholder={ph} onChange={(e) => on(e.target.value)}
    className="w-full bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-xs text-t1 outline-none focus:border-accent" />
}
// Per-source-only tabs show this hint when scope = All sources.
function RequireSource({ scope, what, children }) {
  if (!scope) return <EDAEmptyState message={`Select a specific source (top-right) to view ${what}.`} detail="This view is per-source; switch scope to 'All sources' for corpus-wide tabs." />
  return children
}

export default function SemanticOSPage() {
  // ingestion
  const [srcType, setSrcType] = useState('files')
  const [files, setFiles] = useState([])
  const [role, setRole] = useState('')
  const [domain, setDomain] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [report, setReport] = useState(null)
  const [dbForm, setDbForm] = useState({ engine: 'postgresql', host: 'localhost', port: '5432', dbname: '', user: '', password: '', path: '' })
  const [dbStatus, setDbStatus] = useState(null)
  // shell
  const [health, setHealth] = useState(null)
  const [tab, setTab] = useState('pipeline')
  const [scope, setScope] = useState('')          // '' = all sources; else source_id
  const [sources, setSources] = useState([])

  useEffect(() => { sioApi.health().then(setHealth).catch(() => setHealth(null)) }, [])
  const refreshSources = () => sioApi.sources().then((d) => setSources(d.sources || [])).catch(() => {})
  useEffect(() => { refreshSources() }, [])

  const setDb = (k, v) => setDbForm((p) => ({ ...p, [k]: v }))
  const dbPayload = () => ({ ...dbForm, port: dbForm.port ? Number(dbForm.port) : null, role, domain })

  async function testDb() {
    setBusy(true); setDbStatus({ tone: 'amber', msg: 'Testing connection…' })
    try {
      const r = await sioApi.dbTest(dbPayload())
      setDbStatus(r.ok ? { tone: 'gg', msg: `✓ Connected — ${r.table_count} table(s) (${r.dialect})` } : { tone: 'coral', msg: `Failed: ${r.error}` })
    } catch (e) { setDbStatus({ tone: 'coral', msg: e.message }) } finally { setBusy(false) }
  }
  async function runPipeline() {
    setBusy(true); setErr(null); setReport(null)
    try {
      let r
      if (srcType === 'database') r = await sioApi.dbConnect(dbPayload())
      else { if (!files.length) { setBusy(false); return } r = await sioApi.ingest(files, { role, domain }) }
      setReport(r)
      setScope(r.source_id || '')   // default scope to the run just completed → preserves the per-source loop
      setTab('pipeline')
      refreshSources()
    } catch (e) { setErr(e.message || 'Ingestion failed') } finally { setBusy(false) }
  }

  const summary = report?.summary || {}

  return (
    <div className="px-8 py-8 max-w-[1180px] mx-auto">
      {/* Header + scope selector */}
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-t1 flex items-center gap-2"><Boxes size={22} className="text-accent" /> Semantic Intelligence OS</h1>
          <p className="text-t2 text-xs mt-1">14-layer pipeline + observatory · governance mode: <span className="pill-b">{health?.governance_mode || 'offline'}</span></p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-t3">Scope</span>
          <select value={scope} onChange={(e) => setScope(e.target.value)}
            className="bg-card2 border border-dborder2 rounded-sm px-3 py-1.5 text-xs text-t1 outline-none focus:border-accent max-w-[260px]">
            <option value="">All sources (corpus)</option>
            {sources.map((s) => <option key={s.source_id} value={s.source_id}>{s.filename || s.source_id}</option>)}
          </select>
        </div>
      </div>

      {/* Ingest */}
      <div className="card mb-6">
        <div className="sect">Ingest a source</div>
        <div className="flex gap-1.5 mb-4">
          {[['files', 'Files', FileText], ['folder', 'Folder', Layers], ['database', 'Database', Boxes]].map(([k, label, Icon]) => (
            <button key={k} onClick={() => { setSrcType(k); setErr(null) }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-all ${srcType === k ? 'bg-accent text-white border-accent' : 'bg-transparent text-t3 border-dborder hover:bg-bg4'}`}>
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
        {srcType !== 'database' && (
          <div>
            <label className="block border-2 border-dashed border-dborder2 rounded-card py-7 text-center cursor-pointer hover:border-accent transition-colors">
              <UploadCloud size={22} className="text-accent mx-auto mb-2" />
              <div className="text-xs text-t1 font-medium">{files.length ? `${files.length} file(s) selected` : (srcType === 'folder' ? 'Click to choose a folder' : 'Click to choose file(s)')}</div>
              <div className="text-[10px] text-t3 mt-1">PDF · DOCX · TXT · MD · CSV · XLSX · JSON · HTML — multiple allowed</div>
              <input type="file" className="hidden" multiple accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls,.json,.html,.htm"
                {...(srcType === 'folder' ? { webkitdirectory: '', directory: '' } : {})}
                onChange={(e) => setFiles(Array.from(e.target.files || []))} />
            </label>
            {files.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3 max-h-24 overflow-y-auto">
                {files.slice(0, 40).map((f, i) => <span key={i} className="apill">{f.name}</span>)}
                {files.length > 40 && <span className="apill">+{files.length - 40} more</span>}
              </div>
            )}
          </div>
        )}
        {srcType === 'database' && (
          <div>
            <div className="grid md:grid-cols-3 gap-3 mb-3">
              <Field label="Engine">
                <select value={dbForm.engine} onChange={(e) => setDb('engine', e.target.value)}
                  className="w-full bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-xs outline-none focus:border-accent">
                  {DB_ENGINES.map((o) => <option key={o}>{o}</option>)}
                </select>
              </Field>
              {dbForm.engine === 'sqlite' ? (
                <Field label="SQLite file path"><DbInput v={dbForm.path} on={(x) => setDb('path', x)} ph="/path/to/db.sqlite" /></Field>
              ) : (
                <>
                  <Field label="Host"><DbInput v={dbForm.host} on={(x) => setDb('host', x)} ph="db.example.com" /></Field>
                  <Field label="Port"><DbInput v={dbForm.port} on={(x) => setDb('port', x)} ph="5432" /></Field>
                  <Field label="Database name"><DbInput v={dbForm.dbname} on={(x) => setDb('dbname', x)} ph="production_db" /></Field>
                  <Field label="Username"><DbInput v={dbForm.user} on={(x) => setDb('user', x)} ph="admin" /></Field>
                  <Field label="Password"><DbInput v={dbForm.password} on={(x) => setDb('password', x)} ph="••••••••" type="password" /></Field>
                </>
              )}
            </div>
            <button className="btn btn-sm" disabled={busy} onClick={testDb}>{busy ? 'Testing…' : 'Test connection'}</button>
            {dbStatus && <span className="ml-3 text-[11px]" style={{ color: dbStatus.tone === 'gg' ? '#16a34a' : dbStatus.tone === 'amber' ? '#d97706' : '#e11d48' }}>{dbStatus.msg}</span>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <input className="px-3 py-2 rounded-sm border border-dborder2 bg-card2 text-xs" placeholder="role (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
          <input className="px-3 py-2 rounded-sm border border-dborder2 bg-card2 text-xs" placeholder="domain (optional)" value={domain} onChange={(e) => setDomain(e.target.value)} />
          <button className="btn btn-teal" disabled={busy || (srcType !== 'database' && !files.length)} onClick={runPipeline}>
            {busy ? 'Running 14 layers…' : srcType === 'database' ? 'Connect & ingest' : 'Run pipeline'}
          </button>
        </div>
        {err && <div className="mt-3 text-xs text-coral flex items-center gap-2"><AlertTriangle size={13} /> {err}</div>}
        {report?.ingested_count > 1 && <div className="mt-2 text-[11px] text-gg">✓ Ingested {report.ingested_count} files into the shared knowledge graph.</div>}
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-all ${tab === key ? 'bg-accent text-white border-accent' : 'bg-transparent text-t3 border-dborder hover:bg-bg4'}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {tab === 'pipeline' && <PipelineTab report={report} summary={summary} band={band} />}
      {tab === 'overview' && <KPIHealth scope={scope} />}
      {tab === 'extraction' && <ExtractionQuality scope={scope} />}
      {tab === 'metadata' && <RequireSource scope={scope} what="metadata intelligence"><MetadataView sid={scope} /></RequireSource>}
      {tab === 'eda' && <EDATab scope={scope} />}
      {tab === 'graph' && <><GraphTrust scope={scope} /><KGAnalytics scope={scope} /></>}
      {tab === 'confidence' && <SemanticHeatmap scope={scope} />}
      {tab === 'trust' && <TrustTab scope={scope} />}
      {tab === 'governance' && <GovernanceTab scope={scope} />}
      {tab === 'wiki' && <WikiView />}
    </div>
  )
}

/* ---------- Pipeline (the 14-layer run view) ---------- */
const STEP_DEFS = [
  ['__upload', 'File Upload + Lineage'], ['extraction', 'Ingestion & Extraction'], ['normalization', 'Cleaning + Normalization'],
  ['chunking', 'Chunking + Segmentation'], ['metadata', 'Metadata Intelligence'], ['entity_relation', 'Entity + Relationship'],
  ['semantic_learning', 'Semantic Learning'], ['eda', 'EDA Intelligence'], ['validation', 'ML Validation & Accuracy'],
  ['governance', 'Ontology & Governance'], ['canonicalization', 'Canonicalization'], ['graph_construction', 'KG Construction'],
  ['graph_consistency', 'Graph Consistency'], ['wiki', 'Wiki + Explainability'],
]
function PipelineTab({ report, summary, band }) {
  if (!report) return <Panel title="Pipeline"><EDAEmptyState message="Run an ingestion to watch the 14 layers execute and see this run's summary." /></Panel>
  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <Tile label="Entities" value={summary.entities} />
        <Tile label="Relationships" value={summary.relationships} />
        <Tile label="Graph nodes" value={summary.graph?.graph_node_total} />
        <BandTile label="Trust score" v={summary.graph_trust_score} band={band} />
        <BandTile label="Ontology consistency" v={summary.ontology_consistency} band={band} />
      </div>
      <Panel title={`Layer execution · source ${report.source_id}`}>
        <div className="space-y-1.5">
          {STEP_DEFS.map(([key, name], i) => {
            const status = key === '__upload' ? 'ok' : report.stages?.[key]
            const ok = status === 'ok'
            return (
              <div key={key} className="flex items-center gap-3 py-2 px-3 rounded-sm bg-bg4/60 border border-dborder">
                <span className="w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center text-[10px] font-bold">{i + 1}</span>
                <span className="text-xs font-medium text-t1 flex-1">{name}</span>
                <span className={ok ? 'pill-g' : status ? band(0) : 'apill'}>{ok ? '✓ ok' : status || 'skipped'}</span>
              </div>
            )
          })}
        </div>
      </Panel>
    </div>
  )
}
function Tile({ label, value }) {
  return <div className="mcard"><div className="text-[10px] uppercase tracking-widest text-t3 mb-1">{label}</div><div className="text-xl font-bold text-t1">{value ?? '—'}</div></div>
}
function BandTile({ label, v, band }) {
  return <div className="mcard"><div className="text-[10px] uppercase tracking-widest text-t3 mb-1">{label}</div><div><span className={band(v)}>{v ?? '—'}</span></div></div>
}

/* ---------- EDA tab: Semantic (per-source) + Statistics + Correlation ---------- */
function EDATab({ scope }) {
  const [sub, setSub] = useState('Semantic')
  return (
    <div>
      <SubTabs tabs={['Semantic', 'Statistics', 'Correlation & Outliers']} active={sub} onChange={setSub} />
      {sub === 'Semantic' && <RequireSource scope={scope} what="per-source semantic EDA"><SemanticEDA sid={scope} /></RequireSource>}
      {sub === 'Statistics' && <DataQuality scope={scope} />}
      {sub === 'Correlation & Outliers' && <CorrelationOutliers scope={scope} />}
    </div>
  )
}
function SemanticEDA({ sid }) {
  const s = useFetch(() => sioApi.eda(sid), [sid])
  return (
    <Panel title="Semantic / graph EDA (this source)">
      <Body state={s}>
        {(d) => (
          <div>
            <StatTiles tiles={[
              { label: 'Nodes', value: d.graph_eda?.node_count, color: '#4f46e5' },
              { label: 'Edges', value: d.graph_eda?.edge_count, color: '#0d9488' },
              { label: 'Density', value: d.graph_eda?.density, color: '#d97706' },
              { label: 'Orphans', value: d.graph_eda?.orphan_node_count, color: '#e11d48' },
            ]} />
            <div className="grid md:grid-cols-2 gap-4 mt-4">
              <div><div className="text-[10px] text-t3 mb-1">Entity-type cluster map</div><Donut data={d.semantic_cluster_map} /></div>
              <div><div className="text-[10px] text-t3 mb-1">Relationship distribution</div><Bars data={d.relation_distribution} color="#0d9488" /></div>
              <div><div className="text-[10px] text-t3 mb-1">Confidence bands</div><Donut data={d.confidence_eda?.band_distribution} colors={['#16a34a', '#d97706', '#e11d48']} /></div>
              <div><div className="text-[10px] text-t3 mb-1">Semantic drift</div>
                <StatTiles tiles={[{ label: 'Drift signals', value: d.semantic_drift?.count, color: '#e11d48' }, { label: 'Avg confidence', value: d.confidence_eda?.avg_confidence, color: '#4f46e5' }]} /></div>
            </div>
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* ---------- Metadata (per-source) ---------- */
function MetadataView({ sid }) {
  const s = useFetch(() => sioApi.metadata(sid), [sid])
  return (
    <Panel title="Metadata intelligence">
      <Body state={s}>
        {(d) => !d.is_tabular ? <EDAEmptyState message="This source is non-tabular — metadata intelligence applies to spreadsheets / DB exports." /> : (
          <div>
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="pill-b">Class: {d.table_classification?.label} ({d.table_classification?.confidence})</span>
              <span className="pill-t">Rows: {d.row_count}</span>
              {(d.predicted_keys?.primary_key || []).map((k) => <span key={k.column} className="pill-g">PK: {k.column}</span>)}
              {(d.predicted_keys?.foreign_keys || []).map((k) => <span key={k.column} className="pill-a">FK: {k.column}</span>)}
            </div>
            <div className="text-[10px] text-t3 mb-1">Column semantic labels (confidence)</div>
            <ConfBars items={(d.columns || []).map((c) => ({ label: `${c.column}  ·  ${c.semantic_label} (${c.datatype})`, value: c.audit?.confidence?.score }))} height={340} />
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* ---------- Validation & Trust: per-source validation + AI trust center ---------- */
function TrustTab({ scope }) {
  return (
    <div>
      {scope ? <ValidationView sid={scope} /> : <Panel title="Validation (per-source)"><EDAEmptyState message="Select a specific source to see detailed P/R/F1 + calibration; the corpus AI Trust Center is below." /></Panel>}
      <AITrustCenter scope={scope} />
    </div>
  )
}
function ValidationView({ sid }) {
  const s = useFetch(() => sioApi.validation(sid), [sid])
  return (
    <Panel title="ML validation (this source)">
      <Body state={s}>
        {(d) => (
          <div>
            <div className="grid md:grid-cols-3 gap-4 mb-2">
              <div><div className="text-[10px] text-t3 mb-1">Graph trust</div><Gauge value={d.graph_trust_score} title="trust" /></div>
              <div><div className="text-[10px] text-t3 mb-1">Hallucination risk</div><Gauge value={d.hallucination_risk} title="risk" invert /></div>
              <div><div className="text-[10px] text-t3 mb-1">Calibration error</div><Gauge value={d.calibration_error} title="ECE" invert /></div>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div><div className="text-[10px] text-t3 mb-1">Entity metrics</div><Bars data={{ precision: d.entity_metrics?.precision, recall: d.entity_metrics?.recall, f1: d.entity_metrics?.f1 }} color="#4f46e5" /></div>
              <div><div className="text-[10px] text-t3 mb-1">Relationship metrics</div><Bars data={{ precision: d.relationship_metrics?.precision, recall: d.relationship_metrics?.recall, f1: d.relationship_metrics?.f1 }} color="#7c3aed" /></div>
            </div>
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* ---------- Governance & Ontology: per-source verdicts + global ontology ---------- */
function GovernanceTab({ scope }) {
  return (
    <div>
      {scope ? <GovernanceView sid={scope} /> : <Panel title="Governance verdicts (per-source)"><EDAEmptyState message="Select a specific source to see its accept/review/reject verdicts; the ontology is shown below." /></Panel>}
      <OntologyView />
    </div>
  )
}
function GovernanceView({ sid }) {
  const s = useFetch(() => sioApi.governance(sid), [sid])
  return (
    <Panel title="Governance verdicts (this source)">
      <Body state={s}>
        {(d) => {
          const vs = d.verdicts_summary || {}
          const rejected = (d.accepted_relationships || []).filter((r) => r.governance?.action === 'reject')
          return (
            <div className="grid md:grid-cols-2 gap-4">
              <div><div className="text-[10px] text-t3 mb-1">Verdict distribution</div>
                <Donut data={{ auto_accept: vs.auto_accept, review_required: vs.review_required, reject: vs.reject }} colors={['#16a34a', '#d97706', '#e11d48']} /></div>
              <div><div className="text-[10px] text-t3 mb-1">Ontology consistency</div><Gauge value={d.ontology_consistency} title="consistency" /></div>
              <div className="md:col-span-2">
                <div className="text-[10px] text-t3 mb-1">Rejected / violating relationships ({rejected.length})</div>
                <div className="space-y-1" style={{ maxHeight: 220, overflowY: 'auto' }}>
                  {!rejected.length && <div className="text-[11px] text-t3">No ontology violations.</div>}
                  {rejected.slice(0, 50).map((r, i) => (
                    <div key={i} className="text-[10px] bg-coral/5 border border-coral/20 rounded px-2 py-1">
                      <span className="font-medium text-t1">{r.source}</span><span className="text-coral mx-1">[{r.relation}]</span>
                      <span className="font-medium text-t1">{r.target}</span><span className="text-t3 ml-2">— {r.governance?.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )
        }}
      </Body>
    </Panel>
  )
}
function OntologyView() {
  const s = useFetch(() => sioApi.ontology(), [])
  return (
    <Panel title="Ontology (taxonomy + relationship constraints)">
      <Body state={s}>
        {(d) => (
          <div>
            <div className="text-[10px] text-t3 mb-1">Entity taxonomy</div>
            <TaxonomyGraph taxonomy={d.taxonomy} />
            <div className="text-[10px] text-t3 mt-3 mb-1">Relationship constraints</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(d.relationship_constraints || {}).map(([pred, pairs]) => (
                <div key={pred} className="mcard">
                  <div className="text-[11px] font-semibold text-accent mb-1">{pred}</div>
                  <div className="text-[10px] text-t2">{pairs === 'ANY' ? 'any → any' : pairs.map((p, i) => <div key={i}>{p[0]} → {p[1]}</div>)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Body>
    </Panel>
  )
}

/* ---------- Wiki (global) ---------- */
function WikiView() {
  const s = useFetch(() => sioApi.wikiPages(), [])
  const [openPage, setOpenPage] = useState(null)
  return (
    <Panel title="Wiki + explainability">
      <Body state={s}>
        {(d) => {
          const pages = Object.entries(d.pages || {})
          return (
            <div>
              {!pages.length && <div className="text-t3 text-xs">No wiki pages yet.</div>}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {pages.map(([cid, p]) => (
                  <button key={cid} onClick={() => sioApi.wikiPage(cid).then(setOpenPage)} className="text-left mcard hover:border-accent">
                    <div className="text-xs font-semibold text-t1 truncate">{p.title}</div><div className="text-[10px] text-t3">{p.type}</div>
                  </button>
                ))}
              </div>
              {openPage && (
                <div className="mt-4 p-4 rounded-card border border-accent/30 bg-accent/5">
                  <div className="text-sm font-bold text-t1">{openPage.title}</div>
                  <p className="text-xs text-t2 mt-1">{openPage.summary}</p>
                  <div className="text-[10px] uppercase tracking-widest text-t3 mt-3 mb-1">Key facts</div>
                  <ul className="text-xs text-t2 list-disc pl-4 space-y-0.5">
                    {(openPage.key_facts || []).slice(0, 8).map((f, i) => <li key={i}>{f.fact} <span className="text-t3">({f.confidence})</span></li>)}
                  </ul>
                  <div className="text-[10px] uppercase tracking-widest text-t3 mt-3 mb-1">Confidence explanation</div>
                  <p className="text-xs text-t2">{openPage.explanations?.confidence}</p>
                </div>
              )}
            </div>
          )
        }}
      </Body>
    </Panel>
  )
}
