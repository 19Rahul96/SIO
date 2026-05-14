import logo from '../assests/c5i-primary-logo.svg'

export default function Footer() {
  return (
    <footer
      className="w-full flex items-center justify-between px-10 py-4"
      style={{
        background: 'rgba(255,255,255,0.95)',
        borderTop: '1px solid #dde2ee',
        boxShadow: '0 -1px 6px rgba(79,70,229,0.04)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <img src={logo} alt="C5i Logo" className="h-7 w-auto" />
      </div>

      {/* Center text */}
      <span className="text-[11px] text-t3 font-medium">
        AI-Orchestrator &copy; {new Date().getFullYear()} &mdash; Powered by C5i
      </span>

      {/* Right side */}
      <span className="text-[11px] text-t3">
        All rights reserved
      </span>
    </footer>
  )
}
