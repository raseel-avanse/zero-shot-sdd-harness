'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  getEngagement,
  listFindings,
  startRun,
  type EngagementDetail,
  type Finding,
  type ProgressEvent,
} from '@/lib/api'
import { FindingCard } from './FindingCard'
import { ErrorBanner, StubBadge } from './ui'

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

    es.addEventListener('done', () => {
      setStreamState('done')
      es.close()
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

  const running = streamState === 'starting' || streamState === 'streaming' || streamState === 'reconnecting'

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
        <button
          disabled
          className="cursor-not-allowed rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-500"
          title="Export dossier — coming in Phase 3"
        >
          Export dossier (MD / PDF / JSON)
        </button>
        <StubBadge phase="P3" />
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
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        )}
      </section>

      {/* Later-phase stubs, clearly labelled */}
      <section className="grid gap-4 sm:grid-cols-2">
        <StubPanel title="Interactive chat" phase="P2">
          <div className="flex gap-2">
            <input
              disabled
              placeholder="Ask a follow-up about this engagement…"
              className="w-full cursor-not-allowed rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 text-sm text-slate-500"
            />
            <button disabled className="cursor-not-allowed rounded-lg border border-slate-800 px-3 text-sm text-slate-600">
              Send
            </button>
          </div>
        </StubPanel>
        <StubPanel title="Next-probe suggestions" phase="P3">
          <p className="text-sm text-slate-500">
            Sentinel will suggest the highest-value next probes and flag the same pattern elsewhere.
          </p>
        </StubPanel>
      </section>
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

function StubPanel({ title, phase, children }: { title: string; phase: 'P2' | 'P3'; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-400">{title}</h4>
        <StubBadge phase={phase} />
      </div>
      {children}
    </div>
  )
}
