import { useEffect, useState } from 'react'
import api from '../services/api'

const TYPE_COLOR = {
  organization: { bg: 'rgba(124,58,237,.10)', color: '#7c3aed', border: 'rgba(124,58,237,.30)' },
  value:        { bg: 'rgba(217,119,6,.10)',  color: '#d97706', border: 'rgba(217,119,6,.30)' },
  time:         { bg: 'rgba(13,148,136,.10)', color: '#0d9488', border: 'rgba(13,148,136,.30)' },
  entity:       { bg: 'rgba(37,99,235,.10)',  color: '#2563eb', border: 'rgba(37,99,235,.30)' },
}
function typeChip(type) {
  const c = TYPE_COLOR[type] || TYPE_COLOR.entity
  return (
    <span
      className="inline-flex items-center text-[9px] font-semibold px-1.5 py-0.5 rounded-md ml-1.5"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}
    >
      {type}
    </span>
  )
}

function nodeColor(node) {
  const key = (node.entity_type || node.type || '').toLowerCase()
  if (key.includes('org') || key.includes('organization')) return '#7c3aed'
  if (key.includes('time') || key.includes('date')) return '#0d9488'
  if (key.includes('money') || key.includes('value')) return '#d97706'
  return '#2563eb'
}

function stableHash(input) {
  const str = String(input || '')
  let h = 2166136261
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return Math.abs(h >>> 0)
}

function ellipsis(text, max = 20) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

function buildGraphCanvas(graph, maxNodes = 80) {
  const width = 980
  const height = 560
  const pad = 36
  const centerX = width / 2
  const centerY = height / 2

  const degree = {}
  graph.nodes.forEach((n) => { degree[n.id] = 0 })
  graph.edges.forEach((e) => {
    if (degree[e.source] != null) degree[e.source] += 1
    if (degree[e.target] != null) degree[e.target] += 1
  })

  const ranked = [...graph.nodes].sort((a, b) => (degree[b.id] || 0) - (degree[a.id] || 0))
  const selectedNodes = ranked.slice(0, maxNodes)
  const selectedIds = new Set(selectedNodes.map((n) => n.id))
  const selectedEdges = graph.edges.filter((e) => selectedIds.has(e.source) && selectedIds.has(e.target)).slice(0, 220)

  if (selectedNodes.length === 0) {
    return { width, height, nodes: [], edges: [], pos: {}, totalNodes: graph.nodes.length, totalEdges: graph.edges.length }
  }

  // Build adjacency index for attractive forces on connected nodes.
  const adjacency = {}
  selectedNodes.forEach((n) => { adjacency[n.id] = new Set() })
  selectedEdges.forEach((e) => {
    if (adjacency[e.source]) adjacency[e.source].add(e.target)
    if (adjacency[e.target]) adjacency[e.target].add(e.source)
  })

  // Deterministic initialization spreads nodes in distinct places across runs.
  const seeded = selectedNodes.map((n) => {
    const h = stableHash(n.id || n.label)
    const a = (h % 360) * (Math.PI / 180)
    const r = 70 + (h % 210)
    const x = centerX + Math.cos(a) * r
    const y = centerY + Math.sin(a) * r
    return {
      ...n,
      x,
      y,
      vx: 0,
      vy: 0,
    }
  })

  const byId = {}
  seeded.forEach((n) => { byId[n.id] = n })

  // Lightweight force simulation: repulsion + spring edges + center gravity.
  const iterations = 140
  const repulsion = 4200
  const springK = 0.018
  const restLen = 92
  const gravity = 0.0032
  const damping = 0.86

  for (let iter = 0; iter < iterations; iter += 1) {
    for (let i = 0; i < seeded.length; i += 1) {
      const a = seeded[i]

      for (let j = i + 1; j < seeded.length; j += 1) {
        const b = seeded[j]
        let dx = b.x - a.x
        let dy = b.y - a.y
        let d2 = dx * dx + dy * dy
        if (d2 < 25) d2 = 25
        const d = Math.sqrt(d2)
        if (d === 0) continue

        const f = repulsion / d2
        const fx = (dx / d) * f
        const fy = (dy / d) * f
        a.vx -= fx
        a.vy -= fy
        b.vx += fx
        b.vy += fy
      }
    }

    for (let i = 0; i < selectedEdges.length; i += 1) {
      const e = selectedEdges[i]
      const s = byId[e.source]
      const t = byId[e.target]
      if (!s || !t) continue

      const dx = t.x - s.x
      const dy = t.y - s.y
      const d = Math.max(1, Math.sqrt(dx * dx + dy * dy))
      const stretch = d - restLen
      const force = springK * stretch
      const fx = (dx / d) * force
      const fy = (dy / d) * force

      s.vx += fx
      s.vy += fy
      t.vx -= fx
      t.vy -= fy
    }

    for (let i = 0; i < seeded.length; i += 1) {
      const n = seeded[i]
      n.vx += (centerX - n.x) * gravity
      n.vy += (centerY - n.y) * gravity

      n.vx *= damping
      n.vy *= damping

      n.x += n.vx
      n.y += n.vy

      n.x = Math.max(pad, Math.min(width - pad, n.x))
      n.y = Math.max(pad, Math.min(height - pad, n.y))
    }
  }

  const maxDeg = Math.max(1, ...selectedNodes.map((n) => degree[n.id] || 0))
  const placedNodes = seeded.map((n) => {
    const r = 4 + Math.round(((degree[n.id] || 0) / maxDeg) * 8)
    return { ...n, r, labelShort: ellipsis(n.label || '', 22) }
  })

  const pos = {}
  placedNodes.forEach((n) => { pos[n.id] = n })

  return { width, height, nodes: placedNodes, edges: selectedEdges, pos, totalNodes: graph.nodes.length, totalEdges: graph.edges.length }
}

export default function GraphRAGViewer({ fileIds = [], onClose }) {
  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('graph') // graph | stats | nodes | edges

  useEffect(() => {
    if (!fileIds.length) {
      setGraph({ nodes: [], edges: [], stats: { node_count: 0, edge_count: 0, density: 0 } })
      setLoading(false)
      return
    }

    setLoading(true)
    api.getCanonicalGraph(fileIds)
      .then((canonical) => {
        if ((canonical?.nodes?.length || 0) > 0 || (canonical?.edges?.length || 0) > 0) {
          return canonical
        }
        // Fallback to per-file graph if canonical artifacts are not yet available.
        return api.getGraph(fileIds)
      })
      .then(setGraph)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [fileIds.join(',')])

  const density = graph
    ? graph.stats.node_count > 1
      ? (graph.stats.edge_count / (graph.stats.node_count * (graph.stats.node_count - 1))).toFixed(4)
      : '—'
    : '—'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(10,12,22,.72)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="bg-card2 border border-dborder rounded-card flex flex-col"
        style={{ width: '860px', maxWidth: '95vw', maxHeight: '88vh' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-dborder flex-shrink-0">
          <div>
            <div className="font-sora text-[15px] font-semibold text-t1">GraphRAG Canonical Knowledge Graph</div>
            <div className="text-[11px] text-t3 mt-0.5">
              {fileIds.length > 0 ? `${fileIds.length} uploaded file${fileIds.length > 1 ? 's' : ''}` : 'No uploaded files selected'} · canonical entities, merged aliases &amp; wiki-aligned relations
            </div>
          </div>
          <button
            className="btn btn-sm"
            onClick={onClose}
            style={{ minWidth: 32, padding: '4px 10px' }}
          >
            ✕ Close
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-dborder flex-shrink-0">
          {[['graph', 'Knowledge Graph'], ['stats', 'Graph Stats'], ['nodes', `Nodes${graph ? ` (${graph.stats.node_count})` : ''}`], ['edges', `Edges${graph ? ` (${graph.stats.edge_count})` : ''}`]].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="px-5 py-2.5 text-[11px] font-medium transition-colors border-b-2"
              style={{
                borderBottomColor: tab === key ? 'var(--color-accent, #4f46e5)' : 'transparent',
                color: tab === key ? '#4f46e5' : 'var(--color-t2, #5a6077)',
                background: 'transparent',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && (
            <div className="flex items-center justify-center h-40 text-t3 text-[12px]">
              <span className="inline-block w-2 h-2 rounded-full bg-accent mr-2 animate-pulse" />
              Loading graph…
            </div>
          )}
          {error && (
            <div className="text-coral text-[12px] py-8 text-center">Error: {error}</div>
          )}
          {!loading && !error && graph && (
            <>
              {tab === 'graph' && (
                <div>
                  {!fileIds.length ? (
                    <p className="text-t3 text-[12px] text-center py-10">No completed uploaded files are selected yet.</p>
                  ) : graph.nodes.length === 0 ? (
                    <p className="text-t3 text-[12px] text-center py-10">No graph data found for selected uploads.</p>
                  ) : (
                    (() => {
                      const canvas = buildGraphCanvas(graph)
                      return (
                        <div className="border border-dborder rounded-card bg-bg3 overflow-hidden">
                          <div className="flex items-center justify-between px-3.5 py-2 border-b border-dborder text-[10px] text-t3">
                            <span>Visualized subset: {canvas.nodes.length} / {canvas.totalNodes} nodes · {canvas.edges.length} / {canvas.totalEdges} edges</span>
                            <span>Force-directed layout with entity labels</span>
                          </div>
                          <svg viewBox={`0 0 ${canvas.width} ${canvas.height}`} className="w-full h-[500px] block">
                            <defs>
                              <radialGradient id="graphGlow" cx="50%" cy="50%" r="50%">
                                <stop offset="0%" stopColor="#eef2ff" stopOpacity="0.55" />
                                <stop offset="100%" stopColor="#eef2ff" stopOpacity="0" />
                              </radialGradient>
                            </defs>
                            <rect x="0" y="0" width={canvas.width} height={canvas.height} fill="url(#graphGlow)" />

                            {canvas.edges.map((e, i) => {
                              const s = canvas.pos[e.source]
                              const t = canvas.pos[e.target]
                              if (!s || !t) return null
                              return (
                                <line
                                  key={`${e.source}-${e.target}-${i}`}
                                  x1={s.x}
                                  y1={s.y}
                                  x2={t.x}
                                  y2={t.y}
                                  stroke="#94a3b8"
                                    strokeOpacity="0.44"
                                    strokeWidth="1.1"
                                >
                                  <title>{`${s.label} - ${e.relation} - ${t.label}`}</title>
                                </line>
                              )
                            })}

                            {canvas.nodes.map((n) => (
                              <g key={n.id}>
                                <circle cx={n.x} cy={n.y} r={n.r + 5} fill={nodeColor(n)} opacity="0.10" />
                                <circle cx={n.x} cy={n.y} r={n.r} fill={nodeColor(n)} fillOpacity="0.9" stroke="#f8fafc" strokeWidth="1.2">
                                  <title>{`${n.label} (${n.entity_type || n.type || 'entity'})`}</title>
                                </circle>
                                <rect
                                  x={n.x + n.r + 4}
                                  y={n.y - 7}
                                  width={Math.max(20, (n.labelShort?.length || 0) * 6.2)}
                                  height="14"
                                  rx="4"
                                  fill="rgba(248,250,252,.9)"
                                  stroke="rgba(148,163,184,.45)"
                                />
                                <text
                                  x={n.x + n.r + 8}
                                  y={n.y + 3}
                                  fontSize="9"
                                  fill="#334155"
                                  style={{ userSelect: 'none' }}
                                >
                                  {n.labelShort}
                                </text>
                              </g>
                            ))}
                          </svg>
                        </div>
                      )
                    })()
                  )}
                </div>
              )}

              {tab === 'stats' && (
                <div className="space-y-5">
                  {/* Stat cards */}
                  <div className="grid grid-cols-4 gap-3">
                    {[
                      { label: 'Nodes', value: graph.stats.node_count, color: '#4f46e5' },
                      { label: 'Edges', value: graph.stats.edge_count, color: '#0d9488' },
                      { label: 'Graph Density', value: graph.stats.density ?? density, color: '#d97706' },
                      { label: 'Files', value: fileIds.length || '—', color: '#7c3aed' },
                    ].map((s) => (
                      <div key={s.label} className="card text-center py-5">
                        <div className="font-sora text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
                        <div className="text-[10px] text-t3 mt-1 uppercase tracking-widest">{s.label}</div>
                      </div>
                    ))}
                  </div>

                  {/* Entity type breakdown */}
                  <div>
                    <div className="sect">Entity type breakdown</div>
                    {(() => {
                      const counts = {}
                      graph.nodes.forEach((n) => {
                        const t = n.entity_type || n.type || 'ENTITY'
                        counts[t] = (counts[t] || 0) + 1
                      })
                      const total = graph.nodes.length || 1
                      return Object.entries(counts)
                        .sort((a, b) => b[1] - a[1])
                        .map(([type, count]) => (
                          <div key={type} className="mb-2">
                            <div className="flex justify-between text-[11px] text-t2 mb-1">
                              <span>{type}</span>
                              <span>{count} ({Math.round(count / total * 100)}%)</span>
                            </div>
                            <div className="prog-bar">
                              <div className="prog-fill" style={{ width: `${count / total * 100}%` }} />
                            </div>
                          </div>
                        ))
                    })()}
                  </div>

                  {/* Relation type breakdown */}
                  <div>
                    <div className="sect">Relationship type breakdown</div>
                    {(() => {
                      const counts = {}
                      graph.edges.forEach((e) => {
                        const r = e.relation || 'related_to'
                        counts[r] = (counts[r] || 0) + 1
                      })
                      const total = graph.edges.length || 1
                      return Object.entries(counts)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 10)
                        .map(([rel, count]) => (
                          <div key={rel} className="mb-2">
                            <div className="flex justify-between text-[11px] text-t2 mb-1">
                              <span>{rel}</span><span>{count}</span>
                            </div>
                            <div className="prog-bar">
                              <div className="prog-fill" style={{ width: `${count / total * 100}%`, background: '#0d9488' }} />
                            </div>
                          </div>
                        ))
                    })()}
                  </div>
                </div>
              )}

              {tab === 'nodes' && (
                <div>
                  {graph.nodes.length === 0 ? (
                    <p className="text-t3 text-[12px] text-center py-10">No entities found in selected files.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {graph.nodes.map((n) => (
                        <div key={n.id} className="flex items-center gap-2.5 px-3 py-2 bg-bg3 border border-dborder rounded-sm">
                          <span className="text-[10px] font-mono text-t3 w-16 flex-shrink-0">{n.id}</span>
                          <span className="text-[12px] text-t1 font-medium flex-1 truncate">{n.label}</span>
                          {typeChip(n.entity_type || n.type)}
                          {n.chunk_idx != null && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: 'rgba(79,70,229,.10)', color: '#4f46e5', border: '1px solid rgba(79,70,229,.25)', flexShrink: 0 }}>
                              chunk {n.chunk_idx}
                            </span>
                          )}
                          {n.file_id && (
                            <span className="text-[9px] text-t3 font-mono flex-shrink-0">{n.file_id.slice(0, 8)}…</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'edges' && (
                <div>
                  {graph.edges.length === 0 ? (
                    <p className="text-t3 text-[12px] text-center py-10">No relationships found in selected files.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {graph.edges.map((e, i) => (
                        <div key={i} className="px-3 py-2 bg-bg3 border border-dborder rounded-sm">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[11px] font-medium text-t1">{e.source}</span>
                            <span className="text-[9px] px-2 py-0.5 rounded-md font-semibold" style={{ background: 'rgba(13,148,136,.12)', color: '#0d9488', border: '1px solid rgba(13,148,136,.3)' }}>
                              {e.relation}
                            </span>
                            <span className="text-[11px] font-medium text-t1">{e.target}</span>
                            {e.chunk_idx != null && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: 'rgba(79,70,229,.10)', color: '#4f46e5', border: '1px solid rgba(79,70,229,.25)', marginLeft: 'auto', flexShrink: 0 }}>
                                chunk {e.chunk_idx}
                              </span>
                            )}
                            {e.file_id && (
                              <span className="text-[9px] text-t3 font-mono flex-shrink-0">{e.file_id.slice(0, 8)}…</span>
                            )}
                          </div>
                          {e.context && (
                            <div className="text-[10px] text-t3 mt-1 truncate italic">"{e.context}"</div>
                          )}
                          {e.chunk_preview && (
                            <div className="text-[10px] text-t3 mt-0.5 truncate">
                              <span className="font-semibold not-italic">Source: </span>"{e.chunk_preview}…"
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
