import useStore from '../../store'
import ROLES from '../../data/roles'
import UploadSurface from './UploadSurface'

function Breadcrumb({ children }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-t3 mb-3">{children}</div>
  )
}

function ModeBackLink() {
  const { resetInjectMode } = useStore()
  return (
    <button className="text-accent hover:text-accent2" onClick={resetInjectMode}>
      ← Change mode
    </button>
  )
}

function RolePicker() {
  const { setSelectedRole } = useStore()
  return (
    <div>
      <Breadcrumb>
        <ModeBackLink />
        <span>·</span>
        <span>Step 1: pick role</span>
      </Breadcrumb>
      <div className="grid grid-cols-3 gap-3">
        {ROLES.map((role) => {
          const Icon = role.icon
          return (
            <button
              key={role.id}
              className="card text-left hover:border-accent transition-colors"
              onClick={() => setSelectedRole(role)}
            >
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-9 h-9 rounded-sm bg-accent/10 border border-accent/30 flex items-center justify-center">
                  <Icon />
                </div>
                <div className="font-sora text-[13px] font-semibold text-t1">{role.label}</div>
              </div>
              <div className="text-[11px] text-t2 leading-relaxed">{role.blurb}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function RoleQuestions() {
  const { selectedRole, roleAnswers, setRoleAnswer, setSelectedRole, setRoleStage } = useStore()
  if (!selectedRole) return null
  const allAnswered = selectedRole.questions.every((q) => {
    const optional = /optional/i.test(q.label)
    return optional || (roleAnswers[q.id] && String(roleAnswers[q.id]).trim() !== '')
  })

  return (
    <div>
      <Breadcrumb>
        <ModeBackLink />
        <span>·</span>
        <button className="text-accent hover:text-accent2" onClick={() => setSelectedRole(null)}>
          ← Change role
        </button>
        <span>·</span>
        <span>{selectedRole.label} · questions</span>
      </Breadcrumb>

      <div className="card mb-3">
        <div className="font-sora text-[14px] font-semibold text-t1 mb-1">Tell us about your work</div>
        <div className="text-[11px] text-t3 mb-4">
          Answers shape the recommended document types and tag every upload for smarter retrieval.
        </div>
        <div className="grid grid-cols-2 gap-3">
          {selectedRole.questions.map((q) => (
            <div key={q.id} className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-t3">{q.label}</label>
              {q.type === 'select' ? (
                <select
                  className="bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-[12px] text-t1 outline-none focus:border-accent"
                  value={roleAnswers[q.id] || ''}
                  onChange={(e) => setRoleAnswer(q.id, e.target.value)}
                >
                  <option value="">Select…</option>
                  {q.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder={q.placeholder || ''}
                  value={roleAnswers[q.id] || ''}
                  onChange={(e) => setRoleAnswer(q.id, e.target.value)}
                  className="bg-bg3 border border-dborder2 rounded-sm px-3 py-2 text-[12px] text-t1 outline-none focus:border-accent"
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <button
          className="btn btn-p"
          disabled={!allAnswered}
          onClick={() => setRoleStage('upload')}
        >
          Continue to upload →
        </button>
      </div>
    </div>
  )
}

function RoleUpload() {
  const { selectedRole, roleAnswers, setRoleStage } = useStore()
  if (!selectedRole) return null
  const roleLabel =
    selectedRole.id === 'custom' && roleAnswers.role_name ? roleAnswers.role_name : selectedRole.label
  const ctx = { role: roleLabel, domain: selectedRole.domain }

  return (
    <div>
      <Breadcrumb>
        <ModeBackLink />
        <span>·</span>
        <button className="text-accent hover:text-accent2" onClick={() => setRoleStage('questions')}>
          ← Edit answers
        </button>
        <span>·</span>
        <span>{roleLabel} · upload</span>
      </Breadcrumb>

      {selectedRole.recommendedDocTypes.length > 0 && (
        <div className="card mb-3">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-t3 mb-2">
            Recommended document types
          </div>
          <div className="flex flex-wrap gap-2">
            {selectedRole.recommendedDocTypes.map((d) => (
              <span key={d} className="pill-b">
                {d}
              </span>
            ))}
          </div>
        </div>
      )}

      <UploadSurface
        acceptAttr={selectedRole.acceptAttr}
        uploadContext={ctx}
        showScrape={true}
        helperText={`Supports ${selectedRole.allowedExtensions.join(' · ').replaceAll('.', '').toUpperCase()} — tagged as ${roleLabel}`}
      />
    </div>
  )
}

export default function RoleWorkflow() {
  const { selectedRole, roleStage } = useStore()
  if (!selectedRole) return <RolePicker />
  if (roleStage === 'questions') return <RoleQuestions />
  if (roleStage === 'upload') return <RoleUpload />
  return <RolePicker />
}
