// Sentinel API client — all calls are SAME-ORIGIN relative paths.
// The app is served under /app by FastAPI, but fetch()/EventSource ignore
// Next's basePath, so "/engagements" hits the API at the origin root.

export type TargetType = 'repo' | 'live_app'

export interface EngagementSummary {
  engagement_id: string
  name: string
  target_type: TargetType
  status: string
  created_at: string
}

export interface ScopeRecord {
  target_ref: string
  authorized_targets: string[]
  rules_of_engagement: string
  authorized_by: string
  non_destructive_only: boolean
}

export interface EngagementDetail {
  engagement: EngagementSummary & { target_ref?: string }
  scope_record: ScopeRecord
}

export interface CreateEngagementBody {
  name: string
  target_type: TargetType
  target_ref: string
  authorized_targets: string[]
  rules_of_engagement: string
  authorized_by: string
  non_destructive_only: boolean
}

export interface Finding {
  id: string
  category: string
  title: string
  severity_label: string
  cvss_score: number | null
  location: string
  description: string
  evidence: string
  confidence: string
  status: string
  remediation: string
  suggested_patch: string
  created_at: string
}

export interface RunSnapshot {
  run_id: string
  status: string
  current_phase: string | null
  current_category: string | null
  step_count: number
  step_budget: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  error_message: string | null
}

// SSE payload shapes (event names: progress | finding | done | error)
export interface ProgressEvent {
  current_phase: string | null
  current_category: string | null
  step_count: number
  step_budget: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_usd: number
}
export interface DoneEvent {
  status: string
}
export interface ErrorEvent {
  message: string
}

/** Success envelope: {data, error:null}. Error: {detail:{code,message}}. */
export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError('Network error — is the Sentinel server running?', 'network', 0)
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through — handled below
  }
  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } } | null)?.detail
    throw new ApiError(
      detail?.message ?? `Request failed (${res.status})`,
      detail?.code ?? 'error',
      res.status,
    )
  }
  return (body as { data: T }).data
}

export function listEngagements() {
  return request<EngagementSummary[]>('/engagements')
}

export function getEngagement(id: string) {
  return request<EngagementDetail>(`/engagements/${id}`)
}

export function createEngagement(body: CreateEngagementBody) {
  return request<{ engagement_id: string; status: string }>('/engagements', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function startRun(engagementId: string) {
  return request<{ run_id: string; status: string }>(`/engagements/${engagementId}/runs`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function getRun(runId: string) {
  return request<RunSnapshot>(`/runs/${runId}`)
}

export function listFindings(engagementId: string) {
  return request<Finding[]>(`/engagements/${engagementId}/findings`)
}
