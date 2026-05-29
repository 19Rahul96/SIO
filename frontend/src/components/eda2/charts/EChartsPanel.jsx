import ReactECharts from 'echarts-for-react'

function toHeatmapValues(matrix = []) {
  const values = []
  for (let y = 0; y < matrix.length; y += 1) {
    const row = matrix[y] || []
    for (let x = 0; x < row.length; x += 1) {
      values.push([x, y, Number(row[x] || 0)])
    }
  }
  return values
}

export default function EChartsPanel({ chart }) {
  const type = chart?.chart_type
  const data = chart?.data || {}
  const panelHeight = Number(chart?.options?.height || 250)

  if (type !== 'heatmap') {
    return <div className="text-[11px] text-t3">Unsupported ECharts chart type: {String(type || 'unknown')}</div>
  }

  const x = data.x || []
  const y = data.y || []
  const matrix = data.values || []
  const values = toHeatmapValues(matrix)

  if (!x.length || !y.length || !values.length) {
    return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No heatmap data available.'}</div>
  }

  const option = {
    animation: false,
    grid: { left: 80, right: 20, top: 30, bottom: 60 },
    tooltip: { position: 'top' },
    xAxis: {
      type: 'category',
      data: x,
      axisLabel: { rotate: 35, fontSize: 10 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: y,
      axisLabel: { fontSize: 10 },
      splitArea: { show: true },
    },
    visualMap: {
      min: -1,
      max: 1,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#991b1b', '#fca5a5', '#f8fafc', '#86efac', '#166534'],
      },
    },
    series: [
      {
        type: 'heatmap',
        data: values,
        label: { show: false },
      },
    ],
  }

  return <ReactECharts option={option} style={{ width: '100%', height: panelHeight }} notMerge lazyUpdate />
}
