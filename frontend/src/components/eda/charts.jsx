import ReactECharts from 'echarts-for-react'
import { CONFIDENCE_COLORS } from './utils/confidenceColorScale'

const FONT = { fontFamily: 'Sora, sans-serif', fontSize: 11 }

// Section 5 — per-entity × per-layer confidence heatmap.
// Null cells render gray "—"; clicking a cell invokes onCell({entity, layer, score}).
export function ConfidenceHeatmap({ matrix, onCell, max = 40, height = 460 }) {
  const layers = matrix.layers || []
  const entities = (matrix.entities || []).slice(0, max)
  const yLabels = entities.map((e) => e.label)
  const data = []
  entities.forEach((e, y) => {
    layers.forEach((layer, x) => {
      const v = e.scores?.[layer]
      data.push([x, y, v == null ? '-' : Number(v.toFixed(3))])
    })
  })
  const option = {
    textStyle: FONT,
    tooltip: {
      formatter: (p) => {
        const e = entities[p.value[1]]
        return `<b>${e.label}</b><br/>${layers[p.value[0]]}: ${p.value[2] === '-' ? '— (no signal)' : p.value[2]}`
      },
    },
    grid: { left: 130, right: 16, top: 40, bottom: 20 },
    xAxis: { type: 'category', data: layers, position: 'top', splitArea: { show: true }, axisLabel: { fontSize: 9, interval: 0, rotate: 12 } },
    yAxis: { type: 'category', data: yLabels, splitArea: { show: true }, axisLabel: { fontSize: 9, width: 120, overflow: 'truncate' } },
    visualMap: {
      min: 0, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: -4, itemHeight: 80,
      inRange: { color: [CONFIDENCE_COLORS.RED, CONFIDENCE_COLORS.AMBER, CONFIDENCE_COLORS.TEAL] },
      textStyle: { fontSize: 9 },
    },
    series: [{
      type: 'heatmap', data,
      label: { show: true, fontSize: 8, formatter: (p) => (p.value[2] === '-' ? '—' : p.value[2]) },
      itemStyle: { borderColor: '#fff', borderWidth: 1 },
      emphasis: { itemStyle: { borderColor: '#4f46e5', borderWidth: 2 } },
    }],
  }
  const onEvents = {
    click: (p) => {
      if (!onCell) return
      const e = entities[p.value[1]]
      onCell({ entity: e, layer: layers[p.value[0]], score: p.value[2] === '-' ? null : p.value[2] })
    },
  }
  return <ReactECharts option={option} style={{ height }} notMerge onEvents={onEvents} />
}

// Box-and-whisker for a single numeric column.
export function BoxPlot({ box, name = '', height = 220 }) {
  if (!box) return null
  const option = {
    textStyle: FONT,
    grid: { left: 50, right: 20, top: 16, bottom: 30 },
    xAxis: { type: 'category', data: [name], axisLabel: { fontSize: 9 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 9 } },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'boxplot',
      data: [[box.lower_whisker, box.q1, box.median, box.q3, box.upper_whisker]],
      itemStyle: { color: 'rgba(79,70,229,0.12)', borderColor: '#4f46e5' },
    }],
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}
