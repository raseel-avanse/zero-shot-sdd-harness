// API client + shared types for the Data Analyst Agent.
// All calls are same-origin relative under /api (the frontend is served at /app).
// Success envelope: { ok: true, data }. Error: { ok: false, error: { code, detail } }.

export interface Column {
  name: string
  dtype: string
  non_null: number
  null_count: number
  sample_values: unknown[]
}

export interface Profile {
  row_count: number
  columns: Column[]
  dq_flags: string[]
}

export interface UploadResult {
  dataset_id: string
  profile: Profile
}

export interface ChartPoint {
  x: string | number
  y: number
}

export interface ChartSeries {
  label: string
  points: ChartPoint[]
}

export interface ChartSpec {
  type: string
  x: string
  y: string
  series: ChartSeries[]
  title: string
}

export interface TokenUsage {
  prompt: number
  completion: number
  total: number
}

export interface StepTraceEntry {
  step: string
  status: string
  attempt: number
}

export interface AnswerResult {
  run_id: number
  answer: string
  method_note: string
  executed_code: string
  result_repr: string
  assumptions: string[]
  chart_spec: ChartSpec | null
  token_usage: TokenUsage
  attempts: number
  used_fallback: boolean
  step_trace: StepTraceEntry[]
}

export interface ApiError {
  code: string
  detail: string
}

// Thrown when the server returns a non-ok envelope or a transport failure.
export class ApiCallError extends Error {
  code: string
  constructor(code: string, detail: string) {
    super(detail)
    this.code = code
    this.name = 'ApiCallError'
  }
}

type Envelope<T> = { ok: true; data: T } | { ok: false; error: ApiError }

async function unwrap<T>(res: Response): Promise<T> {
  let body: Envelope<T> | null = null
  try {
    body = (await res.json()) as Envelope<T>
  } catch {
    throw new ApiCallError('BAD_RESPONSE', `Server returned an unreadable response (${res.status}).`)
  }
  if (body && body.ok) return body.data
  if (body && !body.ok && body.error) {
    throw new ApiCallError(body.error.code, body.error.detail)
  }
  throw new ApiCallError('UNKNOWN', `Request failed (${res.status}).`)
}

export async function uploadDataset(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  let res: Response
  try {
    res = await fetch('/api/datasets', { method: 'POST', body: form })
  } catch {
    throw new ApiCallError('NETWORK', 'Network error — is the server running?')
  }
  return unwrap<UploadResult>(res)
}

export async function askQuestion(datasetId: string, question: string): Promise<AnswerResult> {
  let res: Response
  try {
    res = await fetch(`/api/datasets/${encodeURIComponent(datasetId)}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
  } catch {
    throw new ApiCallError('NETWORK', 'Network error — is the server running?')
  }
  return unwrap<AnswerResult>(res)
}
