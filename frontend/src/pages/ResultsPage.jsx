import { useEffect, useState } from 'react'
import api from '../services/api'
import useStore from '../store'

function Pyramid() {
  return (
    <div className="flex flex-col items-center gap-1 pb-7">
      {[
        { label: '✓ Result', w: 100, done: true, active: true },
        { label: '✓ Model select', w: 190, done: true },
        { label: '✓ SLM engine', w: 280, done: true },
        { label: '✓ Data + GraphRAG', w: 380, done: true },
      ].map((t, i) => (
        <div key={i} className={`pyramid-step ${t.active ? 'pyramid-step-active' : t.done ? 'pyramid-step-done' : ''}`} style={{ width: t.w }}>
          {t.label}
        </div>
      ))}
    </div>
  )
}

function TraceStep({ event, description, elapsed, color, icon }) {
  return (
    <div className="tl-item">
      <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 border ${color}`}>
        {icon}
      </div>
      <div>
        <div className="text-[12px] font-semibold text-t1 mb-1">{description}</div>
        {elapsed !== undefined && (
          <span className={`inline-block text-[10px] px-2 py-0.5 rounded-lg mt-1 font-medium border ${color}`}>
            +{elapsed.toFixed(2)}s
          </span>
        )}
      </div>
    </div>
  )
}

const TRACE_STYLES = {
  query_received:      { color: 'bg-amber/10 border-amber/30 text-amber', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="2" y="1.5" width="11" height="12" rx="2" stroke="#d97706" strokeWidth="1.3"/><path d="M4.5 5.5h6M4.5 8h4" stroke="#d97706" strokeWidth="1" strokeLinecap="round"/></svg> },
  slm_loaded:          { color: 'bg-coral/10 border-coral/30 text-coral', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="7.5" cy="7.5" r="5.5" stroke="#e11d48" strokeWidth="1.3"/><path d="M10.5 4.5L4.5 10.5" stroke="#e11d48" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  retrieval_complete:  { color: 'bg-blue/10 border-blue/30 text-blue', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1.5" y="3" width="12" height="9" rx="2" stroke="#2563eb" strokeWidth="1.3"/><path d="M5 3V2M10 3V2M1.5 6.5h12" stroke="#2563eb" strokeWidth="1" strokeLinecap="round"/></svg> },
  graph_traversed:     { color: 'bg-purple/10 border-purple/30 text-purple', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="7.5" cy="3" r="2" stroke="#7c3aed" strokeWidth="1.3"/><circle cx="2.5" cy="12" r="2" stroke="#7c3aed" strokeWidth="1.3"/><circle cx="12.5" cy="12" r="2" stroke="#7c3aed" strokeWidth="1.3"/><path d="M7.5 5v2m0 2l-4 3m4-3l4 3" stroke="#7c3aed" strokeWidth="1.2"/></svg> },
  model_selected:      { color: 'bg-teal/10 border-teal/30 text-teal', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1.5" y="3" width="12" height="9" rx="2" stroke="#0d9488" strokeWidth="1.3"/><path d="M5 3V2M10 3V2M1.5 6.5h12" stroke="#0d9488" strokeWidth="1" strokeLinecap="round"/></svg> },
  response_generated:  { color: 'bg-gg/10 border-gg/30 text-gg', icon: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M2.5 8L5.5 11 12.5 4" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg> },
}

export default function ResultsPage() {
  const {
    prompt, slmResult, selectedModel, uploadedFileIds,
    finalRunResult, setFinalRunResult, setStep, startNewSession, isRunning, setRunning,
    wikiPages, setWikiPages, selectedWikiPage, setSelectedWikiPage,
    wikiReviews, setWikiReviews, wikiLoading, setWikiLoading,
    wikiReviewUpdating, setWikiReviewUpdating,
    qualityMetrics, setQualityMetrics,
  } = useStore()
  const [error, setError] = useState(null)
  const [wikiSearch, setWikiSearch] = useState('')

  const slm = slmResult?.slm

  useEffect(() => {
    if (finalRunResult) return
    if (!slm || !selectedModel) return
    setRunning(true)
    setError(null)
    api.finalRun(prompt, slm.id, selectedModel, uploadedFileIds)
      .then(setFinalRunResult)
      .catch((e) => setError(e.message))
      .finally(() => setRunning(false))
  }, [])

  const refreshWiki = async (query = '') => {
    setWikiLoading(true)
    try {
      const [pagesRes, reviewsRes] = await Promise.all([
        api.getWikiPages({ q: query, fileIds: uploadedFileIds, limit: 80 }),
        api.getWikiReviews({ status: 'pending', limit: 80 }),
      ])
      const pages = pagesRes?.pages || []
      setWikiPages(pages)
      setWikiReviews(reviewsRes?.reviews || [])

      if (!selectedWikiPage && pages.length > 0) {
        const first = await api.getWikiPage(pages[0].canonical_id)
        setSelectedWikiPage(first)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setWikiLoading(false)
    }
  }

  useEffect(() => {
    refreshWiki('')
    api.getQualityMetrics().then(setQualityMetrics).catch(() => {})
  }, [])

  const selectWikiPage = async (canonicalId) => {
    if (!canonicalId) return
    setWikiLoading(true)
    try {
      const page = await api.getWikiPage(canonicalId)
      setSelectedWikiPage(page)
    } catch (e) {
      setError(e.message)
    } finally {
      setWikiLoading(false)
    }
  }

  const applyReview = async (reviewId, decision) => {
    setWikiReviewUpdating(true)
    try {
      await api.submitWikiReview(reviewId, decision, 'frontend-review')
      await refreshWiki(wikiSearch)
    } catch (e) {
      setError(e.message)
    } finally {
      setWikiReviewUpdating(false)
    }
  }

  const result = finalRunResult
  const insights = result?.session_insights
  const trace = result?.trace
  const trust = qualityMetrics?.trust || {}
  const eda = qualityMetrics?.eda || {}

  const downloadResult = () => {
    const data = {
      session: { prompt, slm: slm?.name, model: selectedModel },
      session_insights: insights,
      answer: result?.answer,
      trace: trace?.steps,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'orchestrator-result.json'
    a.click()
  }

  const downloadTxt = () => {
    const blob = new Blob([result?.answer || ''], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'orchestrator-result.txt'
    a.click()
  }

  return (
    <div>
      <div className="bg-card border-b border-dborder px-0 py-7 mb-7">
        <div className="max-w-[1100px] mx-auto px-12">
          <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-t3 mb-1.5 flex items-center gap-2">
            <span className="inline-block w-4 h-px bg-accent" />
            Step 4 of 4 · Complete
          </div>
          <div className="font-sora text-2xl font-semibold text-t1">Results & Intelligence Report</div>
          <div className="text-[12px] text-t2 mt-1">Full process trace, session insights & downloadable output</div>
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-12">
        <Pyramid />

        {/* Loading state */}
        {isRunning && (
          <div className="flex items-center gap-3 p-5 bg-purple/10 border border-purple/30 rounded-card mb-6">
            <div className="flex gap-1">
              {[0, .22, .44].map((d) => (
                <span key={d} className="w-2 h-2 rounded-full bg-purple animate-blink" style={{ animationDelay: `${d}s` }} />
              ))}
            </div>
            <span className="text-[12px] text-purple">Executing full pipeline — GraphRAG retrieval → SLM routing → LLM generation…</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="p-4 bg-coral/10 border border-coral/30 rounded-card mb-6 text-[12px] text-coral">
            Error: {error}
          </div>
        )}

        {/* Process trace */}
        {trace?.steps?.length > 0 && (
          <>
            <div className="sect">Process trace</div>
            <div className="mb-6">
              {trace.steps.map((step, i) => {
                const style = TRACE_STYLES[step.event] || TRACE_STYLES.response_generated
                return (
                  <TraceStep
                    key={i}
                    event={step.event}
                    description={step.description}
                    elapsed={step.elapsed}
                    color={style.color}
                    icon={style.icon}
                  />
                )
              })}
            </div>
          </>
        )}

        {/* Session insights */}
        {insights && (
          <>
            <div className="sect">Session insights</div>
            <div className="grid grid-cols-4 gap-3.5 mb-6">
              <div className="mcard" style={{ '--bar-color': '#16a34a' }}>
                <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-gg" />
                <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Tokens used</div>
                <div className="font-sora text-[26px] font-bold text-t1 leading-none">{insights.tokens_used?.toLocaleString()}</div>
                <div className="text-[11px] text-t2 mt-1">vs ~{insights.tokens_saved ? (insights.tokens_used + insights.tokens_saved).toLocaleString() : '—'} base</div>
                <div className="pill-g mt-2">↓ {insights.token_reduction_pct}%</div>
              </div>
              <div className="mcard" style={{ '--bar-color': '#0d9488' }}>
                <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-teal" />
                <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Cost</div>
                <div className="font-sora text-[26px] font-bold text-t1 leading-none">${insights.cost_usd}</div>
                <div className="text-[11px] text-t2 mt-1">via {insights.model}</div>
                <div className="pill-g mt-2">efficient</div>
              </div>
              <div className="mcard" style={{ '--bar-color': '#4f46e5' }}>
                <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-accent" />
                <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">SLM used</div>
                <div className="font-sora text-[18px] font-bold text-t1 leading-none truncate">{insights.slm_used}</div>
                <div className="text-[11px] text-t2 mt-1">from registry</div>
                <div className="pill-b mt-2">Reused</div>
              </div>
              <div className="mcard" style={{ '--bar-color': '#d97706' }}>
                <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-amber" />
                <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Latency</div>
                <div className="font-sora text-[26px] font-bold text-t1 leading-none">{insights.execution_time}s</div>
                <div className="text-[11px] text-t2 mt-1">end-to-end</div>
                <div className="pill-t mt-2">Fast</div>
              </div>
            </div>
          </>
        )}

        {/* Output */}
        {result?.answer && (
          <>
            <div className="sect">Output</div>
            <div className="bg-card2 border border-dborder rounded-card p-5">
              <div className="text-[12px] leading-relaxed text-t2 whitespace-pre-wrap">
                {result.answer}
              </div>
              <div className="flex items-center justify-between mt-3.5 pt-3 border-t border-dborder">
                <span className="text-[11px] text-t3">
                  {insights?.model} · {slm?.name} · {insights?.tokens_used} tokens · ${insights?.cost_usd}
                </span>
                <div className="flex gap-2">
                  <button className="btn btn-sm" onClick={downloadTxt}>↓ TXT</button>
                  <button className="btn btn-p btn-sm" onClick={downloadResult}>↓ JSON</button>
                </div>
              </div>
            </div>
          </>
        )}

        <div className="mt-6">
          <div className="sect">Reliability and relationship confidence</div>
          <div className="grid grid-cols-4 gap-3.5 mb-6">
            <div className="mcard" style={{ '--bar-color': '#0d9488' }}>
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-teal" />
              <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">EDA evidence</div>
              <div className="font-sora text-[26px] font-bold text-t1 leading-none">{eda.relationship_evidence_count ?? 0}</div>
              <div className="text-[11px] text-t2 mt-1">relationship evidence rows</div>
              <div className="pill-b mt-2">EDA-backed</div>
            </div>
            <div className="mcard" style={{ '--bar-color': '#2563eb' }}>
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-blue" />
              <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">High-risk edges</div>
              <div className="font-sora text-[26px] font-bold text-t1 leading-none">{((trust.high_risk_edge_ratio ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-[11px] text-t2 mt-1">low confidence edge share</div>
              <div className="pill-t mt-2">Trust</div>
            </div>
            <div className="mcard" style={{ '--bar-color': '#e11d48' }}>
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-coral" />
              <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Contradictions</div>
              <div className="font-sora text-[26px] font-bold text-t1 leading-none">{((trust.contradiction_ratio ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-[11px] text-t2 mt-1">edge contradiction ratio</div>
              <div className="pill-a mt-2">Validation</div>
            </div>
            <div className="mcard" style={{ '--bar-color': '#d97706' }}>
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t bg-amber" />
              <div className="text-[10px] text-t3 font-semibold uppercase tracking-widest mb-2">Calibration error</div>
              <div className="font-sora text-[26px] font-bold text-t1 leading-none">{((trust.calibration_proxy_error ?? 0) * 100).toFixed(1)}%</div>
              <div className="text-[11px] text-t2 mt-1">confidence reliability proxy</div>
              <div className="pill-g mt-2">Accuracy</div>
            </div>
          </div>
        </div>

        {/* Sources */}
        {result?.sources?.length > 0 && (
          <div className="mt-5">
            <div className="sect">Source chunks used</div>
            {result.sources.slice(0, 3).map((chunk, i) => (
              <div key={i} className="bg-card border border-dborder rounded-sm px-4 py-3 mb-2">
                <div className="text-[10px] text-t3 mb-1">Chunk #{chunk.chunk_idx} · score {chunk.score?.toFixed(3)} · {chunk.file_id?.slice(0, 8)}…</div>
                <div className="text-[11px] text-t2 leading-relaxed line-clamp-3">{chunk.text?.slice(0, 200)}…</div>
              </div>
            ))}
          </div>
        )}

        {/* Wiki explorer */}
        <div className="mt-6">
          <div className="sect">Nano wiki explorer</div>
          <div className="card mb-3.5">
            <div className="flex items-center gap-2.5">
              <input
                className="prompt-box min-h-0 h-10 py-2 text-[12px]"
                style={{ resize: 'none' }}
                placeholder="Search wiki pages by entity or type…"
                value={wikiSearch}
                onChange={(e) => setWikiSearch(e.target.value)}
              />
              <button className="btn btn-sm" onClick={() => refreshWiki(wikiSearch)} disabled={wikiLoading}>
                {wikiLoading ? 'Loading…' : 'Search'}
              </button>
            </div>
            <div className="text-[11px] text-t3 mt-2">
              Pages: {wikiPages.length} · Pending merge reviews: {wikiReviews.length}
            </div>
          </div>

          <div className="grid grid-cols-12 gap-3.5">
            <div className="col-span-5">
              <div className="card">
                <div className="text-[11px] text-t3 mb-2.5 uppercase tracking-wider font-semibold">Wiki pages</div>
                {wikiPages.length === 0 && (
                  <div className="text-[12px] text-t2">No pages found for the current filter.</div>
                )}
                {wikiPages.map((p) => {
                  const active = selectedWikiPage?.canonical_id === p.canonical_id
                  return (
                    <button
                      key={p.canonical_id}
                      className={`model-row w-full text-left ${active ? 'chosen' : ''}`}
                      onClick={() => selectWikiPage(p.canonical_id)}
                    >
                      <div className="flex-1">
                        <div className="text-[12px] text-t1 font-semibold truncate">{p.title}</div>
                        <div className="text-[10px] text-t3 mt-1">
                          {p.entity_type} · v{p.version} · {p.source_files?.length || 0} source files
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="col-span-7">
              <div className="card">
                {!selectedWikiPage && <div className="text-[12px] text-t2">Select a wiki page to inspect provenance.</div>}
                {selectedWikiPage && (
                  <>
                    <div className="flex items-center justify-between mb-2.5">
                      <div>
                        <div className="text-[16px] font-semibold text-t1">{selectedWikiPage.title}</div>
                        <div className="text-[11px] text-t3">{selectedWikiPage.entity_type} · version {selectedWikiPage.version}</div>
                      </div>
                      <span className="pill-b">{selectedWikiPage.citation_coverage?.facts_with_citations || 0}/{selectedWikiPage.citation_coverage?.total_facts || 0} cited facts</span>
                    </div>

                    <div className="text-[12px] text-t2 leading-relaxed mb-3">{selectedWikiPage.summary}</div>

                    <div className="text-[11px] text-t3 mb-1 uppercase tracking-wider font-semibold">Key facts</div>
                    {(selectedWikiPage.key_facts || []).slice(0, 8).map((fact, i) => (
                      <div key={i} className="bg-bg4 border border-dborder rounded-sm px-3 py-2 mb-2">
                        <div className="text-[12px] text-t1">{fact.claim}</div>
                        <div className="text-[10px] text-t3 mt-1">
                          confidence {Math.round((fact.confidence || 0) * 100)}% · citations {fact.citations?.length || 0}
                        </div>
                        {(fact.citations || []).slice(0, 1).map((c, ci) => (
                          <div key={ci} className="text-[10px] text-t2 mt-1 line-clamp-2">
                            {c.file_id?.slice(0, 8)}… · chunk {c.chunk_idx ?? '-'} · {c.excerpt || 'no excerpt'}
                          </div>
                        ))}
                      </div>
                    ))}

                    <div className="text-[11px] text-t3 mt-3 mb-1 uppercase tracking-wider font-semibold">Provenance</div>
                    {(selectedWikiPage.sources || []).slice(0, 10).map((s, i) => (
                      <div key={i} className="db-chip w-full justify-start mb-1.5">
                        <span className="text-t1">{s.file_id?.slice(0, 8)}…</span>
                        <span className="text-t3">chunk {s.chunk_idx ?? '-'}</span>
                        <span className="text-t2 truncate">{s.excerpt || 'no excerpt'}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Merge review queue */}
        <div className="mt-6">
          <div className="sect">Merge review queue</div>
          <div className="card">
            {wikiReviews.length === 0 && (
              <div className="text-[12px] text-t2">No pending low-confidence merges.</div>
            )}
            {wikiReviews.map((r) => (
              <div key={r.review_id} className="bg-bg4 border border-dborder rounded-sm p-3 mb-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-[12px] text-t1 font-semibold">
                      {r.node_label} ↔ {r.candidate_label}
                    </div>
                    <div className="text-[10px] text-t3 mt-1">
                      score {Math.round((r.score || 0) * 100)}% · {r.node_canonical_id?.slice(0, 10)}… → {r.candidate_canonical_id?.slice(0, 10)}…
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-sm"
                      onClick={() => applyReview(r.review_id, 'reject')}
                      disabled={wikiReviewUpdating}
                    >
                      Reject
                    </button>
                    <button
                      className="btn btn-p btn-sm"
                      onClick={() => applyReview(r.review_id, 'approve')}
                      disabled={wikiReviewUpdating}
                    >
                      Approve merge
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="h-6" />
        <div className="grid grid-cols-2 gap-3">
          <button className="btn" onClick={() => setStep(0)}>← Dashboard</button>
          <button className="btn btn-p" onClick={startNewSession}>New session →</button>
        </div>
        <div className="h-8" />
      </div>
    </div>
  )
}
