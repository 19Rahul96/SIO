import CytoscapeComponent from 'react-cytoscapejs'

export default function CytoscapePanel({ chart }) {
  const data = chart?.data || {}
  const nodes = data.nodes || []
  const edges = data.edges || []
  const elements = [
    ...nodes.map((n) => ({ data: { id: String(n.id), label: n.label || n.id } })),
    ...edges.map((e, idx) => ({ data: { id: `${e.source}-${e.target}-${idx}`, source: String(e.source), target: String(e.target), label: e.label || '' } })),
  ]

  if (!elements.length) {
    return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No graph data available.'}</div>
  }

  return (
    <div style={{ width: '100%', height: 360 }}>
      <CytoscapeComponent
        elements={elements}
        layout={{ name: 'cose', animate: false }}
        style={{ width: '100%', height: '100%' }}
        stylesheet={[
          { selector: 'node', style: { label: 'data(label)', 'font-size': 10, 'background-color': '#2563eb', color: '#1f2937' } },
          { selector: 'edge', style: { width: 1.5, label: 'data(label)', 'font-size': 8, 'line-color': '#94a3b8', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#94a3b8', 'curve-style': 'bezier' } },
        ]}
      />
    </div>
  )
}
