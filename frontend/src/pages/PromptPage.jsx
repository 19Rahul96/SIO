import { useState } from 'react'
import api from '../services/api'
import useStore from '../store'

function ScoreRing({ score }) {
  const r = 34
  const circ = 2 * Math.PI * r
  const pct = Math.min(100, Math.max(0, score)) / 100
  const offset = circ * (1 - pct)
  const color = score >= 80 ? '#16a34a' : score >= 50 ? '#d97706' : '#e11d48'

  return (
    <svg width="88" height="88" viewBox="0 0 88 88">
      <circle cx="44" cy="44" r={r} fill="none" stroke="#eef1f7" strokeWidth="10" />
      <circle cx="44" cy="44" r={r} fill="none" stroke={color} strokeWidth="10"
        strokeDasharray={circ} strokeDashoffset={offset}
        transform="rotate(-90 44 44)" strokeLinecap="round" />
      <text x="44" y="41" textAnchor="middle" fontSize="16" fontWeight="700" fill="#1a1d2e" fontFamily="Sora,sans-serif">{score > 0 ? Math.round(score) : '—'}</text>
      <text x="44" y="53" textAnchor="middle" fontSize="8" fill="#8e97b8" fontFamily="DM Sans,sans-serif">/100</text>
    </svg>
  )
}

function RoutingPath({ tier, desc, isActive, isWarn }) {
  const cls = isActive
    ? 'border-gg/40 bg-gg/5 text-gg'
    : isWarn
    ? 'border-amber/40 bg-amber/5 text-amber'
    : 'border-dborder bg-bg4 text-t3 opacity-50'
  return (
    <div className={`flex-1 p-3 rounded-sm border ${cls} text-[11px] font-medium`}>
      <div className="text-[10px] font-bold uppercase tracking-wider mb-1">{tier}</div>
      <div className="opacity-85">{desc}</div>
    </div>
  )
}

function Pyramid() {
  return (
    <div className="flex flex-col items-center gap-1 pb-7">
      {[
        { label: 'Result', w: 80 },
        { label: 'Model select', w: 160 },
        { label: '▶ SLM engine — active', w: 250, active: true },
        { label: 'Data + GraphRAG — done ✓', w: 360, done: true },
      ].map((t, i) => (
        <div key={i} className={`pyramid-step ${t.active ? 'pyramid-step-active' : t.done ? 'pyramid-step-done' : ''}`} style={{ width: t.w }}>
          {t.label}
        </div>
      ))}
    </div>
  )
}

export default function PromptPage() {
  const { prompt, setPrompt, setAnalyseResult, slmResult, decisionData, uploadedFileIds, setStep, isAnalysing, setAnalysing } = useStore()
  const [thinkState, setThinkState] = useState('idle') // idle | thinking | done

  const handleAnalyse = async () => {
    if (!prompt.trim()) return
    setThinkState('thinking')
    setAnalysing(true)
    try {
      const res = await api.analyse(prompt.trim(), uploadedFileIds)
      setAnalyseResult(res)
      setThinkState('done')
    } catch (e) {
      setThinkState('idle')
      console.error(e)
    } finally {
      setAnalysing(false)
    }
  }

  const slm = slmResult?.slm
  const score = slmResult?.score ?? 0
  const decision = slmResult?.decision ?? ''

  const thinkBg = thinkState === 'done'
    ? 'bg-gg/10 border-gg/30 text-gg'
    : thinkState === 'thinking'
    ? 'bg-amber/10 border-amber/30 text-amber'
    : 'bg-purple/10 border-purple/30 text-purple'

  const thinkMsg = thinkState === 'done'
    ? `✓ Route decided: ${decision === 'reuse' ? 'Reuse path' : decision === 'modify' ? 'Modify path' : 'Create new SLM'} — ${slm?.name} — Token saving: ~${decisionData?.token_saving_pct ?? 0}%`
    : thinkState === 'thinking'
    ? 'Scanning SLM library… comparing embeddings against all trained models'
    : 'Internal GPT scans & routes automatically — no manual SLM selection needed'

  const decisionBadge = decision === 'reuse'
    ? { text: '✓ Route: Reuse SLM', cls: 'bg-gg/10 text-gg border-gg/30' }
    : decision === 'modify'
    ? { text: '⚡ Route: Modify SLM', cls: 'bg-amber/10 text-amber border-amber/30' }
    : decision === 'create'
    ? { text: '+ Route: New SLM Created', cls: 'bg-purple/10 text-purple border-purple/30' }
    : null

  return (
    <div>
      <div className="bg-card border-b border-dborder px-0 py-7 mb-7">
        <div className="max-w-[1100px] mx-auto px-12">
          <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-t3 mb-1.5 flex items-center gap-2">
            <span className="inline-block w-4 h-px bg-accent" />
            Step 2 of 4 · SLM engine
          </div>
          <div className="font-sora text-2xl font-semibold text-t1">Prompt & SLM intelligence</div>
          <div className="text-[12px] text-t2 mt-1">
            Internal GPT scores your request against the SLM library and decides the optimal routing path
          </div>
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-12">
        <Pyramid />

        <div className="sect">Your request</div>
        <textarea
          className="prompt-box"
          placeholder="Describe what you need from your data…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
        />
        <div className="flex justify-between items-center mt-2.5">
          <span className="text-[11px] text-t3">Internal GPT scans & routes automatically — no manual SLM selection needed</span>
          <button
            className={`btn btn-sm ${isAnalysing ? 'opacity-60' : 'btn-p'}`}
            onClick={handleAnalyse}
            disabled={isAnalysing || !prompt.trim()}
          >
            {isAnalysing ? 'Scanning…' : thinkState === 'done' ? '✓ Analysed' : 'Analyse ↗'}
          </button>
        </div>

        <div className="h-4" />

        {/* Thinking bar */}
        <div className={`thinking-bar ${thinkBg}`}>
          {thinkState !== 'done' && (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0 animate-blink" />
              <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0 animate-blink" style={{ animationDelay: '.22s' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0 animate-blink" style={{ animationDelay: '.44s' }} />
            </>
          )}
          <span>{thinkMsg}</span>
        </div>

        <div className="h-4" />

        {/* SLM result block */}
        {slm && (
          <div className="bg-card2 border border-dborder rounded-card overflow-hidden">
            {/* Header */}
            <div className="px-5 py-4 border-b border-dborder bg-bg4">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-t1">SLM routing decision</span>
                {decisionBadge && (
                  <span className={`ft-badge px-2.5 py-1 text-[10px] border ${decisionBadge.cls}`}>{decisionBadge.text}</span>
                )}
              </div>
              <div className="text-[11px] text-t2 mt-1">
                {score >= 80 ? 'Score above 80 threshold — existing SLM selected automatically'
                  : score >= 50 ? 'Score 50–79 — SLM modified with new context and re-saved'
                  : 'Score below 50 — new SLM created and saved to registry'}
              </div>
            </div>

            {/* Score ring + paths */}
            <div className="px-5 py-5 border-b border-dborder">
              <div className="flex items-center gap-4 mb-4">
                <ScoreRing score={score} />
                <div>
                  <div className="text-[14px] font-semibold text-t1 mb-1">
                    Match score: {Math.round(score)} — {slm.name}
                  </div>
                  <div className="text-[11px] text-t2 leading-relaxed">
                    {decision === 'reuse'
                      ? `High confidence match. Existing SLM reused directly with latest GraphRAG context. Persisted for future prompts.`
                      : decision === 'modify'
                      ? `Moderate match. SLM parameters blended with new domain context. Updated registry entry saved.`
                      : `No sufficient match. New SLM created from this prompt embedding and saved to registry for future reuse.`}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <RoutingPath tier="Score ≥ 80 — Active" desc="Reuse existing SLM as-is. Update with new GraphRAG context. Highest token efficiency." isActive={decision === 'reuse'} />
                <RoutingPath tier="Score 50–79 — Active" desc="Modify existing SLM: merge new domain knowledge. Internal GPT auto-triggers." isWarn={decision === 'modify'} isActive={decision === 'modify'} />
                <RoutingPath tier="Score < 50 — Active" desc="Create new SLM from GraphRAG. Internal GPT auto-builds & saves to library." isActive={decision === 'create'} />
              </div>
            </div>

            {/* SLM status */}
            <div className={`flex items-start gap-3.5 px-5 py-4 border-b border-dborder ${decision === 'reuse' ? 'bg-gg/5' : decision === 'create' ? 'bg-purple/5' : 'bg-amber/5'}`}>
              <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 border ${decision === 'reuse' ? 'bg-gg/10 border-gg/30' : decision === 'create' ? 'bg-purple/10 border-purple/30' : 'bg-amber/10 border-amber/30'}`}>
                {decision === 'reuse' ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M13.5 4L6.5 11.5 2.5 7.5" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                ) : decision === 'create' ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" /></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8h12M8 2l4 6-4 6" stroke="#d97706" strokeWidth="1.5" strokeLinecap="round" /></svg>
                )}
              </div>
              <div>
                <div className={`text-[12px] font-semibold mb-1 ${decision === 'reuse' ? 'text-gg' : decision === 'create' ? 'text-purple' : 'text-amber'}`}>
                  {decision === 'reuse' ? `Reusing: ${slm.name}` : decision === 'create' ? `Created: ${slm.name}` : `Modified: ${slm.name}`}
                </div>
                <div className="text-[11px] text-t2 leading-relaxed">
                  {Math.round(score)}% confidence · domain: {slm.parameters?.domain || 'general'} · saved to registry for future prompts
                </div>
              </div>
            </div>

            {/* Stats row */}
            <div className="flex">
              {[
                ['Parameters', `${slm.parameters?.context_window?.toLocaleString() || '2048'}`],
                ['Match score', `${Math.round(score)}%`],
                ['Token saving', `↓ ${decisionData?.token_saving_pct ?? 0}%`],
                ['Usage count', `${slm.usage_count || 1}×`],
              ].map(([k, v], i) => (
                <div key={k} className="flex-1 py-3 px-4 text-center border-r border-dborder last:border-r-0">
                  <div className="font-sora text-[18px] font-bold text-t1">{v}</div>
                  <div className="text-[10px] text-t3 mt-1">{k}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="h-6" />
        <div className="grid grid-cols-2 gap-3">
          <button className="btn" onClick={() => setStep(1)}>← Back</button>
          <button className="btn btn-p" onClick={() => setStep(3)} disabled={!slm}>
            Proceed to model select →
          </button>
        </div>
        <div className="h-8" />
      </div>
    </div>
  )
}
