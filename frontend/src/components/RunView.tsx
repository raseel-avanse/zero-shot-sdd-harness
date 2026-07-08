'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  exportUrl,
  getEngagement,
  getRun,
  listFindings,
  startRun,
  type EngagementDetail,
  type Finding,
  type ProgressEvent,
} from '@/lib/api'
import { ChatPanel } from './ChatPanel'
import { FindingCard } from './FindingCard'
import { ErrorBanner } from './ui'

type StreamState = 'idle' | 'starting' | 'streaming' | 'reconnecting' | 'done' | 'error'

const EMPTY_PROGRESS: ProgressEvent = {
  current_phase: null,
  current_category: null,
  step_count: 0,
  step_budget: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  estimated_cost_usd: 0,
}

export function RunView({ engagementId, onBack }: { engagementId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<EngagementDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(true)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [streamState, setStreamState] = useState<StreamState>('idle')
  const [progress, setProgress] = useState<ProgressEvent>(EMPTY_PROGRESS)
  const [findings, setFindings] = useState<Finding[]>([])
  const [runError, setRunError] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    let alive = true
    setLoadingDetail(true)
    getEngagement(engagementId)
      .then((d) => {
        if (!alive) return
        setDetail(d)
        setDetailError(null)
      })
      .catch((e) => alive && setDetailError(e instanceof ApiError ? e.message : 'Failed to load engagement.'))
      .finally(() => alive && setLoadingDetail(false))
    // Load any pre-existing findings (finished run).
    listFindings(engagementId)
      .then((f) => alive && f.length && setFindings(f))
      .catch(() => {})
    return () => {
      alive = false
      esRef.current?.close()
    }
  }, [engagementId])

  const openStream = useCallback((runId: string) => {
    esRef.current?.close()
    const es = new EventSource(`/runs/${runId}/events`)
    esRef.current = es

    es.addEventListener('open', () => setStreamState('streaming'))

    es.addEventListener('progress', (ev) => {
      try {
        setProgress(JSON.parse((ev as MessageEvent).data) as ProgressEvent)
        setStreamState('streaming')
      } catch {
        /* ignore malformed frame */
      }
    })

    es.addEventListener('finding', (ev) => {
      try {
        const f = JSON.parse((ev as MessageEvent).data) as Finding
        setFindings((prev) => (prev.some((p) => p.id === f.id) ? prev : [...prev, f]))
      } catch {
        /* ignore malformed frame */
      }
    })

    es.addEventListener('done', (ev) => {
      setStreamState('done')
      es.close()
      // Proactive next-probe suggestions may ride the done frame or land in run
      // metadata. Tolerate either / neither — render nothing rather than crash.
      let fromFrame: string[] | undefined
      try {
        const parsed = JSON.parse((ev as MessageEvent).data)
        if (Array.isArray(parsed?.next_probes)) fromFrame = parsed.next_probes
      } catch {
        /* ignore */
      }
      if (fromFrame?.length) setSuggestions(fromFrame)
      getRun(runId)
        .then((snap) => {
          if (Array.isArray(snap.next_probes) && snap.next_probes.length) {
            setSuggestions(snap.next_probes)
          }
        })
        .catch(() => {
          /* run-metadata suggestions are optional */
        })
    })

    es.addEventListener('error', (ev) => {
      const data = (ev as MessageEvent).data
      if (data) {
        try {
          setRunError(JSON.parse(data).message ?? 'Assessment failed.')
        } catch {
          setRunError('Assessment failed.')
        }
        setStreamState('error')
        es.close()
      } else if (es.readyState === EventSource.CLOSED) {
        setStreamState('error')
      } else {
        // transient network drop — browser auto-reconnects
        setStreamState('reconnecting')
      }
    })
  }, [])

  async function handleStart() {
    setStartError(null)
    setRunError(null)
    setFindings([])
    setSuggestions([])
    setProgress(EMPTY_PROGRESS)
    setStreamState('starting')
    try {
      const { run_id } = await startRun(engagementId)
      openStream(run_id)
    } catch (e) {
      setStreamState('idle')
      if (e instanceof ApiError && e.status === 422) {
        setStartError('Target outside authorized scope — run refused.')
      } else {
        setStartError(e instanceof ApiError ? e.message : 'Could not start the assessment.')
      }
    }
  }

  function handleRetested(id: string, status: string, confidence: string, evidence?: string) {
    setFindings((prev) =>
      prev.map((f) =>
        f.id === id
          ? { ...f, status, confidence, ...(evidence !== undefined ? { evidence } : {}) }
          : f,
      ),
    )
  }

  function handleStatusChanged(id: string, status: string) {
    setFindings((prev) => prev.map((f) => (f.id === id ? { ...f, status } : f)))
  }

  const running = streamState === 'starting' || streamState === 'streaming' || streamState === 'reconnecting'
  const isLive = detail?.engagement.target_type === 'live_app'

  // Group findings that share a `pattern_ref` (same vulnerability pattern found
  // in ≥2 places). Only refs with >1 occurrence get a visible flag/label.
  const patternLabels = new Map<string, string>()
  {
    const counts = new Map<string, number>()
    for (const f of findings) {
      if (f.pattern_ref) counts.set(f.pattern_ref, (counts.get(f.pattern_ref) ?? 0) + 1)
    }
    let n = 0
    for (const [ref, count] of counts) {
      if (count > 1) patternLabels.set(ref, `Pattern ${String.fromCharCode(65 + n++)}`)
    }
  }

  return (
    <div className="space-y-6">
      <button onClick={onBack} className="text-sm text-slate-400 hover:text-slate-200">
        ← Back to engagements
      </button>

      {loadingDetail && <p className="text-sm text-slate-400">Loading engagement…</p>}
      {detailError && <ErrorBanner message={detailError} />}

      {detail && (
        <div>
          <h2 className="text-2xl font-semibold text-slate-50">{detail.engagement.name}</h2>
          <p className="mt-1 font-mono text-sm text-emerald-400">{detail.scope_record.target_ref}</p>
          {detail.scope_record.authorized_by && (
            <p className="mt-1 text-xs text-slate-500">
              Authorized by {detail.scope_record.authorized_by} ·{' '}
              {detail.scope_record.non_destructive_only ? 'non-destructive only' : 'destructive allowed'}
            </p>
          )}
          {isLive && (
            <p
              data-testid="live-probe-notice"
              className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-sky-500/10 px-2.5 py-1 text-xs font-medium text-sky-300 ring-1 ring-sky-500/30"
            >
              Live-app probe · read-only (GET / HEAD / OPTIONS), allowlisted hosts only
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleStart}
          disabled={running || !detail}
          data-testid="start-assessment"
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {streamState === 'starting'
            ? 'Starting…'
            : running
              ? 'Assessment running…'
              : streamState === 'done'
                ? 'Run again'
                : 'Start Assessment'}
        </button>
        <div className="flex flex-wrap items-center gap-2" data-testid="export-dossier">
          <span className="text-sm text-slate-400">Export dossier:</span>
          {(['md', 'pdf', 'json'] as const).map((fmt) => (
            <a
              key={fmt}
              href={exportUrl(engagementId, fmt)}
              download
              data-testid={`export-${fmt}`}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-emerald-500/50 hover:bg-slate-800"
              title={`Download the engagement dossier as ${fmt.toUpperCase()}`}
            >
              {fmt.toUpperCase()}
            </a>
          ))}
        </div>
      </div>

      {startError && <ErrorBanner message={startError} />}

      {(running || streamState === 'done' || streamState === 'error') && (
        <ProgressPanel progress={progress} state={streamState} />
      )}

      {streamState === 'reconnecting' && (
        <p className="text-sm text-amber-400">Stream interrupted — reconnecting…</p>
      )}
      {runError && <ErrorBanner message={runError} />}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Findings {findings.length > 0 && <span className="text-slate-500">({findings.length})</span>}
          </h3>
        </div>

        {findings.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/40 px-6 py-12 text-center">
            {running ? (
              <p className="text-sm text-slate-400">Hunting for vulnerabilities — findings will stream in as they are validated…</p>
            ) : (
              <p className="text-sm text-slate-400">No findings yet — start an assessment.</p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {findings.map((f) => (
              <FindingCard
                key={f.id}
                finding={f}
                patternLabel={f.pattern_ref ? patternLabels.get(f.pattern_ref) : undefined}
                onRetested={handleRetested}
                onStatusChanged={handleStatusChanged}
              />
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <ChatPanel engagementId={engagementId} />
        <SuggestionsPanel suggestions={suggestions} state={streamState} />
      </section>
    </div>
  )
}

function SuggestionsPanel({ suggestions, state }: { suggestions: string[]; state: StreamState }) {
  return (
    <div
      data-testid="suggestions-panel"
      className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
    >
      <h4 className="mb-2 text-sm font-semibold text-slate-300">Suggested next probes</h4>
      {suggestions.length > 0 ? (
        <ul className="space-y-2" data-testid="suggestions-list">
          {suggestions.map((s, i) => (
            <li
              key={i}
              data-testid="suggestion-item"
              className="flex gap-2 rounded-lg bg-slate-800/50 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700/60"
            >
              <span className="text-emerald-400">→</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">
          {state === 'done'
            ? 'No further probes suggested — the target surface has been covered.'
            : 'After a run, Sentinel suggests the highest-value next probes and flags the same vulnerability pattern elsewhere in the target.'}
        </p>
      )}
    </div>
  )
}

function ProgressPanel({ progress, state }: { progress: ProgressEvent; state: StreamState }) {
  const pct = progress.step_budget ? Math.min(100, (progress.step_count / progress.step_budget) * 100) : 0
  return (
    <div className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5 sm:grid-cols-2">
      <div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Progress</span>
          <span className="font-mono text-sm text-slate-200" data-testid="step-counter">
            step {progress.step_count} / {progress.step_budget || '—'}
          </span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
          <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <dl className="mt-3 space-y-1 text-sm">
          <Row label="Phase" value={progress.current_phase ?? (state === 'done' ? 'complete' : '—')} />
          <Row label="Category" value={progress.current_category ?? '—'} />
        </dl>
      </div>
      <div>
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Token &amp; cost</span>
        <dl className="mt-2 space-y-1 font-mono text-sm">
          <Row label="Prompt" value={progress.prompt_tokens.toLocaleString()} />
          <Row label="Completion" value={progress.completion_tokens.toLocaleString()} />
          <Row label="Total tokens" value={progress.total_tokens.toLocaleString()} />
          <Row
            label="Est. cost"
            value={<span data-testid="est-cost">${progress.estimated_cost_usd.toFixed(4)}</span>}
          />
        </dl>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-200">{value}</dd>
    </div>
  )
}
