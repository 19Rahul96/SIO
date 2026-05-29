import {
  Bar,
  BarChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  Tooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  RadialBarChart,
  RadialBar,
} from 'recharts'

const PIE_COLORS = ['#2563eb', '#d97706', '#16a34a', '#e11d48']

export default function RechartsPanel({ chart }) {
  const type = chart?.chart_type
  const data = chart?.data || {}
  const panelHeight = Number(chart?.options?.height || 210)

  if (type === 'bar') {
    const series = data.series || []
    const xKey = chart?.options?.xKey || 'name'
    const yKey = chart?.options?.yKey || 'value'
    const color = chart?.options?.color || '#2563eb'
    const seriesKeys = Array.isArray(chart?.options?.seriesKeys) ? chart.options.seriesKeys : []
    const stacked = Boolean(chart?.options?.stacked)
    if (!series.length) return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No bar data available.'}</div>
    return (
      <div style={{ width: '100%', height: panelHeight }}>
        <ResponsiveContainer>
          <BarChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,.2)" />
            <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            {seriesKeys.length > 0 ? (
              seriesKeys.map((s, idx) => (
                <Bar
                  key={`${s.key}-${idx}`}
                  dataKey={s.key}
                  name={s.name || s.key}
                  fill={s.color || '#2563eb'}
                  stackId={stacked ? 'a' : undefined}
                  radius={stacked ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                />
              ))
            ) : (
              <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'line') {
    const series = data.series || []
    const xKey = chart?.options?.xKey || 'date'
    const yKey = chart?.options?.yKey || 'count'
    if (!series.length) return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No line data available.'}</div>
    return (
      <div style={{ width: '100%', height: panelHeight }}>
        <ResponsiveContainer>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,.2)" />
            <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line type="monotone" dataKey={yKey} stroke="#2563eb" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'donut') {
    const series = data.series || []
    if (!series.length) return <div className="text-[11px] text-t3">{chart?.meta?.empty_reason || 'No donut data available.'}</div>
    return (
      <div style={{ width: '100%', height: panelHeight }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={series} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}>
              {series.map((_, i) => (
                <Cell key={`cell-${i}`} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'gauge') {
    const value = Number(data.value || 0)
    const gaugeData = [{ name: chart?.title || 'score', value: Math.max(0, Math.min(1, value)) * 100, fill: '#16a34a' }]
    return (
      <div style={{ width: '100%', height: panelHeight }}>
        <ResponsiveContainer>
          <RadialBarChart
            cx="50%"
            cy="65%"
            innerRadius="50%"
            outerRadius="85%"
            barSize={16}
            startAngle={180}
            endAngle={0}
            data={gaugeData}
          >
            <RadialBar background dataKey="value" cornerRadius={8} />
            <Tooltip />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  return <div className="text-[11px] text-t3">Unsupported Recharts chart type: {String(type || 'unknown')}</div>
}
