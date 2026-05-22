import useStore from '../store'
import c5iLogo from '../assests/c5i-primary-logo.svg'

const STEPS = ['Dashboard', '① Inject', '② Prompt', '③ Model', '④ Results']

export default function Topbar() {
  const { currentStep, setStep } = useStore()

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center justify-between px-10"
      style={{
        background: 'rgba(255,255,255,0.95)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid #dde2ee',
        boxShadow: '0 1px 6px rgba(79,70,229,0.06)',
      }}
    >
      {/* Brand */}
      <a className="flex items-center gap-3 font-sora font-bold text-lg text-t1 no-underline" href="#">
        <img
          src={c5iLogo}
          alt="C5i logo"
          className="h-8 w-auto flex-shrink-0"
        />
        AI-Orchestrator
      </a>

      {/* Step nav */}
      <div className="flex gap-0.5">
        {STEPS.map((label, i) => {
          const isActive = currentStep === i
          const isDone = currentStep > i
          return (
            <button
              key={i}
              onClick={() => setStep(i)}
              className={`
                px-4 py-2 rounded-full text-[13px] font-semibold tracking-wide border transition-all duration-150
                ${isActive
                  ? 'bg-accent text-white border-accent shadow-[0_0_0_2px_rgba(79,70,229,0.25)]'
                  : isDone
                  ? 'bg-accent/8 text-accent border-dborder2'
                  : 'bg-transparent text-t3 border-transparent hover:text-t2 hover:bg-bg4'
                }
              `}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-teal bg-teal/10 border border-teal/30 px-3 py-1 rounded-xl font-semibold">
          ● Live
        </span>
        <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-[10px] font-semibold text-white">
          AI
        </div>
      </div>
    </nav>
  )
}
