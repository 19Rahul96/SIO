import RechartsPanel from './RechartsPanel'
import EChartsPanel from './EChartsPanel'
import PlotlyPanel from './PlotlyPanel'
import CytoscapePanel from './CytoscapePanel'

export default function ChartRenderer({ chart }) {
  if (!chart) return <div className="text-[11px] text-t3">No chart payload available.</div>
  const hint = String(chart.library_hint || '').toLowerCase()

  if (hint === 'recharts') return <RechartsPanel chart={chart} />
  if (hint === 'echarts') return <EChartsPanel chart={chart} />
  if (hint === 'plotly') return <PlotlyPanel chart={chart} />
  if (hint === 'cytoscape') return <CytoscapePanel chart={chart} />

  return <div className="text-[11px] text-t3">Unknown chart library hint: {chart.library_hint}</div>
}
