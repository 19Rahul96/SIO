import ReactECharts from 'echarts-for-react'
import CytoscapeComponent from 'react-cytoscapejs'

const PALETTE = ['#4f46e5', '#7c3aed', '#0d9488', '#d97706', '#2563eb', '#16a34a', '#e11d48', '#64748b']
const BASE = { animation: true, textStyle: { fontFamily: 'Sora, sans-serif', fontSize: 11 } }

export function Donut({ data, height = 240, colors = PALETTE }) {
  const seriesData = Object.entries(data || {}).map(([name, value]) => ({ name, value }))
  if (!seriesData.length) return <Empty />
  const option = {
    ...BASE,
    color: colors,
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: true, fontSize: 10, formatter: '{b}: {c}' },
        data: seriesData,
      },
    ],
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}

export function Bars({ data, height = 240, color = '#4f46e5', horizontal = false }) {
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1])
  if (!entries.length) return <Empty />
  const cats = entries.map((e) => e[0])
  const vals = entries.map((e) => e[1])
  const catAxis = { type: 'category', data: cats, axisLabel: { fontSize: 9, rotate: horizontal ? 0 : 30, interval: 0 } }
  const valAxis = { type: 'value', axisLabel: { fontSize: 9 } }
  const option = {
    ...BASE,
    grid: { left: horizontal ? 110 : 40, right: 20, top: 16, bottom: horizontal ? 16 : 60 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: horizontal ? valAxis : catAxis,
    yAxis: horizontal ? { ...catAxis, inverse: true } : valAxis,
    series: [{ type: 'bar', data: vals, itemStyle: { color, borderRadius: 4 }, barMaxWidth: 26 }],
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}

// Radial gauge for a 0..1 score (trust, risk, consistency).
export function Gauge({ value = 0, title = '', height = 220, invert = false }) {
  const v = Math.round((value || 0) * 100)
  const good = invert ? v < 30 : v >= 75
  const mid = invert ? v < 60 : v >= 45
  const color = good ? '#16a34a' : mid ? '#d97706' : '#e11d48'
  const option = {
    ...BASE,
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        progress: { show: true, width: 14, itemStyle: { color } },
        axisLine: { lineStyle: { width: 14, color: [[1, '#eef1f7']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        title: { offsetCenter: [0, '28%'], fontSize: 11, color: '#5a6280' },
        detail: { valueAnimation: true, fontSize: 26, offsetCenter: [0, '-5%'], formatter: '{value}', color },
        data: [{ value: v, name: title }],
      },
    ],
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}

// Confidence-bar list (e.g. column semantic-label confidences).
export function ConfBars({ items, height }) {
  if (!items?.length) return <Empty />
  return (
    <div className="space-y-2" style={{ maxHeight: height, overflowY: 'auto' }}>
      {items.map((it, i) => {
        const pct = Math.round((it.value || 0) * 100)
        const color = pct >= 75 ? '#16a34a' : pct >= 45 ? '#d97706' : '#e11d48'
        return (
          <div key={i}>
            <div className="flex justify-between text-[11px] text-t2 mb-0.5">
              <span className="truncate">{it.label}</span>
              <span style={{ color }}>{it.tag || `${pct}%`}</span>
            </div>
            <div className="h-1.5 bg-bg4 rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Taxonomy as an interactive hierarchy graph (cytoscape).
export function TaxonomyGraph({ taxonomy, height = 340 }) {
  const entries = Object.entries(taxonomy || {})
  if (!entries.length) return <Empty />
  const els = []
  entries.forEach(([t]) => els.push({ data: { id: t, label: t } }))
  entries.forEach(([t, def]) => {
    if (def.parent) els.push({ data: { id: `${def.parent}->${t}`, source: def.parent, target: t } })
  })
  return (
    <div className="border border-dborder rounded-card bg-bg3" style={{ height }}>
      <CytoscapeComponent
        elements={els}
        layout={{ name: 'breadthfirst', directed: true, padding: 20, spacingFactor: 1.3 }}
        style={{ width: '100%', height: '100%' }}
        stylesheet={[
          { selector: 'node', style: { label: 'data(label)', 'background-color': '#4f46e5', color: '#1a1d2e', 'font-size': 10, 'text-valign': 'bottom', 'text-margin-y': 3, width: 16, height: 16 } },
          { selector: 'edge', style: { width: 1.5, 'line-color': '#c8d0e3', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#c8d0e3', 'curve-style': 'bezier' } },
        ]}
      />
    </div>
  )
}

function Empty() {
  return <div className="text-[11px] text-t3 py-8 text-center">No data available.</div>
}

export function StatTiles({ tiles }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {tiles.map((t, i) => (
        <div key={i} className="mcard">
          <div className="text-[10px] uppercase tracking-widest text-t3 mb-1">{t.label}</div>
          <div className="text-xl font-bold" style={{ color: t.color || '#1a1d2e' }}>{t.value ?? '—'}</div>
        </div>
      ))}
    </div>
  )
}
