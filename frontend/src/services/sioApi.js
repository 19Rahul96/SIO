// Client for the Semantic Intelligence OS (14-step pipeline) backend.
// Routed through the Vite `/sio` proxy -> http://127.0.0.1:8020 (see vite.config.js),
// kept separate from the legacy `/api` client so both backends coexist.
const SIO_BASE = import.meta.env.VITE_SIO_API_URL || '/sio'

async function req(path, opts = {}) {
  const res = await fetch(`${SIO_BASE}${path}`, opts)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = body.detail || res.statusText
    const err = new Error(typeof detail === 'string' ? detail : 'Request failed')
    err.status = res.status
    throw err
  }
  return res.json()
}

const sioApi = {
  health: () => req('/health'),

  // Ingest one or many files (also used for folder uploads).
  ingest: (files, ctx = {}) => {
    const fd = new FormData()
    const list = Array.isArray(files) ? files : [files]
    list.forEach((f) => fd.append('files', f))
    if (ctx.role) fd.append('role', ctx.role)
    if (ctx.domain) fd.append('domain', ctx.domain)
    return req('/ingest', { method: 'POST', body: fd })
  },

  dbTest: (payload) =>
    req('/db/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  dbConnect: (payload) =>
    req('/ingest/database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  runReport: (sid) => req(`/run/${sid}`),
  lineage: (sid) => req(`/lineage/${sid}`),
  metadata: (sid) => req(`/metadata/${sid}`),
  eda: (sid) => req(`/eda/${sid}`),
  validation: (sid) => req(`/validation/${sid}`),
  governance: (sid) => req(`/governance/${sid}`),

  ontology: () => req('/ontology'),
  graph: () => req('/graph'),
  graphConsistency: () => req('/graph/consistency'),
  wikiPages: () => req('/wiki/pages'),
  wikiPage: (cid) => req(`/wiki/page/${cid}`),

  // Sources list (for the scope selector)
  sources: () => req('/sources'),

  // Observatory aggregate endpoints — pass a sourceId to scope to one source, '' for all.
  edaSummary: (sid = '') => req(`/eda/summary${qs(sid)}`),
  edaColumns: (sid = '') => req(`/eda/columns${qs(sid)}`),
  edaValidation: (sid = '') => req(`/eda/validation${qs(sid)}`),
  edaCorrelation: (sid = '') => req(`/eda/correlation${qs(sid)}`),
  edaOutliers: (sid = '') => req(`/eda/outliers${qs(sid)}`),
  edaConfidence: (sid = '') => req(`/eda/confidence${qs(sid)}`),
  edaExtraction: (sid = '') => req(`/eda/extraction${qs(sid)}`),
  graphStats: (sid = '') => req(`/graph/stats${qs(sid)}`),
  graphEntities: (filter = '', sid = '') =>
    req(`/graph/entities${qs(sid, filter ? { filter } : {})}`),
  graphRelationships: (sid = '') => req(`/graph/relationships${qs(sid)}`),
  metricsAggregate: (sid = '') => req(`/metrics/aggregate${qs(sid)}`),
}

// Build a query string from an optional source_id + extra params.
function qs(sid, extra = {}) {
  const params = { ...extra }
  if (sid) params.source_id = sid
  const s = new URLSearchParams(params).toString()
  return s ? `?${s}` : ''
}

export default sioApi
