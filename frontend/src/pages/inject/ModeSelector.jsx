import useStore from '../../store'

function ScaleIcon() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3v18M5 21h14M7 8h10M7 8l-2 5a3 3 0 0 0 6 0L9 8M17 8l-2 5a3 3 0 0 0 6 0l-2-5"
        stroke="#4f46e5"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <path
        d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"
        stroke="#4f46e5"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Pill({ icon, label }) {
  return (
    <div className="flex items-center justify-center gap-2 px-3 py-2 rounded-sm bg-bg4 border border-dborder text-[11px] text-t2 font-medium">
      {icon}
      <span>{label}</span>
    </div>
  )
}

const ROLE_PILLS = [
  {
    label: 'Legal',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <path d="M12 3v18M5 21h14M7 8h10" stroke="#5a6280" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: 'Risk Mgr',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z" stroke="#5a6280" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    label: 'Finance',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="#5a6280" strokeWidth="1.6" />
        <path d="M9.5 14c.5.8 1.5 1.2 2.5 1.2 1.5 0 2.5-.8 2.5-2s-1-1.5-2.5-2-2.5-1-2.5-2 1-2 2.5-2c.9 0 1.7.3 2.3.9" stroke="#5a6280" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: 'Data Sci',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <path d="M3 17l5-6 4 3 4-5 5 6" stroke="#5a6280" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
]

const UPLOAD_PILLS = [
  {
    label: 'Files',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" stroke="#5a6280" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M14 3v5h5" stroke="#5a6280" strokeWidth="1.6" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: 'Database',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <ellipse cx="12" cy="6" rx="8" ry="3" stroke="#5a6280" strokeWidth="1.6" />
        <path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" stroke="#5a6280" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    label: 'Web URL',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="#5a6280" strokeWidth="1.6" />
        <path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18" stroke="#5a6280" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    label: 'Folder',
    icon: (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" stroke="#5a6280" strokeWidth="1.6" />
        <path d="M9 12h6M12 9v6" stroke="#5a6280" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
]

export default function ModeSelector() {
  const { setInjectMode } = useStore()
  return (
    <div className="mb-4">
      <div className="sect">Choose entry mode</div>
      <div className="text-[11px] text-t3 mb-3 -mt-2">
        Both modes converge to the same preprocessing & GraphRAG pipeline. The role-based mode tailors the upload form and tags every file with role context for smarter SLM matching.
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="card flex flex-col">
          <div className="flex flex-col items-center text-center gap-1 mb-3">
            <ScaleIcon />
            <div className="font-sora text-[15px] font-semibold text-t1 mt-1">Role-Based Mode</div>
            <div className="text-[11px] text-t2">Select a predefined role for guided, optimized workflow</div>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-4">
            {ROLE_PILLS.map((p) => (
              <Pill key={p.label} icon={p.icon} label={p.label} />
            ))}
          </div>
          <button className="btn btn-full" onClick={() => setInjectMode('role')}>
            Select Role
          </button>
        </div>

        <div className="card flex flex-col">
          <div className="flex flex-col items-center text-center gap-1 mb-3">
            <FolderIcon />
            <div className="font-sora text-[15px] font-semibold text-t1 mt-1">Direct Upload Mode</div>
            <div className="text-[11px] text-t2">Upload files directly for flexible, auto-domain processing</div>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-4">
            {UPLOAD_PILLS.map((p) => (
              <Pill key={p.label} icon={p.icon} label={p.label} />
            ))}
          </div>
          <button className="btn btn-full" onClick={() => setInjectMode('direct')}>
            Start Upload
          </button>
        </div>
      </div>
    </div>
  )
}
