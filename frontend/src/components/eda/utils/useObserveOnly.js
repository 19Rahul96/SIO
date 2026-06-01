import { useState } from 'react'

// Preview/observe-only flag for the Observatory's [Preview] sections.
// Vite convention (NOT process.env / CRA): import.meta.env.VITE_EDA_PREVIEW.
export function useObserveOnly() {
  const envFlag = String(import.meta.env.VITE_EDA_PREVIEW ?? 'true').toLowerCase() !== 'false'
  return useState(envFlag)
}
