import Plot from 'react-plotly.js'

export default function PlotlyPanel({ chart }) {
  const type = chart?.chart_type
  const data = chart?.data || {}
  const panelHeight = Number(chart?.options?.height || 250)

  if (type === 'scatter') {
    const points = data.points || []
    if (!points.length) return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No scatter data available.'}</div>

    const x = points.map((p) => p.x)
    const y = points.map((p) => p.y)
    const labels = points.map((p) => p.label || '')
    const sizes = points.map((p) => Number(p.size || 7))
    const colors = points.map((p) => p.color || chart?.options?.pointColor || '#2563eb')

    const traces = [
      {
        x,
        y,
        text: labels,
        mode: 'markers',
        type: 'scattergl',
        hovertemplate: '%{text}<br>x=%{x:.3f}<br>y=%{y:.3f}<extra></extra>',
        marker: {
          color: colors,
          size: sizes,
          opacity: 0.85,
        },
      },
    ]

    const ref = data.referenceLine || null
    if (ref?.x?.length && ref?.y?.length) {
      traces.push({
        x: ref.x,
        y: ref.y,
        mode: 'lines',
        type: 'scatter',
        name: ref.name || 'reference',
        line: { color: '#d97706', width: 1.5, dash: 'dash' },
        hoverinfo: 'skip',
      })
    }

    return (
      <Plot
        data={traces}
        layout={{
          autosize: true,
          margin: { l: 50, r: 20, t: 20, b: 45 },
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          xaxis: { title: chart?.options?.xTitle || '', zeroline: false },
          yaxis: { title: chart?.options?.yTitle || '', zeroline: false },
          showlegend: Boolean(ref),
        }}
        style={{ width: '100%', height: `${panelHeight}px` }}
        config={{ displayModeBar: false, responsive: true }}
      />
    )
  }

  return <div className="text-[11px] text-t3">Unsupported Plotly chart type: {String(type || 'unknown')}</div>
}
