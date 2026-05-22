import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'

function pct(n) {
  return `${(Number(n || 0) * 100).toFixed(1)}%`
}

function num(n) {
  return Number(n || 0).toLocaleString()
}

function relStrengthColor(level) {
  const key = String(level || '').toLowerCase()
  if (key === 'strong') return '#16a34a'
  if (key === 'medium') return '#d97706'
  return '#e11d48'
}

function scorePct(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function sourceCountLabel(label, count) {
  return `${count} ${label}${count === 1 ? '' : 's'}`
}

export default function EDAVisualsViewer({ fileIds = [], dbIds = [], onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeSource, setActiveSource] = useState('db')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getEdaDashboard({ fileIds, dbIds })
      .then((res) => {
        setData(res)
        const dbRuns = res?.db_eda?.runs || []
        const fileRuns = res?.file_eda?.runs || []
        if (dbRuns.length > 0) {
          setActiveSource('db')
          setSelectedRunId(dbRuns[0].db_id)
        } else if (fileRuns.length > 0) {
          setActiveSource('file')
          setSelectedRunId(fileRuns[0].file_id)
        } else {
          setSelectedRunId(null)
        }
      })
      .catch((e) => setError(e.message || 'Failed to load EDA visuals'))
      .finally(() => setLoading(false))
  }, [dbIds.join(','), fileIds.join(',')])

  const summary = data?.summary || {}
  const dbSummary = data?.db_eda?.summary || {}
  const fileSummary = data?.file_eda?.summary || {}
  const dbRuns = data?.db_eda?.runs || []
  const fileRuns = data?.file_eda?.runs || []
  const runs = activeSource === 'file' ? fileRuns : dbRuns
  const selectedRun = useMemo(
    () => runs.find((r) => (activeSource === 'file' ? r.file_id : r.db_id) === selectedRunId) || runs[0] || null,
    [runs, selectedRunId]
  )

  const joinabilityTotal =
    (dbSummary?.joinability_distribution?.strong || 0) +
    (dbSummary?.joinability_distribution?.medium || 0) +
    (dbSummary?.joinability_distribution?.weak || 0)

  const hasRuns = dbRuns.length > 0 || fileRuns.length > 0

  useEffect(() => {
    if (activeSource === 'db' && dbRuns.length > 0) {
      if (!dbRuns.some((run) => run.db_id === selectedRunId)) {
        setSelectedRunId(dbRuns[0].db_id)
      }
      return
    }
    if (activeSource === 'file' && fileRuns.length > 0) {
      if (!fileRuns.some((run) => run.file_id === selectedRunId)) {
        setSelectedRunId(fileRuns[0].file_id)
      }
      return
    }
    if (activeSource === 'db' && fileRuns.length > 0) {
      setActiveSource('file')
      setSelectedRunId(fileRuns[0].file_id)
    } else if (activeSource === 'file' && dbRuns.length > 0) {
      setActiveSource('db')
      setSelectedRunId(dbRuns[0].db_id)
    }
  }, [activeSource, dbRuns, fileRuns, selectedRunId])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(10,12,22,.72)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="bg-card2 border border-dborder rounded-card flex flex-col"
        style={{ width: '960px', maxWidth: '95vw', maxHeight: '88vh' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-dborder flex-shrink-0">
          <div>
            <div className="font-sora text-[15px] font-semibold text-t1">EDA Visuals and Stage Insights</div>
            <div className="text-[11px] text-t3 mt-0.5">
              Detailed view of profiling, anomaly detection, relationship evidence, and trust impact.
            </div>
          </div>
          <button className="btn btn-sm" onClick={onClose}>✕ Close</button>
        </div>

        <div className="flex gap-0 border-b border-dborder flex-shrink-0">
          {[['overview', 'Overview'], ['runs', `Run Details${runs.length ? ` (${runs.length})` : ''}`]].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="px-5 py-2.5 text-[11px] font-medium transition-colors border-b-2"
              style={{
                borderBottomColor: tab === key ? 'var(--color-amber, #d97706)' : 'transparent',
                color: tab === key ? '#d97706' : 'var(--color-t2, #5a6077)',
                background: 'transparent',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && <div className="text-[12px] text-t3 text-center py-8">Loading EDA visuals...</div>}
          {error && <div className="text-[12px] text-coral text-center py-8">Error: {error}</div>}
          {!loading && !error && !hasRuns && (
            <div className="text-[12px] text-t2 text-center py-10">
              No EDA artifacts found yet. Complete an upload or DB ingestion pipeline to generate EDA visuals.
            </div>
          )}

          {!loading && !error && hasRuns && tab === 'overview' && (
            <div className="space-y-5">
              <div className="grid grid-cols-4 gap-3.5">
                <div className="mcard">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Total runs</div>
                  <div className="font-sora text-[24px] font-bold text-t1">{num(summary.total_runs)}</div>
                </div>
                <div className="mcard">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Quality</div>
                  <div className="font-sora text-[24px] font-bold text-t1">{scorePct(summary.combined_quality_score)}</div>
                </div>
                <div className="mcard">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Confidence</div>
                  <div className="font-sora text-[24px] font-bold text-t1">{scorePct(summary.combined_confidence_score)}</div>
                </div>
                <div className="mcard">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Retrieval readiness</div>
                  <div className="font-sora text-[24px] font-bold text-t1">{scorePct(summary.combined_retrieval_readiness_score)}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3.5">
                <div className="card">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-[12px] font-semibold text-t1">Upload EDA summary</div>
                      <div className="text-[10px] text-t3 mt-1">Files processed through the extraction and GraphRAG pipeline.</div>
                    </div>
                    <span className="pill-a">{sourceCountLabel('upload', fileSummary.run_count || 0)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Quality</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(fileSummary.avg_overall_kg_quality)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Confidence</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(fileSummary.avg_confidence_score)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Retrieval</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(fileSummary.avg_retrieval_readiness)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Graph density</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{pct(fileSummary.avg_graph_density)}</div>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-[12px] font-semibold text-t1">Database EDA summary</div>
                      <div className="text-[10px] text-t3 mt-1">Schema profiling, anomaly detection, and relationship evidence across DB ingestions.</div>
                    </div>
                    <span className="pill-b">{sourceCountLabel('DB', dbSummary.run_count || 0)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Quality</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(dbSummary.avg_overall_kg_quality)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Confidence</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(dbSummary.avg_confidence_score)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Retrieval</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(dbSummary.avg_retrieval_readiness)}</div>
                    </div>
                    <div className="mcard">
                      <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Trust</div>
                      <div className="font-sora text-[20px] font-bold text-t1">{scorePct(dbSummary.avg_graph_trust_score)}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3.5">
                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-3">Joinability signal distribution</div>
                  {[
                    ['strong', dbSummary?.joinability_distribution?.strong || 0],
                    ['medium', dbSummary?.joinability_distribution?.medium || 0],
                    ['weak', dbSummary?.joinability_distribution?.weak || 0],
                  ].map(([label, value]) => {
                    const pctWidth = joinabilityTotal ? (Number(value) / joinabilityTotal) * 100 : 0
                    return (
                      <div key={label} className="mb-2.5">
                        <div className="flex justify-between text-[11px] text-t2 mb-1">
                          <span className="capitalize">{label}</span>
                          <span>{num(value)}</span>
                        </div>
                        <div className="prog-bar">
                          <div className="prog-fill" style={{ width: `${pctWidth}%`, background: relStrengthColor(label) }} />
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="card">
                  <div className="text-[12px] font-semibold text-t1 mb-3">Recent source readiness</div>
                  <div className="space-y-2">
                    {[
                      { key: 'upload', label: 'Uploads', value: fileSummary.avg_retrieval_readiness || 0, tone: '#0d9488' },
                      { key: 'db', label: 'Databases', value: dbSummary.avg_retrieval_readiness || 0, tone: '#2563eb' },
                      { key: 'combined', label: 'Combined trust', value: summary.combined_trust_score || 0, tone: '#d97706' },
                    ].map((row) => (
                      <div key={row.key}>
                        <div className="flex justify-between text-[10px] text-t3 mb-1">
                          <span>{row.label}</span>
                          <span>{scorePct(row.value)}</span>
                        </div>
                        <div className="prog-bar">
                          <div className="prog-fill" style={{ width: `${Math.min(100, (row.value || 0) * 100)}%`, background: row.tone }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3.5">
                <div className="card">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">DB high-risk edges</div>
                  <div className="font-sora text-[22px] font-bold text-t1">{pct(dbSummary.avg_high_risk_edge_ratio)}</div>
                </div>
                <div className="card">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">DB contradictions</div>
                  <div className="font-sora text-[22px] font-bold text-t1">{pct(dbSummary.avg_contradiction_ratio)}</div>
                </div>
                <div className="card">
                  <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">DB calibration error</div>
                  <div className="font-sora text-[22px] font-bold text-t1">{pct(dbSummary.avg_calibration_proxy_error)}</div>
                </div>
              </div>
            </div>
          )}

          {!loading && !error && hasRuns && tab === 'runs' && (
            <div className="grid grid-cols-12 gap-3.5">
              <div className="col-span-4">
                <div className="card">
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      className="btn btn-sm"
                      style={{
                        color: activeSource === 'db' ? '#2563eb' : 'var(--color-t2, #5a6077)',
                        borderColor: activeSource === 'db' ? 'rgba(37,99,235,.35)' : 'var(--color-dborder, rgba(123,132,160,.2))',
                        background: activeSource === 'db' ? 'rgba(37,99,235,.08)' : 'transparent',
                      }}
                      onClick={() => {
                        setActiveSource('db')
                        if (dbRuns[0]) setSelectedRunId(dbRuns[0].db_id)
                      }}
                    >
                      DB
                    </button>
                    <button
                      className="btn btn-sm"
                      style={{
                        color: activeSource === 'file' ? '#0d9488' : 'var(--color-t2, #5a6077)',
                        borderColor: activeSource === 'file' ? 'rgba(13,148,136,.35)' : 'var(--color-dborder, rgba(123,132,160,.2))',
                        background: activeSource === 'file' ? 'rgba(13,148,136,.08)' : 'transparent',
                      }}
                      onClick={() => {
                        setActiveSource('file')
                        if (fileRuns[0]) setSelectedRunId(fileRuns[0].file_id)
                      }}
                    >
                      Upload
                    </button>
                  </div>
                  <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">{activeSource === 'file' ? 'Upload runs' : 'DB runs'}</div>
                  {runs.map((run) => {
                    const runId = activeSource === 'file' ? run.file_id : run.db_id
                    const active = selectedRun && (activeSource === 'file' ? selectedRun.file_id === run.file_id : selectedRun.db_id === run.db_id)
                    return (
                      <button
                        key={runId}
                        className={`model-row w-full text-left ${active ? 'chosen' : ''}`}
                        onClick={() => setSelectedRunId(runId)}
                      >
                        <div className="flex-1">
                          <div className="text-[12px] text-t1 font-semibold truncate">{activeSource === 'file' ? run.filename : run.database}</div>
                          <div className="text-[10px] text-t3 mt-1">
                            {activeSource === 'file'
                              ? `${run.source || 'file'} · quality ${scorePct(run.overall_kg_quality_score)} · readiness ${scorePct(run.retrieval_readiness_score)}`
                              : `${run.engine} · tables ${run.eda_summary?.table_count || 0} · anomalies ${run.eda_summary?.anomalous_table_count || 0}`}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="col-span-8">
                <div className="card">
                  {!selectedRun && <div className="text-[12px] text-t2">Select a run to inspect details.</div>}
                  {selectedRun && (
                    <>
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="text-[16px] font-semibold text-t1">{activeSource === 'file' ? selectedRun.filename : selectedRun.database}</div>
                          <div className="text-[11px] text-t3">
                            {activeSource === 'file'
                              ? `${selectedRun.source || 'file'} · ${(selectedRun.file_id || '').slice(0, 12)}...`
                              : `${selectedRun.engine} · ${(selectedRun.db_id || '').slice(0, 12)}...`}
                          </div>
                        </div>
                        <span className="pill-a">
                          {activeSource === 'file'
                            ? `Trust ${scorePct(selectedRun.confidence_score)}`
                            : `EDA evidence ${selectedRun.eda_summary?.relationship_evidence_count || 0}`}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-3 mb-4">
                        <div className="mcard">
                          <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">{activeSource === 'file' ? 'Quality' : 'High-risk edges'}</div>
                          <div className="font-sora text-[20px] font-bold text-t1">{activeSource === 'file' ? scorePct(selectedRun.overall_kg_quality_score) : pct(selectedRun.trust?.high_risk_edge_ratio || 0)}</div>
                        </div>
                        <div className="mcard">
                          <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">{activeSource === 'file' ? 'Confidence' : 'Contradictions'}</div>
                          <div className="font-sora text-[20px] font-bold text-t1">{activeSource === 'file' ? scorePct(selectedRun.confidence_score) : pct(selectedRun.trust?.contradiction_ratio || 0)}</div>
                        </div>
                        <div className="mcard">
                          <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">{activeSource === 'file' ? 'Retrieval readiness' : 'Calibration error'}</div>
                          <div className="font-sora text-[20px] font-bold text-t1">{activeSource === 'file' ? scorePct(selectedRun.retrieval_readiness_score) : pct(selectedRun.trust?.calibration_proxy_error || 0)}</div>
                        </div>
                      </div>

                      {activeSource === 'file' ? (
                        <>
                          <div className="text-[11px] text-t3 mb-1 uppercase tracking-wider font-semibold">Entity distribution</div>
                          {(selectedRun.entity_distribution || []).slice(0, 6).map((entity) => (
                            <div key={entity.type} className="mb-2">
                              <div className="flex justify-between text-[11px] text-t2 mb-1">
                                <span>{entity.type}</span>
                                <span>{num(entity.count)}</span>
                              </div>
                              <div className="prog-bar">
                                <div className="prog-fill" style={{ width: `${Math.min(100, entity.count * 10)}%`, background: '#0d9488' }} />
                              </div>
                            </div>
                          ))}

                          <div className="text-[11px] text-t3 mt-4 mb-1 uppercase tracking-wider font-semibold">Top central entities</div>
                          {(selectedRun.node_centrality || []).slice(0, 8).map((node, index) => (
                            <div key={`${node.id || node.label || 'node'}-${index}`} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                              <div className="text-[11px] text-t1 truncate">{node.label || node.id || 'Entity'}</div>
                              <div className="flex items-center justify-between mt-1 text-[10px] text-t3">
                                <span>{node.type || 'entity'}</span>
                                <span>score {Number(node.score || node.centrality || 0).toFixed(2)}</span>
                              </div>
                            </div>
                          ))}
                        </>
                      ) : (
                        <>
                          <div className="text-[11px] text-t3 mb-1 uppercase tracking-wider font-semibold">Top anomalous tables</div>
                          {(selectedRun.top_tables || []).slice(0, 6).map((table) => (
                            <div key={table.table_name} className="mb-2">
                              <div className="flex justify-between text-[11px] text-t2 mb-1">
                                <span>{table.table_name}</span>
                                <span>{pct(table.high_risk_ratio)} risk</span>
                              </div>
                              <div className="prog-bar">
                                <div className="prog-fill" style={{ width: `${Math.min(100, (table.high_risk_ratio || 0) * 100)}%`, background: '#d97706' }} />
                              </div>
                            </div>
                          ))}

                          <div className="text-[11px] text-t3 mt-4 mb-1 uppercase tracking-wider font-semibold">Relationship evidence overlap</div>
                          {(selectedRun.top_relationship_evidence || []).slice(0, 8).map((rel) => (
                            <div key={rel.key} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                              <div className="text-[11px] text-t1 truncate">{rel.key}</div>
                              <div className="flex items-center justify-between mt-1 text-[10px] text-t3">
                                <span className="capitalize" style={{ color: relStrengthColor(rel.joinability_signal) }}>{rel.joinability_signal}</span>
                                <span>overlap {pct(rel.overlap_pct)} ({rel.overlap_count})</span>
                              </div>
                            </div>
                          ))}
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
