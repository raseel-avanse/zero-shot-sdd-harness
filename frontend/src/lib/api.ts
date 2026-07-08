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

// ── Phase 2 ──────────────────────────────────────────────────────────────

/**
 * A chat turn = one user message paired with the assistant's reply, scoped to
 * the engagement (conversation memory). `POST /engagements/{id}/chat` returns
 * `{ reply, turn_id }`; we combine it with the message we sent to build a turn.
 */
export interface ChatTurn {
  turn_id: string
  message: string
  reply: string
  created_at?: string
}

/** `POST /engagements/{id}/chat` — request `{message}` → data `{reply, turn_id}`. */
export async function sendChatMessage(engagementId: string, message: string): Promise<ChatTurn> {
  const data = await request<{ reply: string; turn_id: string; created_at?: string }>(
    `/engagements/${engagementId}/chat`,
    { method: 'POST', body: JSON.stringify({ message }) },
  )
  return { turn_id: data.turn_id, message, reply: data.reply, created_at: data.created_at }
}

/**
 * `GET /engagements/{id}/chat` — data `[{turn_id, message, reply, created_at}]`.
 * Optional (may be unimplemented by the backend); callers tolerate failure and
 * fall back to an empty history.
 */
export function listChatTurns(engagementId: string) {
  return request<ChatTurn[]>(`/engagements/${engagementId}/chat`)
}

/**
 * Normalised re-test result. `POST /findings/{id}/retest` re-runs validation
 * for one finding and returns the updated status/confidence (status →
 * `remediated` when the PoC no longer reproduces). The backend may return
 * either the compact `{finding_id, confidence, status}` shape (spec/api.md) or
 * a full updated finding object; this client accepts both, and surfaces a
 * refreshed evidence block when the backend includes one.
 */
export interface RetestResult {
  finding_id: string
  status: string
  confidence: string
  evidence?: string
}

/** `POST /findings/{id}/retest` — tolerant of the compact and full-finding shapes. */
export async function retestFinding(findingId: string): Promise<RetestResult> {
  const data = await request<Record<string, unknown>>(`/findings/${findingId}/retest`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  // Full finding object (has finding-only keys) → normalise; else compact shape.
  const isFullFinding = 'severity_label' in data || 'category' in data
  const id = String(data.finding_id ?? (isFullFinding ? data.id : findingId) ?? findingId)
  return {
    finding_id: id,
    status: String(data.status ?? ''),
    confidence: String(data.confidence ?? ''),
    evidence: typeof data.evidence === 'string' ? data.evidence : undefined,
  }
}
