// Adapters: transform SIO endpoint payloads into the normalized chart-payload
// contract consumed by the existing eda2/charts/ChartRenderer (reuse unchanged).
//   { chart_id, section, chart_type, library_hint, title, data, options, meta }

export function correlationHeatmap(corr) {
  return {
    chart_id: 'correlation.pearson',
    section: 'correlation',
    chart_type: 'heatmap',
    library_hint: 'echarts',
    title: 'Pearson Correlation',
    data: { x: corr.labels || [], y: corr.labels || [], values: corr.pearson || [] },
    options: { height: 360 },
    meta: { empty_reason: 'At least 2 numeric columns required.' },
  }
}

export function qqScatter(column) {
  const pts = (column.qq_points || []).map((p) => ({ x: p.expected, y: p.actual, label: '', size: 6 }))
  const minv = Math.min(...pts.map((p) => p.x), ...pts.map((p) => p.y))
  const maxv = Math.max(...pts.map((p) => p.x), ...pts.map((p) => p.y))
  return {
    chart_id: `qq.${column.column}`,
    section: 'distributions',
    chart_type: 'scatter',
    library_hint: 'plotly',
    title: `Q–Q Plot — ${column.column}`,
    data: { points: pts, referenceLine: { x: [minv, maxv], y: [minv, maxv], name: 'Normal' } },
    options: { xTitle: 'Theoretical quantiles', yTitle: 'Sample quantiles', height: 300 },
    meta: {},
  }
}
