const ICON_PROPS = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none' }
const STROKE = { stroke: '#4f46e5', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }

export function IconLegal() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3v18M5 21h14M7 8h10M7 8l-2 5a3 3 0 0 0 6 0L9 8M17 8l-2 5a3 3 0 0 0 6 0l-2-5" {...STROKE} />
    </svg>
  )
}

export function IconRisk() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z" {...STROKE} />
      <path d="M12 9v4M12 16v.5" {...STROKE} />
    </svg>
  )
}

export function IconFinance() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="12" cy="12" r="9" {...STROKE} />
      <path d="M14 9.5c-.7-.7-1.7-1-2.5-1-1.5 0-2.5.8-2.5 2s1 1.5 2.5 2 2.5 1 2.5 2-1 2-2.5 2c-.9 0-2-.4-2.7-1.2M12 6.5v1.5M12 16v1.5" {...STROKE} />
    </svg>
  )
}

export function IconDataSci() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 17l5-6 4 3 4-5 5 6" {...STROKE} />
      <path d="M3 21h18" {...STROKE} />
      <circle cx="8" cy="11" r="1.2" fill="#4f46e5" />
      <circle cx="12" cy="14" r="1.2" fill="#4f46e5" />
      <circle cx="16" cy="9" r="1.2" fill="#4f46e5" />
    </svg>
  )
}

export function IconProduct() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="4" y="4" width="16" height="16" rx="2.5" {...STROKE} />
      <path d="M8 9h8M8 13h8M8 17h5" {...STROKE} />
    </svg>
  )
}

export function IconCustom() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3l2.5 5.5 6 .8-4.4 4.2 1.1 6L12 16.8 6.8 19.5l1.1-6L3.5 9.3l6-.8L12 3z" {...STROKE} />
    </svg>
  )
}
