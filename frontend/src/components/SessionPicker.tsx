'use client'

import type { SessionSummary } from '@/lib/api'

interface Props {
  sessions: SessionSummary[]
  activeSessionId: string | null
  loading: boolean
  error: string | null
  onSelect: (sessionId: string) => void
}

function formatWhen(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function SessionPicker({
  sessions,
  activeSessionId,
  loading,
  error,
  onSelect,
}: Props) {
  if (loading) {
    return (
      <section aria-label="Sessions" data-testid="session-picker">
        <p className="py-4 text-center text-sm text-gray-400">Loading past sessions…</p>
      </section>
    )
  }

  if (error) {
    return (
      <section aria-label="Sessions" data-testid="session-picker">
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          data-testid="sessions-error"
        >
          {error}
        </div>
      </section>
    )
  }

  if (sessions.length === 0) return null

  return (
    <section aria-label="Sessions" data-testid="session-picker">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Recent sessions
      </h2>
      <ul className="space-y-2">
        {sessions.map(s => {
          const active = s.session_id === activeSessionId
          return (
            <li key={s.session_id}>
              <button
                type="button"
                onClick={() => onSelect(s.session_id)}
                data-testid="session-item"
                data-session-id={s.session_id}
                aria-current={active}
                className={`flex w-full items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-left text-sm transition-colors ${
                  active
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium text-gray-900">{s.title}</span>
                  <span className="block text-xs text-gray-500">
                    {s.turn_count} {s.turn_count === 1 ? 'question' : 'questions'} ·{' '}
                    {formatWhen(s.updated_at)}
                  </span>
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    s.dataframe_loaded
                      ? 'bg-green-50 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                  data-testid="session-loaded-indicator"
                >
                  {s.dataframe_loaded ? 'data loaded' : 're-upload to continue'}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
