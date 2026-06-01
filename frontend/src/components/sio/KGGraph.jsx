import { useMemo, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'

// Entity-type palette (reuses the color language from GraphRAGViewer).
export const TYPE_COLORS = {
  organization: '#7c3aed',
  person: '#2563eb',
  location: '#0d9488',
  monetary: '#d97706',
  temporal: '#16a34a',
  value: '#d97706',
  concept: '#64748b',
}
const DEFAULT_COLOR = '#94a3b8'

export function typeColor(t) {
  const k = (t || '').toLowerCase()
  return TYPE_COLORS[k] || DEFAULT_COLOR
}

function edgeColor(conf) {
  if (conf >= 0.75) return '#16a34a'
  if (conf >= 0.45) return '#d97706'
  return '#e11d48'
}

// Interactive Neo4j-style knowledge graph: drag, zoom, pan, click-to-inspect.
// Large graphs are capped to the top-degree subgraph to stay responsive.
export default function KGGraph({ nodes = [], edges = [], height = 520, maxNodes = 120 }) {
  const [selected, setSelected] = useState(null)

  const { view, shown, total } = useMemo(() => {
    const degree = {}
    nodes.forEach((n) => { degree[n.canonical_id] = 0 })
    edges.forEach((e) => {
      if (degree[e.source] != null) degree[e.source] += 1
      if (degree[e.target] != null) degree[e.target] += 1
    })
    const ranked = [...nodes].sort((a, b) => (degree[b.canonical_id] || 0) - (degree[a.canonical_id] || 0))
    const keep = ranked.slice(0, maxNodes)
    const keepIds = new Set(keep.map((n) => n.canonical_id))
    const keepEdges = edges.filter((e) => keepIds.has(e.source) && keepIds.has(e.target))
    return { view: { nodes: keep, edges: keepEdges }, shown: keep.length, total: nodes.length }
  }, [nodes, edges, maxNodes])

  const elements = useMemo(() => {
    const nodeIds = new Set(view.nodes.map((n) => n.canonical_id))
    const els = view.nodes.map((n) => ({
      data: {
        id: n.canonical_id,
        label: n.label,
        etype: n.entity_type,
        color: typeColor(n.entity_type),
        aliases: (n.aliases || []).join(', '),
        sources: (n.provenance || []).length,
      },
    }))
    view.edges.forEach((e) => {
      if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) return
      els.push({
        data: {
          id: e.edge_id,
          source: e.source,
          target: e.target,
          label: e.relation,
          conf: e.confidence,
          color: edgeColor(e.confidence),
          width: 1 + (e.confidence || 0.4) * 4,
          suppressed: e.suppressed ? 1 : 0,
        },
      })
    })
    return els
  }, [view])

  const stylesheet = [
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'background-color': 'data(color)',
        color: '#1a1d2e',
        'font-size': 9,
        'font-family': 'Sora, sans-serif',
        'text-valign': 'bottom',
        'text-margin-y': 3,
        width: 18,
        height: 18,
        'border-width': 2,
        'border-color': '#ffffff',
        'overlay-opacity': 0,
      },
    },
    { selector: 'node:selected', style: { 'border-color': '#4f46e5', 'border-width': 3, width: 26, height: 26 } },
    {
      selector: 'edge',
      style: {
        width: 'data(width)',
        label: 'data(label)',
        'font-size': 7,
        color: '#5a6280',
        'line-color': 'data(color)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': 'data(color)',
        'curve-style': 'bezier',
        'text-rotation': 'autorotate',
        opacity: 0.85,
      },
    },
    { selector: 'edge[suppressed = 1]', style: { 'line-style': 'dashed', opacity: 0.35 } },
  ]

  if (!nodes.length) {
    return <div className="text-[11px] text-t3 py-10 text-center">No graph yet — run the pipeline on a source.</div>
  }

  const legend = Object.entries(TYPE_COLORS)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-3">
      <div className="border border-dborder rounded-card bg-bg3 overflow-hidden relative" style={{ height }}>
        {shown < total && (
          <div className="absolute bottom-2 right-3 z-10 text-[9px] text-t3 bg-white/80 px-1.5 py-0.5 rounded">
            showing top {shown} of {total} nodes
          </div>
        )}
        <div className="absolute top-2 left-3 z-10 flex flex-wrap gap-2 text-[9px]">
          {legend.map(([t, c]) => (
            <span key={t} className="flex items-center gap-1 bg-white/80 px-1.5 py-0.5 rounded">
              <span className="w-2 h-2 rounded-full" style={{ background: c }} /> {t}
            </span>
          ))}
        </div>
        <CytoscapeComponent
          elements={elements}
          layout={{ name: 'cose', animate: true, idealEdgeLength: 90, nodeRepulsion: 8000, padding: 30 }}
          style={{ width: '100%', height: '100%' }}
          stylesheet={stylesheet}
          minZoom={0.2}
          maxZoom={3}
          cy={(cy) => {
            cy.removeAllListeners()
            cy.on('tap', 'node', (evt) => {
              const d = evt.target.data()
              const incident = cy.edges().filter((e) => e.data('source') === d.id || e.data('target') === d.id)
              setSelected({
                ...d,
                relations: incident.map((e) => ({
                  rel: e.data('label'),
                  conf: e.data('conf'),
                  other: e.data('source') === d.id ? cy.getElementById(e.data('target')).data('label') : cy.getElementById(e.data('source')).data('label'),
                  dir: e.data('source') === d.id ? '→' : '←',
                })),
              })
            })
            cy.on('tap', (evt) => { if (evt.target === cy) setSelected(null) })
          }}
        />
      </div>

      {/* Inspector */}
      <div className="border border-dborder rounded-card bg-card2 p-3 overflow-y-auto" style={{ height }}>
        <div className="sect">Inspector</div>
        {!selected ? (
          <div className="text-[11px] text-t3">Click a node to inspect its entity, type, aliases and relationships.</div>
        ) : (
          <div>
            <div className="text-sm font-bold text-t1">{selected.label}</div>
            <span className="apill mt-1 inline-block" style={{ background: `${selected.color}1a`, color: selected.color, borderColor: `${selected.color}55` }}>
              {selected.etype}
            </span>
            {selected.aliases && (
              <div className="mt-2 text-[10px] text-t2"><span className="text-t3 uppercase tracking-wider">Aliases:</span> {selected.aliases}</div>
            )}
            <div className="mt-1 text-[10px] text-t2"><span className="text-t3 uppercase tracking-wider">Sources:</span> {selected.sources}</div>
            <div className="mt-3 text-[10px] uppercase tracking-widest text-t3 mb-1">Relationships ({selected.relations.length})</div>
            <div className="space-y-1">
              {selected.relations.slice(0, 30).map((r, i) => (
                <div key={i} className="flex items-center justify-between gap-2 text-[10px] bg-bg4 rounded px-2 py-1">
                  <span className="truncate">{r.dir} {r.rel} <span className="text-t1 font-medium">{r.other}</span></span>
                  <span style={{ color: edgeColor(r.conf) }}>{r.conf}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
