import { useEffect, useRef, useState } from 'react'
import api from '../services/api'
import useStore from '../store'

function Pyramid() {
  return (
    <div className="flex flex-col items-center gap-1 pb-7">
      {[
        { label: 'Result', w: 80 },
        { label: '▶ Model select — active', w: 160, active: true },
        { label: 'SLM engine — done ✓', w: 250, done: true },
        { label: 'Data + GraphRAG — done ✓', w: 360, done: true },
      ].map((t, i) => (
        <div key={i} className={`pyramid-step ${t.active ? 'pyramid-step-active' : t.done ? 'pyramid-step-done' : ''}`} style={{ width: t.w }}>
          {t.label}
        </div>
      ))}
    </div>
  )
}

function ModelRow({ rec, isChosen, onSelect }) {
  const model = rec.model
  const colors = {
    'claude-haiku-4-5-20251001': '#16a34a',
    'claude-sonnet-4-6': '#4f46e5',
    'gpt-4o-mini': '#7c3aed',
    'gpt-4o': '#e11d48',
    'gemini-2.0-flash': '#d97706',
  }
  const dotColor = colors[model.id] || '#8e97b8'

  return (
    <div
      className={`model-row ${isChosen ? 'chosen' : ''}`}
      onClick={() => onSelect(model.id)}
    >
      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: dotColor }} />
      <div className="flex-1">
        <div className={`text-[12px] font-medium ${isChosen ? 'text-teal' : 'text-t1'}`}>{model.name}</div>
        <div className="text-[10px] text-t3 mt-0.5">{rec.recommendation} · est. ${rec.estimated_cost}</div>
      </div>
      <span className={`text-[13px] font-bold mr-1 ${rec.score >= 80 ? 'text-gg' : rec.score >= 60 ? 'text-t2' : 'text-coral'}`}>
        {rec.score}
      </span>
      <span className="text-[10px] text-t3 mr-2">pts</span>
      <span
        className={`ft-badge px-2 py-0.5 text-[10px] border ${
          isChosen ? 'bg-gg/10 text-gg border-gg/30' : 'bg-bg4 text-t3 border-dborder'
        }`}
      >
        {isChosen ? '✓ Chosen' : 'Alt'}
      </span>
    </div>
  )
}

function PipelineSVG({ files, slm, topModel, score }) {
  const fileColors = { PDF: '#e11d48', DOCX: '#7c3aed', XLSX: '#0d9488', CSV: '#d97706', TXT: '#2563eb', DB: '#2563eb' }
  const displayFiles = files.slice(0, 5)

  return (
    <svg viewBox="0 0 960 500" xmlns="http://www.w3.org/2000/svg" style={{ background: '#f4f6fa', borderRadius: 10, width: '100%', display: 'block', border: '1px solid #dde2ee' }}>
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M1 2L8 5L1 8" fill="none" stroke="#c8d0e3" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
        <marker id="arr-g" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M1 2L8 5L1 8" fill="none" stroke="#16a34a" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
        <marker id="arr-a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M1 2L8 5L1 8" fill="none" stroke="#4f46e5" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
      </defs>

      <line x1="100" y1="250" x2="860" y2="250" stroke="#eef1f7" strokeWidth="2" />

      {/* Data sources → GraphRAG */}
      {[130, 195, 250, 310, 370].slice(0, Math.max(1, displayFiles.length)).map((y, i) => (
        <path key={i} d={`M 178 ${y} Q 225 ${y} 260 ${250 + (y - 250) * 0.3}`} fill="none" stroke="#dde2ee" strokeWidth="1.2" markerEnd="url(#arr)" />
      ))}
      <path d="M 338 250 L 398 250" fill="none" stroke="#16a34a" strokeWidth="1.8" markerEnd="url(#arr-g)" strokeDasharray="4 3" />
      <path d="M 478 140 Q 478 190 478 210" fill="none" stroke="#4f46e5" strokeWidth="1.2" markerEnd="url(#arr-a)" />
      <path d="M 558 250 L 618 250" fill="none" stroke="#16a34a" strokeWidth="1.8" markerEnd="url(#arr-g)" />
      <path d="M 698 225 Q 740 190 762 175" fill="none" stroke="#16a34a" strokeWidth="2" markerEnd="url(#arr-g)" />
      <path d="M 700 250 L 762 250" fill="none" stroke="#dde2ee" strokeWidth="1" markerEnd="url(#arr)" />
      <path d="M 698 272 Q 738 305 762 320" fill="none" stroke="#dde2ee" strokeWidth="1" markerEnd="url(#arr)" />
      <path d="M 842 165 Q 880 165 900 220" fill="none" stroke="#16a34a" strokeWidth="2" markerEnd="url(#arr-g)" />

      {/* Data source nodes */}
      <text x="122" y="100" textAnchor="middle" fontSize="9" fontWeight="600" fill="#8e97b8" fontFamily="DM Sans,sans-serif" letterSpacing="1">DATA SOURCES</text>
      {displayFiles.length === 0 ? (
        [['PDF', '#e11d48', 130], ['DOCX', '#7c3aed', 195], ['XLSX', '#0d9488', 250]].map(([ext, c, y]) => (
          <g key={ext}>
            <rect x="66" y={y - 18} width="112" height="36" rx="8" fill="#ffffff" stroke={`${c}55`} strokeWidth="1" />
            <rect x="66" y={y - 18} width="3" height="36" rx="1" fill={c} />
            <text x="80" y={y - 5} fontSize="9" fontWeight="600" fill={c} fontFamily="DM Sans,sans-serif">{ext}</text>
            <text x="80" y={y + 8} fontSize="8.5" fill="#5a6280" fontFamily="DM Sans,sans-serif">Sample file</text>
          </g>
        ))
      ) : (
        displayFiles.map((f, i) => {
          const y = [130, 195, 250, 310, 370][i]
          const c = fileColors[f.ext] || '#2563eb'
          return (
            <g key={f.file_id}>
              <rect x="66" y={y - 18} width="112" height="36" rx="8" fill="#ffffff" stroke={`${c}55`} strokeWidth="1" />
              <rect x="66" y={y - 18} width="3" height="36" rx="1" fill={c} />
              <text x="80" y={y - 5} fontSize="9" fontWeight="600" fill={c} fontFamily="DM Sans,sans-serif">{f.ext}</text>
              <text x="80" y={y + 8} fontSize="8.5" fill="#5a6280" fontFamily="DM Sans,sans-serif">{(f.filename || '').slice(0, 16)}</text>
            </g>
          )
        })
      )}

      {/* GraphRAG node */}
      <ellipse cx="298" cy="250" rx="38" ry="46" fill="#fffbeb" stroke="rgba(217,119,6,.4)" strokeWidth="1.5" />
      <text x="298" y="244" textAnchor="middle" fontSize="11" fontWeight="700" fill="#d97706" fontFamily="Sora,sans-serif">Graph</text>
      <text x="298" y="258" textAnchor="middle" fontSize="11" fontWeight="700" fill="#d97706" fontFamily="Sora,sans-serif">RAG</text>

      {/* SLM Engine */}
      <rect x="398" y="214" width="160" height="72" rx="12" fill="#fff1f2" stroke="rgba(225,29,72,.5)" strokeWidth="1.5" />
      <rect x="398" y="214" width="160" height="72" rx="12" fill="none" stroke="rgba(225,29,72,.15)" strokeWidth="8" />
      <text x="478" y="238" textAnchor="middle" fontSize="10" fontWeight="700" fill="#e11d48" fontFamily="Sora,sans-serif">SLM Engine</text>
      <text x="478" y="252" textAnchor="middle" fontSize="9" fill="#5a6280" fontFamily="DM Sans,sans-serif">Internal GPT</text>
      <text x="478" y="264" textAnchor="middle" fontSize="9" fill="#5a6280" fontFamily="DM Sans,sans-serif">Score: {Math.round(score)}/100</text>
      <text x="478" y="278" textAnchor="middle" fontSize="8" fill="#16a34a" fontFamily="DM Sans,sans-serif">→ {score >= 80 ? 'Reuse SLM' : score >= 50 ? 'Modify SLM' : 'New SLM'}</text>

      {/* SLM Library */}
      <rect x="428" y="90" width="100" height="44" rx="9" fill="#f5f3ff" stroke="rgba(124,58,237,.4)" strokeWidth="1" />
      <text x="478" y="107" textAnchor="middle" fontSize="9" fontWeight="700" fill="#7c3aed" fontFamily="Sora,sans-serif">SLM Library</text>
      <text x="478" y="120" textAnchor="middle" fontSize="8" fill="#5a6280" fontFamily="DM Sans,sans-serif">{slm ? slm.name : 'No SLMs yet'}</text>
      <text x="478" y="132" textAnchor="middle" fontSize="8" fill="#16a34a" fontFamily="DM Sans,sans-serif">{slm ? '✓ matched' : 'ready'}</text>

      {/* Model Router */}
      <rect x="618" y="220" width="80" height="60" rx="10" fill="#f0fdf9" stroke="rgba(13,148,136,.4)" strokeWidth="1.5" />
      <text x="658" y="244" textAnchor="middle" fontSize="9" fontWeight="700" fill="#0d9488" fontFamily="Sora,sans-serif">Model</text>
      <text x="658" y="257" textAnchor="middle" fontSize="9" fontWeight="700" fill="#0d9488" fontFamily="Sora,sans-serif">Router</text>
      <text x="658" y="270" textAnchor="middle" fontSize="8" fill="#8e97b8" fontFamily="DM Sans,sans-serif">{topModel ? `${topModel.score} pts` : '—'}</text>

      {/* Chosen model */}
      <rect x="762" y="145" width="120" height="40" rx="8" fill="#f0fdf4" stroke="rgba(22,163,74,.5)" strokeWidth="1.5" />
      <text x="822" y="160" textAnchor="middle" fontSize="9" fontWeight="700" fill="#16a34a" fontFamily="Sora,sans-serif">{topModel?.model?.name || 'claude-haiku-4-5'}</text>
      <text x="822" y="174" textAnchor="middle" fontSize="8" fill="#5a6280" fontFamily="DM Sans,sans-serif">{slm ? `+ ${slm.name}` : '+ SLM'}</text>

      {/* Alt models */}
      <rect x="762" y="230" width="120" height="34" rx="8" fill="#ffffff" stroke="#dde2ee" strokeWidth="1" />
      <text x="822" y="251" textAnchor="middle" fontSize="9" fill="#8e97b8" fontFamily="DM Sans,sans-serif">gpt-4o-mini</text>
      <rect x="762" y="305" width="120" height="34" rx="8" fill="#ffffff" stroke="#dde2ee" strokeWidth="1" />
      <text x="822" y="326" textAnchor="middle" fontSize="9" fill="#8e97b8" fontFamily="DM Sans,sans-serif">gemini-2.0-flash</text>
      <text x="822" y="134" textAnchor="middle" fontSize="9" fontWeight="600" fill="#8e97b8" fontFamily="DM Sans,sans-serif" letterSpacing="1">MODELS</text>

      {/* Result node */}
      <ellipse cx="910" cy="250" rx="36" ry="40" fill="#eef0ff" stroke="rgba(79,70,229,.5)" strokeWidth="1.5" />
      <ellipse cx="910" cy="250" rx="36" ry="40" fill="none" stroke="rgba(79,70,229,.15)" strokeWidth="8" />
      <text x="910" y="246" textAnchor="middle" fontSize="10" fontWeight="700" fill="#7c3aed" fontFamily="Sora,sans-serif">Result</text>
      <path d="M 882 165 Q 920 165 930 212" fill="none" stroke="#16a34a" strokeWidth="1.8" markerEnd="url(#arr-g)" />

      {/* Token saving callout */}
      <rect x="840" y="395" width="100" height="44" rx="8" fill="#f0fdf4" stroke="rgba(22,163,74,.3)" strokeWidth="1" />
      <text x="890" y="413" textAnchor="middle" fontSize="8" fill="#8e97b8" fontFamily="DM Sans,sans-serif">Token saving</text>
      <text x="890" y="428" textAnchor="middle" fontSize="14" fontWeight="700" fill="#16a34a" fontFamily="Sora,sans-serif">↓ ~70%</text>
      <line x1="890" y1="395" x2="890" y2="292" stroke="#dde2ee" strokeWidth="1" strokeDasharray="3,3" />

      <text x="298" y="470" textAnchor="middle" fontSize="8" fill="#c8d0e3" fontFamily="DM Sans,sans-serif">KNOWLEDGE GRAPH</text>
      <text x="478" y="470" textAnchor="middle" fontSize="8" fill="#c8d0e3" fontFamily="DM Sans,sans-serif">SLM ROUTING</text>
      <text x="658" y="470" textAnchor="middle" fontSize="8" fill="#c8d0e3" fontFamily="DM Sans,sans-serif">MODEL SELECT</text>
      <text x="910" y="470" textAnchor="middle" fontSize="8" fill="#c8d0e3" fontFamily="DM Sans,sans-serif">OUTPUT</text>
    </svg>
  )
}

export default function ModelPage() {
  const { modelRecommendations, selectedModel, setSelectedModel, slmResult, decisionData, prompt, uploadedFileIds, setStep, setRunning } = useStore()
  const [graphData, setGraphData] = useState(null)
  const fileStatuses = useStore((s) => s.fileStatuses)

  useEffect(() => {
    api.getCanonicalGraph(uploadedFileIds)
      .then((canonical) => {
        if ((canonical?.nodes?.length || 0) > 0 || (canonical?.edges?.length || 0) > 0) {
          return canonical
        }
        return api.getGraph(uploadedFileIds)
      })
      .then(setGraphData)
      .catch(() => {})
  }, [uploadedFileIds.join(',')])

  const slm = slmResult?.slm
  const score = slmResult?.score ?? 0
  const topModel = modelRecommendations[0]

  const completedFiles = fileStatuses.filter((f) => f.status === 'completed')

  return (
    <div>
      <div className="bg-card border-b border-dborder px-0 py-7 mb-7">
        <div className="max-w-[1100px] mx-auto px-12">
          <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-t3 mb-1.5 flex items-center gap-2">
            <span className="inline-block w-4 h-px bg-accent" />
            Step 3 of 4 · Model selection
          </div>
          <div className="font-sora text-2xl font-semibold text-t1">Model Routing & Connection Map</div>
          <div className="text-[12px] text-t2 mt-1">
            System selects the optimal model and visualises how every component connects to deliver your result
          </div>
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-12">
        <Pyramid />

        <div className="sect">Available models — ranked by suitability</div>

        {modelRecommendations.length === 0 ? (
          <div className="text-center py-8 text-t3 text-[12px]">Run analysis on step 2 to get model recommendations</div>
        ) : (
          modelRecommendations.map((rec) => (
            <ModelRow
              key={rec.model.id}
              rec={rec}
              isChosen={selectedModel === rec.model.id}
              onSelect={setSelectedModel}
            />
          ))
        )}

        <div className="h-6" />

        {/* Intelligence connection map */}
        <div className="sect">Intelligence connection map — Mirofish view</div>
        <div className="bg-card border border-dborder rounded-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-dborder bg-bg4">
            <div>
              <div className="text-[13px] font-semibold text-t1">How everything connects to produce your result</div>
              <div className="text-[11px] text-t2 mt-0.5">Each node shows its role in the pipeline — hover to explore</div>
            </div>
            <span className="ft-badge bg-teal/10 text-teal border border-teal/30 px-2.5 py-1 text-[10px]">Live trace</span>
          </div>
          <div className="p-2">
            <PipelineSVG
              files={completedFiles}
              slm={slm}
              topModel={topModel}
              score={score}
            />
          </div>
        </div>

        <div className="h-6" />

        {/* Decision reasoning */}
        <div className="sect">Decision reasoning</div>
        <div className="card">
          <div className="grid grid-cols-3 mb-3.5">
            {[
              ['Task complexity', decisionData?.task_complexity ?? '—', '#4f46e5'],
              ['SLM confidence', decisionData ? `${Math.round(decisionData.slm_confidence)}%` : '—', '#16a34a'],
              ['Est. cost', decisionData ? `$${decisionData.estimated_cost}` : '—', '#0d9488'],
            ].map(([k, v, c], i) => (
              <div key={k} className={`text-center py-2.5 ${i > 0 ? 'border-l border-dborder' : ''}`}>
                <div className="font-sora text-[20px] font-bold" style={{ color: c }}>{v}</div>
                <div className="text-[10px] text-t3 mt-1">{k}</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-t2 leading-relaxed pt-3 border-t border-dborder">
            {decisionData?.reasoning || 'Run analysis on step 2 to see decision reasoning.'}
          </div>
        </div>

        <div className="h-6" />
        <div className="grid grid-cols-2 gap-3">
          <button className="btn" onClick={() => setStep(2)}>← Back</button>
          <button
            className="btn btn-p"
            onClick={() => setStep(4)}
            disabled={!slm || !selectedModel}
          >
            Run & view results →
          </button>
        </div>
        <div className="h-8" />
      </div>
    </div>
  )
}
