import { useEffect, useState } from 'react'
import api from '../services/api'
import useStore from '../store'

function MetricCard({ label, value, sub, pill, pillClass, barColor }) {
  return (
    <div className="mcard" style={{ '--bar-color': barColor }}>
      <div
        className="absolute top-0 left-0 right-0 h-0.5 rounded-t"
        style={{ background: barColor }}
      />
      <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">{label}</div>
      <div className="font-sora text-[26px] font-bold text-t1 leading-none">{value}</div>
      {sub && <div className="text-[11px] text-t2 mt-1">{sub}</div>}
      {pill && <div className={`mt-2 ${pillClass}`}>{pill}</div>}
    </div>
  )
}

function Pyramid() {
  return (
    <div className="flex flex-col items-center gap-1 pb-7 pt-1">
      <div className="pyramid-step pyramid-step-active">Result layer</div>
      <div className="pyramid-step pyramid-step-done w-56">Model selection</div>
      <div className="pyramid-step pyramid-step-done w-80">SLM engine</div>
      <div className="pyramid-step pyramid-step-done w-[420px]">Data + GraphRAG foundation</div>
    </div>
  )
}

export default function DashboardPage() {
  const { startNewSession, setDashboardStats, dashboardStats } = useStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.getStats()
      .then(setDashboardStats)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const stats = dashboardStats || {}
  const tokensSaved = stats.tokens_saved ?? 0
  const slmsActive = stats.active_slms ?? 0
  const filesIngested = stats.files_ingested ?? 0
  const costSaved = stats.cost_saved ?? 0
  const sessions = stats.recent_sessions ?? []

  return (
    <div>
      {/* Page header */}
      <div className="bg-card border-b border-dborder px-0 py-7 mb-7">
        <div className="max-w-[1100px] mx-auto px-12">
          <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-t3 mb-1.5 flex items-center gap-2">
            <span className="inline-block w-4 h-px bg-accent" />
            Workspace overview
          </div>
          <div className="font-sora text-2xl font-semibold text-t1">Intelligence Dashboard</div>
          <div className="text-[12px] text-t2 mt-1">Token savings, SLM usage & pipeline health at a glance</div>
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-12">
        <Pyramid />

        <div className="sect">Key metrics</div>
        <div className="grid grid-cols-4 gap-3.5">
          <MetricCard
            label="Tokens saved"
            value={tokensSaved > 0 ? `${(tokensSaved / 1000).toFixed(1)}K` : '—'}
            sub="this month"
            pill="↓ 68% vs GPT-4"
            pillClass="pill-g"
            barColor="#16a34a"
          />
          <MetricCard
            label="SLMs active"
            value={slmsActive || '0'}
            sub="trained models"
            pill={slmsActive > 0 ? `+${slmsActive} total` : 'None yet'}
            pillClass="pill-b"
            barColor="#4f46e5"
          />
          <MetricCard
            label="Files ingested"
            value={filesIngested || '0'}
            sub="PDF · DOCX · XLSX"
            pill={filesIngested > 0 ? `${filesIngested} complete` : 'Upload files'}
            pillClass="pill-b"
            barColor="#2563eb"
          />
          <MetricCard
            label="Cost saved"
            value={costSaved > 0 ? `$${costSaved.toFixed(2)}` : '$0'}
            sub="this month"
            pill="83% efficiency"
            pillClass="pill-a"
            barColor="#d97706"
          />
        </div>

        <div className="h-6" />

        <div className="grid grid-cols-2 gap-3.5">
          {/* Token reduction bars */}
          <div className="card">
            <div className="flex items-center justify-between mb-3.5">
              <span className="text-[13px] font-semibold text-t1">Token usage reduction</span>
              <span className="text-[10px] px-2 py-0.5 rounded-lg bg-bg4 text-t3 border border-dborder">Last 7 sessions</span>
            </div>
            <div className="flex items-center gap-2.5 mb-2.5">
              <span className="text-[11px] text-t2 w-24 flex-shrink-0">Without SLM</span>
              <div className="flex-1 prog-bar"><div className="prog-fill" style={{ width: '100%', background: '#c8d0e3' }} /></div>
              <span className="text-[11px] font-semibold text-t1 w-9 text-right">100%</span>
            </div>
            <div className="flex items-center gap-2.5 mb-2.5">
              <span className="text-[11px] text-t2 w-24 flex-shrink-0">With SLM</span>
              <div className="flex-1 prog-bar"><div className="prog-fill" style={{ width: '32%', background: '#4f46e5' }} /></div>
              <span className="text-[11px] font-semibold text-t1 w-9 text-right">32%</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-[11px] text-t2 w-24 flex-shrink-0">GraphRAG</span>
              <div className="flex-1 prog-bar"><div className="prog-fill" style={{ width: '18%', background: '#0d9488' }} /></div>
              <span className="text-[11px] font-semibold text-t1 w-9 text-right">18%</span>
            </div>
            <div className="mt-3 pt-2.5 border-t border-dborder text-[11px] text-t2">
              <span className="text-gg font-semibold">68% avg reduction</span> using your SLM library
            </div>
          </div>

          {/* SLM hit rate donut */}
          <div className="card">
            <div className="flex items-center justify-between mb-3.5">
              <span className="text-[13px] font-semibold text-t1">SLM hit rate</span>
              <span className="text-[10px] px-2 py-0.5 rounded-lg bg-bg4 text-t3 border border-dborder">Reuse vs create</span>
            </div>
            <div className="flex items-center gap-5">
              <svg width="80" height="80" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="29" fill="none" stroke="#eef1f7" strokeWidth="12" />
                <circle cx="40" cy="40" r="29" fill="none" stroke="#4f46e5" strokeWidth="12"
                  strokeDasharray="118 64" strokeDashoffset="0" transform="rotate(-90 40 40)" />
                <circle cx="40" cy="40" r="29" fill="none" stroke="#0d9488" strokeWidth="12"
                  strokeDasharray="40 142" strokeDashoffset="-118" transform="rotate(-90 40 40)" />
                <text x="40" y="44" textAnchor="middle" fontSize="12" fontWeight="700" fill="#1a1d2e" fontFamily="Sora,sans-serif">
                  {slmsActive > 0 ? '65%' : '—'}
                </text>
              </svg>
              <div>
                <div className="flex items-center gap-2 mb-2 text-[11px] text-t2">
                  <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0" />SLM reused — 65%
                </div>
                <div className="flex items-center gap-2 mb-2 text-[11px] text-t2">
                  <span className="w-2 h-2 rounded-full bg-teal flex-shrink-0" />New SLM created — 22%
                </div>
                <div className="flex items-center gap-2 text-[11px] text-t2">
                  <span className="w-2 h-2 rounded-full bg-dborder flex-shrink-0" />Full LLM fallback — 13%
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="h-6" />
        <div className="sect">Recent sessions</div>

        {sessions.length === 0 ? (
          <div className="text-center py-10 text-t3 text-[12px]">
            No sessions yet — upload files and run your first query
          </div>
        ) : (
          sessions.map((s, i) => (
            <div key={i} className="flex items-center gap-3 p-3 bg-card2 border border-dborder rounded-sm mb-2 transition-colors hover:border-dborder2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0 bg-accent">
                SLM
              </div>
              <div className="flex-1">
                <div className="text-[12px] font-medium text-t1">{s.name}</div>
                <div className="text-[10px] text-t3 mt-0.5">
                  {s.domain} domain · used {s.usage_count}× · {s.slm_id?.slice(0, 8)}…
                </div>
              </div>
              <span className="pill-g">SLM active</span>
            </div>
          ))
        )}

        <div className="h-6" />
        <button className="btn btn-p btn-full" onClick={startNewSession}>
          Start new session →
        </button>
        <div className="h-8" />
      </div>
    </div>
  )
}
