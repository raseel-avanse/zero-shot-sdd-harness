// API client for the DealScout backend. Same-origin: the built UI is served
// at :8001/app/ and calls the API at relative paths (no CORS).

export type RunStatus = 'running' | 'completed' | 'failed' | 'needs_input'
export type ProgressStep = 'queued' | 'searching' | 'reviewing' | 'ranking' | 'done'

export interface Deal {
  rank: number
  site: string
  price_inr: number
  reason: string
  quality_label: string | null
  quality_reason: string | null
  source_url: string | null
}

export interface RunResult {
  run_id: string
  status: RunStatus
  progress_step: ProgressStep | null
  clarifying_question: string | null
  deals: Deal[]
  prompt_tokens: number
  completion_tokens: number
  cost_inr: number | null
  error: string | null
}

interface Envelope<T> {
  data: T | null
  error: string | null
}

// basePath is /app, so an absolute "/runs" would hit the API root at the same
// origin. Next rewrites relative fetches under basePath only for assets, so we
// call the API with a leading slash to reach :8001/runs directly.
const API_BASE = ''

export async function startRun(queryText: string): Promise<{ run_id: string; status: RunStatus }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query_type: 'name', query_text: queryText }),
  })
  const body = (await res.json()) as Envelope<{ run_id: string; status: RunStatus }>
  if (!res.ok || body.error || !body.data) {
    throw new Error(body.error ?? `Couldn't start the search (${res.status}).`)
  }
  return body.data
}

export async function pollRun(runId: string): Promise<RunResult> {
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}`)
  const body = (await res.json()) as Envelope<RunResult>
  if (!res.ok || body.error || !body.data) {
    throw new Error(body.error ?? `Couldn't reach the research service (${res.status}).`)
  }
  return body.data
}

export function formatInr(value: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatCostInr(value: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}
