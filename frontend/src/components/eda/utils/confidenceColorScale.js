// Confidence color scale (per Observatory spec): red -> amber -> teal.
const RED = '#E24B4A'
const AMBER = '#EF9F27'
const TEAL = '#1D9E75'

export function interpolateHex(a, b, t) {
  const pa = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)]
  const pb = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)]
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * Math.max(0, Math.min(1, t))))
  return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

export function getConfidenceColor(score) {
  if (score == null) return '#d8dde9' // gray — missing
  if (score <= 0) return RED
  if (score >= 1) return TEAL
  if (score < 0.4) return interpolateHex(RED, AMBER, score / 0.4)
  if (score < 0.7) return AMBER
  return interpolateHex(AMBER, TEAL, (score - 0.7) / 0.3)
}

export const CONFIDENCE_COLORS = { RED, AMBER, TEAL }
