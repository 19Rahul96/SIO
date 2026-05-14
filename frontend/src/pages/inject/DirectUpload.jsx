import { useState } from 'react'
import useStore from '../../store'
import api from '../../services/api'
import UploadSurface from './UploadSurface'

const LOCAL_SQL_DIR = '/home/neelam/AI-Orchestrator/backend/data/db_data/carbonated_drinks'

function Breadcrumb({ children }) {
  return <div className="flex items-center gap-2 text-[11px] text-t3 mb-3">{children}</div>
}

function DbConnect() {
  const { addFile, updateFile } = useStore()
  const [dbOpen, setDbOpen] = useState(true)
  const [dbStatus, setDbStatus] = useState('Not connected')
  const [dbStatusClass, setDbStatusClass] = useState('text-t3')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    engine: 'SQLite (local SQL folder)',
    host: 'localhost',
    port: '5432',
    dbname: 'carbonated_drinks',
    user: '',
    password: '',
  })

  const fields = [
    {
      label: 'Database type',
      type: 'select',
      key: 'engine',
      opts: ['SQLite (local SQL folder)', 'PostgreSQL', 'MySQL'],
    },
    { label: 'Host / Endpoint', type: 'text', key: 'host', placeholder: 'db.example.com' },
    { label: 'Port', type: 'text', key: 'port', placeholder: '5432' },
    { label: 'Database name', type: 'text', key: 'dbname', placeholder: 'production_db' },
    { label: 'Username', type: 'text', key: 'user', placeholder: 'admin' },
    { label: 'Password', type: 'password', key: 'password', placeholder: '••••••••' },
  ]

  const isLocalSqlMode = form.engine === 'SQLite (local SQL folder)'

  const buildPayload = () => {
    if (isLocalSqlMode) {
      return {
        engine: 'sqlite',
        dbname: 'carbonated_drinks',
        source_sql_dir: LOCAL_SQL_DIR,
        path: 'data/db_data/generated/carbonated_drinks.sqlite',
      }
    }

    const normalizedEngine = form.engine.toLowerCase()
    return {
      engine: normalizedEngine,
      host: form.host || null,
      port: form.port ? Number(form.port) : null,
      dbname: form.dbname || null,
      user: form.user || null,
      password: form.password || null,
    }
  }

  const handleConnectIngest = async () => {
    setBusy(true)
    setDbStatus('Connecting and queuing ingestion...')
    setDbStatusClass('text-amber')
    try {
      const payload = buildPayload()
      const res = await api.dbConnect(payload)
      const record = {
        file_id: res.db_id,
        db_id: res.db_id,
        filename: isLocalSqlMode
          ? 'Database (sqlite) carbonated_drinks'
          : `Database (${payload.engine}) ${payload.dbname || 'db'}`,
        ext: 'DB',
        size: 0,
        status: res.status || 'queued',
        uploaded_at: Date.now() / 1000,
        pipeline_steps: {
          connecting: false,
          introspecting: false,
          profiling: false,
          graphify_running: false,
          merging: false,
          embedding: false,
        },
      }
      addFile(record)
      updateFile(res.db_id, record)
      setDbStatus('✓ DB ingestion queued. Live status appears below.')
      setDbStatusClass('text-gg')
    } catch (err) {
      setDbStatus(`Failed: ${err?.message || 'Unable to connect and ingest'}`)
      setDbStatusClass('text-coral')
    } finally {
      setBusy(false)
    }
  }

  const handleTestConnection = async () => {
    setBusy(true)
    setDbStatus('Testing connection...')
    setDbStatusClass('text-amber')
    try {
      const payload = buildPayload()
      const res = await api.dbTest(payload)
      if (res.ok) {
        setDbStatus(`✓ Connection successful — ${res.table_count} table${res.table_count !== 1 ? 's' : ''} found (${res.dialect})`)
        setDbStatusClass('text-gg')
      } else {
        setDbStatus(`Connection failed: ${res.error || 'Unknown error'}`)
        setDbStatusClass('text-coral')
      }
    } catch (err) {
      setDbStatus(`Failed: ${err?.message || 'Unable to reach backend'}`)
      setDbStatusClass('text-coral')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-card border border-dborder rounded-card overflow-hidden">
      <div
        className="flex items-center justify-between p-3.5 border-b border-dborder bg-card2 cursor-pointer hover:bg-bg4"
        onClick={() => setDbOpen(!dbOpen)}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-blue/10 border border-blue/30 rounded-lg flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <ellipse cx="7" cy="4" rx="5" ry="2" stroke="#2563eb" strokeWidth="1.2" />
              <path d="M2 4v3c0 1.1 2.24 2 5 2s5-.9 5-2V4" stroke="#2563eb" strokeWidth="1.2" />
              <path d="M2 7v3c0 1.1 2.24 2 5 2s5-.9 5-2V7" stroke="#2563eb" strokeWidth="1.2" />
            </svg>
          </div>
          <div>
            <div className="text-[12px] font-semibold text-t1">Database connection</div>
            <div className="text-[10px] text-t3">Connect your data source securely</div>
          </div>
        </div>
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          style={{ transform: dbOpen ? 'rotate(180deg)' : '', transition: 'transform .2s' }}
        >
          <path d="M3 5l4 4 4-4" stroke="#8e97b8" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </div>
      {dbOpen && (
        <div className="p-5">
          {isLocalSqlMode && (
            <div className="mb-3 text-[11px] text-t2 bg-bg3 border border-dborder2 rounded-sm px-3 py-2">
              Source SQL folder: {LOCAL_SQL_DIR}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 mb-4">
            {fields.map((f) => (
              <div key={f.label} className="flex flex-col gap-1">
                <label className="text-[10px] font-semibold uppercase tracking-wider text-t3">{f.label}</label>
                {f.type === 'select' ? (
                  <select
                    value={form[f.key]}
                    onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    className="bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-[12px] text-t1 outline-none focus:border-accent"
                  >
                    {f.opts.map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={f.type}
                    value={form[f.key]}
                    onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    disabled={busy || (isLocalSqlMode && ['host', 'port', 'dbname', 'user', 'password'].includes(f.key))}
                    className="bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-[12px] text-t1 outline-none focus:border-accent"
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2.5">
            <button
              className="btn btn-p btn-sm"
              disabled={busy}
              onClick={handleTestConnection}
            >
              {busy ? 'Testing...' : 'Test connection'}
            </button>
            <button
              className="btn btn-sm"
              disabled={busy}
              onClick={handleConnectIngest}
            >
              {busy ? 'Queuing...' : 'Connect & ingest'}
            </button>
            <span className={`text-[11px] ${dbStatusClass}`}>{dbStatus}</span>
          </div>
          <div className="flex gap-2 flex-wrap mt-3.5 pt-3.5 border-t border-dborder">
            <div className="db-chip db-chip-connected">
              <span className="w-1.5 h-1.5 rounded-full bg-gg flex-shrink-0" />
              PostgreSQL · prod-db
            </div>
            <div className="db-chip">
              <span className="w-1.5 h-1.5 rounded-full bg-t3 flex-shrink-0" />
              MySQL · analytics
            </div>
            <div className="db-chip">
              <span className="w-1.5 h-1.5 rounded-full bg-t3 flex-shrink-0" />
              Snowflake · warehouse
            </div>
            <div className="db-chip border-dashed text-t3">+ Add new source</div>
          </div>
        </div>
      )}
    </div>
  )
}

const TABS = [
  { id: 'file', label: 'Files' },
  { id: 'folder', label: 'Folder' },
  { id: 'scrape', label: 'Web URL' },
  { id: 'db', label: 'Database' },
]

export default function DirectUpload() {
  const { resetInjectMode } = useStore()
  const [activeTab, setActiveTab] = useState('file')

  return (
    <div>
      <Breadcrumb>
        <button className="text-accent hover:text-accent2" onClick={resetInjectMode}>
          ← Change mode
        </button>
        <span>·</span>
        <span>Direct upload</span>
      </Breadcrumb>

      <div className="flex gap-2 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`btn btn-sm ${activeTab === t.id ? 'border-accent text-accent bg-accent/10' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'file' && (
        <UploadSurface
          acceptAttr=".pdf,.docx,.txt,.csv,.xlsx,.xls"
          uploadContext={{}}
          showScrape={false}
          helperText="Supports PDF · DOCX · XLSX · CSV · TXT — multiple files allowed"
        />
      )}

      {activeTab === 'folder' && (
        <UploadSurface
          acceptAttr=".pdf,.docx,.txt,.csv,.xlsx,.xls"
          uploadContext={{}}
          showScrape={false}
          allowFolder={true}
          helperText="Pick a folder — every supported file inside is uploaded individually"
        />
      )}

      {activeTab === 'scrape' && (
        <UploadSurface
          acceptAttr=".pdf,.docx,.txt,.csv,.xlsx,.xls"
          uploadContext={{}}
          showFiles={false}
          showScrape={true}
        />
      )}

      {activeTab === 'db' && <DbConnect />}
    </div>
  )
}
