import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../services/api'
import useStore from '../store'
import ModeSelector from './inject/ModeSelector'
import RoleWorkflow from './inject/RoleWorkflow'
import DirectUpload from './inject/DirectUpload'
import GraphRAGViewer from '../components/GraphRAGViewer'
import EDAVisualsViewer from '../components/EDAVisualsViewer'

const TERMINAL_STATUSES = new Set(['completed', 'failed'])
const PIPELINE_KEYS = ['cleaned', 'chunked', 'entities_extracted', 'graph_built', 'indexed']
const DB_PIPELINE_KEYS = ['connecting', 'introspecting', 'profiling', 'graphify_running', 'merging', 'embedding']
const STUCK_THRESHOLD_SECONDS = 90

const EXT_COLORS = {
  PDF:  { bg: 'rgba(225,29,72,.08)',  color: '#e11d48', border: 'rgba(225,29,72,.25)' },
  DOCX: { bg: 'rgba(124,58,237,.08)', color: '#7c3aed', border: 'rgba(124,58,237,.25)' },
  XLSX: { bg: 'rgba(13,148,136,.08)', color: '#0d9488', border: 'rgba(13,148,136,.25)' },
  CSV:  { bg: 'rgba(217,119,6,.08)',  color: '#d97706', border: 'rgba(217,119,6,.25)' },
  TXT:  { bg: 'rgba(37,99,235,.08)',  color: '#2563eb', border: 'rgba(37,99,235,.25)' },
  DB:   { bg: 'rgba(37,99,235,.08)',  color: '#2563eb', border: 'rgba(37,99,235,.25)' },
}

function getExt(s) { return EXT_COLORS[s?.toUpperCase()] || EXT_COLORS.TXT }

function isDbRecord(file) {
  return (file?.ext || '').toUpperCase() === 'DB' || Boolean(file?.db_id)
}

function getStuckSeconds(file) {
  if (!file || TERMINAL_STATUSES.has(file.status)) return 0
  const lastUpdated = Number(file.updated_at || file.uploaded_at || 0)
  if (!lastUpdated) return 0
  const age = Math.max(0, Math.floor(Date.now() / 1000 - lastUpdated))
  return age > STUCK_THRESHOLD_SECONDS ? age : 0
}

function withStuckState(file) {
  const stuckSeconds = getStuckSeconds(file)
  return {
    ...file,
    stuck: stuckSeconds > 0,
    stuck_for_seconds: stuckSeconds,
  }
}

function StatusDot({ status, stuck = false }) {
  const done = status === 'completed'
  const processing = [
    'processing', 'cleaned', 'chunked', 'entities_extracted', 'graph_built',
    'connecting', 'introspecting', 'profiling', 'graphify_running', 'merging', 'embedding',
  ].includes(status)
  const failed = status === 'failed'
  if (stuck) return <><span className="inline-block w-2 h-2 rounded-full bg-coral mr-1.5 align-middle animate-pulse" /><span className="text-[11px] text-coral font-medium">Stuck</span></>
  if (done) return <><span className="inline-block w-2 h-2 rounded-full bg-gg mr-1.5 align-middle" /><span className="text-[11px] text-gg font-medium">GraphRAG ready</span></>
  if (failed) return <><span className="inline-block w-2 h-2 rounded-full bg-coral mr-1.5 align-middle" /><span className="text-[11px] text-coral font-medium">Failed</span></>
  if (processing) return <><span className="inline-block w-2 h-2 rounded-full bg-amber mr-1.5 align-middle animate-pulse" /><span className="text-[11px] text-amber font-medium capitalize">{status.replace('_', ' ')}</span></>
  return <><span className="inline-block w-2 h-2 rounded-full bg-dborder2 mr-1.5 align-middle" /><span className="text-[11px] text-t3 font-medium">Queued</span></>
}

function PipelineSteps({ steps = {}, status }) {
  const isDb = DB_PIPELINE_KEYS.some((k) => Object.prototype.hasOwnProperty.call(steps, k))
  const labels = isDb
    ? ['Connect', 'Introspect', 'Profile', 'Graphify', 'Merge', 'Embed']
    : ['Cleaned', 'Chunked', 'Entities', 'Graph built', 'Indexed']
  const keys = isDb ? DB_PIPELINE_KEYS : PIPELINE_KEYS
  const processing = [
    'processing', 'cleaned', 'chunked', 'entities_extracted', 'graph_built',
    'connecting', 'introspecting', 'profiling', 'graphify_running', 'merging', 'embedding',
  ].includes(status)

  return (
    <div className="flex flex-wrap gap-1">
      {keys.map((k, i) => {
        const done = steps[k]
        const isActive = !done && processing && keys.slice(0, i).every(pk => steps[pk])
        return (
          <span
            key={k}
            className={`apill ${done ? 'apill-done' : isActive ? 'apill-active' : ''}`}
          >
            {labels[i]}{isActive ? '…' : ''}
          </span>
        )
      })}
    </div>
  )
}

function Pyramid() {
  return (
    <div className="flex flex-col items-center gap-1 pb-7">
      {[
        { label: 'Result', w: 80 }, { label: 'Model select', w: 160 },
        { label: 'SLM engine', w: 250 },
        { label: '▶ Data + GraphRAG — active', w: 360, active: true },
      ].map((t, i) => (
        <div
          key={i}
          className={`pyramid-step ${t.active ? 'pyramid-step-active' : ''}`}
          style={{ width: t.w }}
        >
          {t.label}
        </div>
      ))}
    </div>
  )
}

function IngestionDetailModal({ file, onClose }) {
  const { updateFile } = useStore()
  const [liveFile, setLiveFile] = useState(file)

  useEffect(() => {
    setLiveFile(file)
  }, [file])

  useEffect(() => {
    if (!liveFile?.file_id) return
    if (TERMINAL_STATUSES.has(liveFile.status)) return

    const timer = setInterval(async () => {
      try {
        const latest = await api.getFileStatus(liveFile.file_id)
        setLiveFile(latest)
        updateFile(liveFile.file_id, latest)
      } catch {
        // Keep modal open with last known state.
      }
    }, 1500)

    return () => clearInterval(timer)
  }, [liveFile?.file_id, liveFile?.status, updateFile])

  if (!liveFile) return null

  const isDb = isDbRecord(liveFile)
  const stuckSeconds = getStuckSeconds(liveFile)
  const isStuck = stuckSeconds > 0
  const modalPipelineKeys = isDb ? DB_PIPELINE_KEYS : PIPELINE_KEYS

  const doneCount = modalPipelineKeys.filter((k) => liveFile.pipeline_steps?.[k]).length
  const progressPct = liveFile.status === 'completed'
    ? 100
    : Math.round((doneCount / modalPipelineKeys.length) * 100)

  const stepRows = isDb
    ? [
        { key: 'queued', label: 'DB job queued', done: true },
        { key: 'connecting', label: 'Database connection established', done: !!liveFile.pipeline_steps?.connecting },
        { key: 'introspecting', label: 'Schema introspection completed', done: !!liveFile.pipeline_steps?.introspecting },
        { key: 'profiling', label: 'Column profiling completed', done: !!liveFile.pipeline_steps?.profiling },
        { key: 'graphify_running', label: 'Graphify extraction completed', done: !!liveFile.pipeline_steps?.graphify_running },
        { key: 'merging', label: 'Merged into canonical graph', done: !!liveFile.pipeline_steps?.merging },
        { key: 'embedding', label: 'Schema embeddings indexed', done: !!liveFile.pipeline_steps?.embedding },
      ]
    : [
        { key: 'uploaded', label: 'File uploaded', done: true },
        { key: 'cleaned', label: 'Text cleaned', done: !!liveFile.pipeline_steps?.cleaned },
        { key: 'chunked', label: 'Chunks created', done: !!liveFile.pipeline_steps?.chunked },
        { key: 'entities_extracted', label: 'Entities and relationships extracted', done: !!liveFile.pipeline_steps?.entities_extracted },
        { key: 'graph_built', label: 'Graph built', done: !!liveFile.pipeline_steps?.graph_built },
        { key: 'indexed', label: 'Embeddings indexed', done: !!liveFile.pipeline_steps?.indexed },
      ]

  const isFailed = liveFile.status === 'failed'
  const isCompleted = liveFile.status === 'completed'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(10,12,22,.72)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-card2 border border-dborder rounded-card flex flex-col" style={{ width: '900px', maxWidth: '95vw', maxHeight: '88vh' }}>
        <div className="flex items-start justify-between px-6 py-4 border-b border-dborder">
          <div>
            <div className="font-sora text-[16px] font-semibold text-t1">Ingestion Pipeline Details</div>
            <div className="text-[11px] text-t3 mt-0.5">
              {liveFile.filename} · {liveFile.file_id?.slice(0, 8)}… · status: {liveFile.status}
            </div>
          </div>
          <button className="btn btn-sm" onClick={onClose}>✕ Close</button>
        </div>

        <div className="overflow-y-auto px-6 py-5 space-y-4">
          <div>
            <div className="flex items-center justify-between text-[11px] text-t2 mb-1.5">
              <span>Overall ingestion progress</span>
              <span>{progressPct}%</span>
            </div>
            <div className="prog-bar">
              <div className="prog-fill" style={{ width: `${progressPct}%` }} />
            </div>
            {isStuck && !isFailed && !isCompleted && (
              <div className="text-[11px] text-coral mt-2">
                No pipeline update for {stuckSeconds}s. The job may be stuck; use retry if it does not recover.
              </div>
            )}
            {isFailed && <div className="text-[11px] text-coral mt-2">Failed: {liveFile.error || 'Unknown error'}</div>}
            {isCompleted && <div className="text-[11px] text-gg mt-2">Completed successfully. {isDb ? 'Schema metadata and graph are ready.' : 'Graph and index are ready.'}</div>}
          </div>

          <div className="card">
            <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">Pipeline steps</div>
            <div className="space-y-2">
              {stepRows.map((s, i) => {
                const previousDone = i === 0 || stepRows.slice(1, i).every((x) => x.done)
                const active = !s.done && previousDone && !isFailed && !isCompleted && !isStuck
                return (
                  <div key={s.key} className="flex items-center gap-2.5 text-[12px]">
                    <span className={`w-2 h-2 rounded-full ${s.done ? 'bg-gg' : active ? 'bg-amber animate-pulse' : 'bg-dborder2'}`} />
                    <span className={s.done ? 'text-t1 font-medium' : active ? 'text-amber font-medium' : 'text-t3'}>
                      {s.label}{active ? '…' : ''}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3">
            <div className="mcard">
              <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Chunks</div>
              <div className="font-sora text-[20px] font-bold text-t1">{liveFile.chunks_count || 0}</div>
            </div>
            <div className="mcard">
              <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Entities</div>
              <div className="font-sora text-[20px] font-bold text-t1">{liveFile.entities_count || 0}</div>
            </div>
            <div className="mcard">
              <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Relations</div>
              <div className="font-sora text-[20px] font-bold text-t1">{liveFile.relations_count || 0}</div>
            </div>
            <div className="mcard">
              <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Canonical Nodes</div>
              <div className="font-sora text-[20px] font-bold text-t1">{liveFile.canonical_entities_count || 0}</div>
            </div>
          </div>

          {isDb && (
            <div className="grid grid-cols-3 gap-3">
              <div className="mcard">
                <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Schema tables</div>
                <div className="font-sora text-[20px] font-bold text-t1">{liveFile.schema_tables || 0}</div>
              </div>
              <div className="mcard">
                <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Profiled tables</div>
                <div className="font-sora text-[20px] font-bold text-t1">{liveFile.profiled_tables || 0}</div>
              </div>
              <div className="mcard">
                <div className="text-[10px] text-t3 uppercase tracking-wider mb-1">Graphify</div>
                <div className="font-sora text-[20px] font-bold text-t1">{liveFile.graphify_ok ? 'OK' : 'Fallback'}</div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="card">
              <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">Chunk Validation</div>
              <div className="text-[11px] text-t2 space-y-1">
                <div>Total words: {liveFile.chunk_validation_report?.total_words ?? '-'}</div>
                <div>Coverage: {liveFile.chunk_validation_report?.coverage_pct ?? '-'}%</div>
                <div>Overlap correctness: {liveFile.chunk_validation_report?.overlap_correctness_pct ?? '-'}%</div>
                <div>Data loss detected: {String(liveFile.chunk_validation_report?.data_loss_detected ?? false)}</div>
              </div>
            </div>

            <div className="card">
              <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">Schema / Resolution</div>
              <div className="text-[11px] text-t2 space-y-1">
                <div>Schema valid: {String(liveFile.schema_validation?.valid ?? false)}</div>
                <div>Schema errors: {liveFile.schema_validation?.error_count ?? 0}</div>
                <div>Merged entities: {liveFile.resolution_report?.merged_count ?? 0}</div>
                <div>Pending review: {liveFile.resolution_report?.pending_review_count ?? 0}</div>
              </div>
            </div>

            <div className="card">
              <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">Canonical Upsert</div>
              <div className="text-[11px] text-t2 space-y-1">
                <div>Nodes created: {liveFile.canonical_upsert?.nodes_created ?? 0}</div>
                <div>Nodes updated: {liveFile.canonical_upsert?.nodes_updated ?? 0}</div>
                <div>Edges created: {liveFile.canonical_upsert?.edges_created ?? 0}</div>
                <div>Edges updated: {liveFile.canonical_upsert?.edges_updated ?? 0}</div>
              </div>
            </div>

            <div className="card">
              <div className="text-[11px] text-t3 mb-2 uppercase tracking-wider font-semibold">Wiki Page Generation</div>
              <div className="text-[11px] text-t2 space-y-1">
                <div>Pages created: {liveFile.wiki_page_report?.pages_created ?? 0}</div>
                <div>Pages updated: {liveFile.wiki_page_report?.pages_updated ?? 0}</div>
                <div>Target nodes: {liveFile.wiki_page_report?.total_target_nodes ?? 0}</div>
                <div>Adapter: {liveFile.corpus_profile?.adapter || '-'}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function InjectPage() {
  const { fileStatuses, addFile, updateFile, setStep, injectMode } = useStore()
  const [retrying, setRetrying] = useState({})
  const [showGraph, setShowGraph] = useState(false)
  const [showEdaVisuals, setShowEdaVisuals] = useState(false)
  const [selectedFileForDetails, setSelectedFileForDetails] = useState(null)
  const pollingRef = useRef(null)

  const handleRetry = useCallback(async (fileId) => {
    setRetrying((r) => ({ ...r, [fileId]: true }))
    try {
      await api.retryFile(fileId)
    } catch (e) {
      console.error('Retry failed', e)
    } finally {
      setRetrying((r) => ({ ...r, [fileId]: false }))
    }
  }, [])

  useEffect(() => {
    const poll = async () => {
      try {
        const { files } = await api.getStatus()
        const { uploadedFileIds, sessionStartedAt, fileStatuses: knownFiles } = useStore.getState()
        const sessionFiles = files.filter((f) => {
          const isDb = (f.ext || '').toUpperCase() === 'DB' || Boolean(f.db_id)
          if (isDb) {
            const uploadedAt = Number(f.uploaded_at || 0)
            const recordId = f.file_id || f.db_id
            const known = knownFiles.some((s) => (s.file_id || s.db_id) === recordId)
            return uploadedAt >= sessionStartedAt || uploadedFileIds.includes(recordId) || known
          }
          const uploadedAt = Number(f.uploaded_at || 0)
          return uploadedAt >= sessionStartedAt || uploadedFileIds.includes(f.file_id)
        })

        const normalized = sessionFiles.map(withStuckState)

        normalized.forEach((f) => updateFile(f.file_id, f))
        normalized.forEach((f) => {
          if (!knownFiles.find((s) => s.file_id === f.file_id)) addFile(f)
        })
      } catch {}
    }
    poll()
    pollingRef.current = setInterval(poll, 2000)
    return () => clearInterval(pollingRef.current)
  }, [addFile, updateFile])

  const completed = fileStatuses.filter((f) => f.status === 'completed').length
  const completedFileIds = fileStatuses
    .filter((f) => f.status === 'completed' && !isDbRecord(f))
    .map((f) => f.file_id)
  const completedDbIds = fileStatuses
    .filter((f) => f.status === 'completed' && isDbRecord(f))
    .map((f) => f.db_id || f.file_id)
  const total = fileStatuses.length
  const overallPct = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div>
      <div className="bg-card border-b border-dborder px-0 py-7 mb-7">
        <div className="max-w-[1100px] mx-auto px-12">
          <div className="text-[10px] font-semibold uppercase tracking-[.12em] text-t3 mb-1.5 flex items-center gap-2">
            <span className="inline-block w-4 h-px bg-accent" />
            Step 1 of 4 · Foundation layer
          </div>
          <div className="font-sora text-2xl font-semibold text-t1">Data Injection & GraphRAG</div>
          <div className="text-[12px] text-t2 mt-1">
            Pick an entry mode — both converge on the same preprocessing & GraphRAG pipeline
          </div>
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-12">
        <Pyramid />

        {injectMode === 'selector' && <ModeSelector />}
        {injectMode === 'role' && <RoleWorkflow />}
        {injectMode === 'direct' && <DirectUpload />}

        <div className="h-4" />

        <div className="sect">Injected documents</div>
        <div className="overflow-x-auto border border-dborder rounded-card">
          <table className="w-full border-collapse" style={{ tableLayout: 'fixed', minWidth: 700 }}>
            <thead>
              <tr>
                {[['Document', '30%'], ['Type', '10%'], ['Role / domain', '14%'], ['Curation status', '16%'], ['Pipeline actions', '30%']].map(([h, w]) => (
                  <th key={h} className="text-[10px] font-semibold uppercase tracking-widest text-t3 px-3.5 py-3 text-left bg-bg4 border-b border-dborder" style={{ width: w }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fileStatuses.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-10 text-t3 text-[12px]">
                    No files uploaded yet — pick an entry mode above to get started
                  </td>
                </tr>
              ) : (
                fileStatuses.map((f) => {
                  const ec = getExt(f.ext)
                  const stuckSeconds = Number(f.stuck_for_seconds || 0)
                  return (
                    <tr
                      key={f.file_id}
                      className="border-b border-dborder last:border-b-0 hover:bg-bg4 transition-colors cursor-pointer"
                      onClick={() => setSelectedFileForDetails(f)}
                    >
                      <td className="px-3.5 py-3">
                        <div className="text-[12px] font-medium text-t1 truncate">{f.filename}</div>
                        <div className="text-[10px] text-t3 mt-0.5">
                          {f.size ? `${(f.size / 1024).toFixed(0)} KB` : '—'}
                          {f.entities_count > 0 && ` · ${f.entities_count} entities`}
                          {f.relations_count > 0 && ` · ${f.relations_count} relations`}
                        </div>
                      </td>
                      <td className="px-3.5 py-3">
                        <span className="ft-badge" style={{ background: ec.bg, color: ec.color, border: `1px solid ${ec.border}` }}>{f.ext || 'FILE'}</span>
                      </td>
                      <td className="px-3.5 py-3">
                        {f.role ? (
                          <div className="flex flex-col gap-0.5">
                            <span className="pill-b" style={{ alignSelf: 'flex-start' }}>{f.role}</span>
                            {f.domain && <span className="text-[10px] text-t3">{f.domain}</span>}
                          </div>
                        ) : (
                          <span className="text-[10px] text-t3">Direct</span>
                        )}
                      </td>
                      <td className="px-3.5 py-3 align-middle">
                        <StatusDot status={f.status} stuck={Boolean(f.stuck)} />
                      </td>
                      <td className="px-3.5 py-3">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            className="btn btn-sm"
                            style={{ padding: '2px 8px', fontSize: 11 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedFileForDetails(f)
                            }}
                            title="View ingestion details"
                          >
                            👁 Details
                          </button>
                          <PipelineSteps steps={f.pipeline_steps} status={f.status} />
                          {Boolean(f.stuck) && (
                            <span className="text-[10px] text-coral">
                              No update for {stuckSeconds}s
                            </span>
                          )}
                          {f.status === 'failed' && (
                            <button
                              className="btn btn-sm"
                              style={{ color: '#e11d48', borderColor: 'rgba(225,29,72,.4)', background: 'rgba(225,29,72,.08)', padding: '2px 10px', fontSize: 11 }}
                              disabled={retrying[f.file_id]}
                              onClick={(e) => {
                                e.stopPropagation()
                                handleRetry(f.file_id)
                              }}
                            >
                              {retrying[f.file_id] ? 'Retrying…' : '↺ Retry'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {fileStatuses.length > 0 && (
          <div className="mt-3.5 space-y-2.5">
            <div>
              <div className="flex justify-between mb-1 text-[11px] text-t2">
                <span>Overall GraphRAG construction</span><span>{overallPct}%</span>
              </div>
              <div className="prog-bar"><div className="prog-fill" style={{ width: `${overallPct}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between mb-1 text-[11px] text-t2">
                <span>Entity relationship mapping</span>
                <span>{Math.min(100, Math.round(overallPct * 1.2))}%</span>
              </div>
              <div className="prog-bar">
                <div className="prog-fill" style={{ width: `${Math.min(100, Math.round(overallPct * 1.2))}%`, background: '#0d9488' }} />
              </div>
            </div>
          </div>
        )}

        <div className="h-6" />

        {completedFileIds.length > 0 && (
          <div className="mb-4 p-4 bg-teal/5 border border-teal/25 rounded-card flex items-center justify-between">
            <div>
              <div className="text-[12px] font-semibold text-teal">
                {completed} file{completed > 1 ? 's' : ''} fully processed — GraphRAG ready
              </div>
              <div className="text-[10px] text-t3 mt-0.5">
                Entities and relationships extracted. Inspect the knowledge graph before continuing.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn btn-sm flex-shrink-0"
                style={{ color: '#d97706', borderColor: 'rgba(217,119,6,.35)', background: 'rgba(217,119,6,.08)' }}
                onClick={() => setShowEdaVisuals(true)}
              >
                📊 EDA Visuals
              </button>
              <button
                className="btn btn-teal btn-sm flex-shrink-0"
                onClick={() => setShowGraph(true)}
              >
                🔍 View GraphRAG
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button className="btn" onClick={() => setStep(0)}>← Back</button>
          <button className="btn btn-p" onClick={() => setStep(2)}>Continue to prompt →</button>
        </div>
        <div className="h-8" />
      </div>

      {showGraph && (
        <GraphRAGViewer
          fileIds={completedFileIds}
          onClose={() => setShowGraph(false)}
        />
      )}

      {showEdaVisuals && (
        <EDAVisualsViewer
          fileIds={completedFileIds}
          dbIds={completedDbIds}
          onClose={() => setShowEdaVisuals(false)}
        />
      )}

      {selectedFileForDetails && (
        <IngestionDetailModal
          file={selectedFileForDetails}
          onClose={() => setSelectedFileForDetails(null)}
        />
      )}
    </div>
  )
}
