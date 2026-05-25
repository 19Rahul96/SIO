const BASE = import.meta.env.VITE_API_URL || '/api'

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = body.detail || res.statusText
    const err = new Error(typeof detail === 'string' ? detail : detail.message || 'Request failed')
    err.status = res.status
    err.detail = detail
    throw err
  }
  return res.json()
}

const api = {
  upload: (file, ctx = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    if (ctx.role) fd.append('role', ctx.role)
    if (ctx.domain) fd.append('domain', ctx.domain)
    if (ctx.force) fd.append('force', 'true')
    return req('/upload', { method: 'POST', body: fd })
  },

  getStatus: () => req('/status'),
  getFileStatus: (id) => req(`/status/${id}`),

  scrape: (url, ctx = {}) =>
    req('/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        role: ctx.role || null,
        domain: ctx.domain || null,
        force: Boolean(ctx.force),
      }),
    }),

  dbConnect: (payload) =>
    req('/db/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  dbTest: (payload) =>
    req('/db/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  analyse: (prompt, fileIds = []) =>
    req('/analyse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, file_ids: fileIds }),
    }),

  query: (prompt, fileIds = [], slmId = null) =>
    req('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, file_ids: fileIds, slm_id: slmId }),
    }),

  getGraph: (fileIds = []) => {
    const qs = fileIds.length ? `?file_ids=${fileIds.join(',')}` : ''
    return req(`/graph${qs}`)
  },

  getCanonicalGraph: (fileIds = []) => {
    const qs = fileIds.length ? `?file_ids=${fileIds.join(',')}` : ''
    return req(`/graph-canonical${qs}`)
  },

  getGraphSummary: (fileIds = []) => {
    const qs = fileIds.length ? `?file_ids=${fileIds.join(',')}` : ''
    return req(`/graph/summary${qs}`)
  },

  getWikiPages: ({ q = '', fileIds = [], limit = 100 } = {}) => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (fileIds?.length) params.set('file_ids', fileIds.join(','))
    if (limit) params.set('limit', String(limit))
    const qs = params.toString()
    return req(`/wiki/pages${qs ? `?${qs}` : ''}`)
  },

  getWikiPage: (canonicalId) => req(`/wiki/page/${encodeURIComponent(canonicalId)}`),

  getWikiReviews: ({ status = 'pending', limit = 100 } = {}) => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (limit) params.set('limit', String(limit))
    return req(`/wiki/reviews?${params.toString()}`)
  },

  submitWikiReview: (reviewId, decision, decidedBy = 'ui') =>
    req(`/wiki/review/${encodeURIComponent(reviewId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, decided_by: decidedBy }),
    }),

  finalRun: (prompt, slmId, model, fileIds = []) =>
    req('/final-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, slm_id: slmId, model, file_ids: fileIds }),
    }),

  retryFile: (fileId) =>
    req(`/retry/${fileId}`, { method: 'POST' }),

  getStats: () => req('/stats'),
  getQualityMetrics: () => req('/quality/metrics'),
  getEdaVisuals: (fileIds = []) => {
    const qs = fileIds.length ? `?file_ids=${fileIds.join(',')}` : ''
    return req(`/eda/visuals${qs}`)
  },
  getEdaDashboard: ({ fileIds = [], dbIds = [] } = {}) => {
    const params = new URLSearchParams()
    if (fileIds.length) params.set('file_ids', fileIds.join(','))
    if (dbIds.length) params.set('db_ids', dbIds.join(','))
    const qs = params.toString()
    return req(`/eda/dashboard${qs ? `?${qs}` : ''}`)
  },
  getMlMetrics: () => req('/metrics/aggregate'),

  getIngestionReport: () => req('/ingestion-report'),
}

export default api
