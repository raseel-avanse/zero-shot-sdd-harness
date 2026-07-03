'use client'

import type { StepTraceEntry } from '@/lib/api'

interface Props {
  // While the request is in flight, trace is null and we show an animated indicator.
  inFlight: boolean
  trace: StepTraceEntry[] | null
  attempts?: number
}

const STEP_ORDER = ['profiling', 'writing_code', 'running_code', 'synthesizing']
const STEP_LABELS: Record<string, string> = {
  profiling: 'Profiling',
  writing_code: 'Writing code',
  running_code: 'Running code',
  synthesizing: 'Synthesizing',
}

function labelFor(step: string): string {
  return STEP_LABELS[step] ?? step.replace(/_/g, ' ')
}

export default function StepStatus({ inFlight, trace, attempts }: Props) {
  if (!inFlight && !trace) return null

  // In-flight: show the ordered plan with a spinner (we don't yet know progress).
  if (inFlight) {
    return (
      <div
        className="flex flex-wrap items-center gap-3 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800"
        data-testid="step-status"
        aria-live="polite"
      >
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
        <span className="font-medium">Working on it…</span>
        <span className="flex flex-wrap gap-2 text-xs text-blue-700">
          {STEP_ORDER.map((s, i) => (
            <span key={s}>
              {labelFor(s)}
              {i < STEP_ORDER.length - 1 ? ' →' : ''}
            </span>
          ))}
        </span>
      </div>
    )
  }

  const steps = trace ?? []
  return (
    <div
      className="rounded-lg border border-gray-200 bg-gray-50 p-3"
      data-testid="step-status"
    >
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                s.status === 'done' ? 'bg-green-500' : 'bg-gray-300'
              }`}
            />
            <span className="font-medium">{labelFor(s.step)}</span>
            {s.attempt > 1 && (
              <span className="rounded bg-gray-200 px-1 text-[10px] text-gray-600">
                attempt {s.attempt}
              </span>
            )}
            {i < steps.length - 1 && <span className="text-gray-300">→</span>}
          </div>
        ))}
      </div>
      {attempts !== undefined && attempts > 1 && (
        <p className="mt-2 text-xs font-medium text-amber-700" data-testid="self-corrected">
          Self-corrected after {attempts} attempts.
        </p>
      )}
    </div>
  )
}
