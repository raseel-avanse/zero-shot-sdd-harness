// OWASP API Security Top 10 (2023) taxonomy — shared by the scope-form profile
// selector, the finding OWASP badge, and the run-view coverage panel.
// Canonical `APIn:2023 — Title` strings match spec/capabilities/owasp-api-top10.md.

export interface OwaspApiCategory {
  /** Canonical ref id, e.g. "API1:2023". */
  id: string
  /** Short title, e.g. "Broken Object Level Authorization". */
  title: string
}

export const OWASP_API_CATEGORIES: OwaspApiCategory[] = [
  { id: 'API1:2023', title: 'Broken Object Level Authorization' },
  { id: 'API2:2023', title: 'Broken Authentication' },
  { id: 'API3:2023', title: 'Broken Object Property Level Authorization' },
  { id: 'API4:2023', title: 'Unrestricted Resource Consumption' },
  { id: 'API5:2023', title: 'Broken Function Level Authorization' },
  { id: 'API6:2023', title: 'Unrestricted Access to Sensitive Business Flows' },
  { id: 'API7:2023', title: 'Server Side Request Forgery' },
  { id: 'API8:2023', title: 'Security Misconfiguration' },
  { id: 'API9:2023', title: 'Improper Inventory Management' },
  { id: 'API10:2023', title: 'Unsafe Consumption of APIs' },
]

/**
 * Extract the canonical category id (e.g. "API1:2023") from a finding's
 * `owasp_api_ref` string, which is typically "API1:2023 — Broken Object …".
 * Returns null when the ref is absent or unrecognised (tolerant, never throws).
 */
export function owaspRefId(ref: string | null | undefined): string | null {
  if (!ref) return null
  const m = ref.match(/API\d{1,2}:2023/i)
  return m ? m[0].toUpperCase() : null
}
