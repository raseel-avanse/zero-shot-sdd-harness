'use client'

import { useEffect, useRef, useState } from 'react'
import {
  startRun,
  pollRun,
  submitAnswer,
  type QueryType,
  type RunResult,
} from '@/lib/api'
import ProgressBar from '@/components/ProgressBar'
import DealCard from '@/components/DealCard'
import CostFooter from '@/components/CostFooter'
import ClarifyPrompt from '@/components/ClarifyPrompt'
import ModeTabs, { MODES } from '@/components/ModeTabs'

const POLL_MS = 1500

type Phase = 'empty' | 'running' | 'needs_input' | 'completed' | 'failed'

const PLACEHOLDERS: Record<QueryType, string> = {
  name: 'e.g. Sony WH-1000XM5 headphones',
  url: 'e.g. https://www.amazon.in/dp/B09XS7JWHH',
  category: 'e.g. wireless earbuds under ₹5000',
}

const INPUT_LABELS: Record<QueryType, string> = {
  name: 'Product name',
  url: 'Product URL',
  category: 'Category',
}

export default function Home() {
  const [mode, setMode] = useState<QueryType>('name')
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<Phase>('empty')
  const [run, setRun] = useState<RunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [answering, setAnswering] = useState(false)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [])

  function stopPolling() {
    if (pollRef.current) {
      clearTimeout(pollRef.current)
      pollRef.current = null
    }
  }

  async function tick(runId: string) {
    try {
      const result = await pollRun(runId)
      setRun(result)
      if (result.status === 'completed') {
        setPhase('completed')
        stopPolling()
      } else if (result.status === 'failed') {
        setError(result.error ?? 'The research run failed. Please try again.')
        setPhase('failed')
        stopPolling()
      } else if (result.status === 'needs_input') {
        setPhase('needs_input')
        stopPolling()
      } else {
        pollRef.current = setTimeout(() => tick(runId), POLL_MS)
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Couldn’t reach the research service — try again.',
      )
      setPhase('failed')
      stopPolling()
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = query.trim()
    if (!text || phase === 'running') return
    stopPolling()
    setError(null)
    setRun(null)
    setPhase('running')
    try {
      const started = await startRun(mode, text)
      pollRef.current = setTimeout(() => tick(started.run_id), POLL_MS)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Couldn’t reach the research service — try again.',
      )
      setPhase('failed')
    }
  }

  async function handleAnswer(answer: string) {
    if (!run) return
    setAnswering(true)
    setError(null)
    try {
      const resumed = await submitAnswer(run.run_id, answer)
      setPhase('running')
      setAnswering(false)
      pollRef.current = setTimeout(() => tick(resumed.run_id), POLL_MS)
    } catch (err) {
      setAnswering(false)
      setError(
        err instanceof Error ? err.message : 'Couldn’t submit your answer — try again.',
      )
      setPhase('failed')
    }
  }

  const isRunning = phase === 'running'
  const inputDisabled = isRunning || phase === 'needs_input'
  const activeMode = MODES.find(m => m.key === mode)!

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-12 sm:py-16">
      <header className="mb-10 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-medium text-[var(--text-muted)] shadow-sm">
          <span aria-hidden="true" className="text-[var(--accent)]">◆</span>
          Real-time deal research
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-[var(--text)] sm:text-5xl">
          DealScout
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-[var(--text-muted)] sm:text-base">
          Find the best deal across Indian shopping sites.
        </p>
      </header>

      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6">
        <ModeTabs mode={mode} onChange={setMode} disabled={inputDisabled} />

        <form onSubmit={handleSubmit} className="mt-4">
          <label
            htmlFor="query-input"
            className="mb-1.5 block text-sm font-medium text-[var(--text)]"
          >
            {INPUT_LABELS[mode]}
          </label>
          <p className="mb-2 text-xs text-[var(--text-faint)]" data-testid="mode-hint">
            {activeMode.hint}
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="query-input"
              type={mode === 'url' ? 'url' : 'text'}
              inputMode={mode === 'url' ? 'url' : 'text'}
              className="flex-1 rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3.5 py-2.5 text-sm text-[var(--text)] shadow-sm transition-colors placeholder:text-[var(--text-faint)] focus:border-[var(--accent)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:opacity-60"
              placeholder={PLACEHOLDERS[mode]}
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={inputDisabled}
              autoComplete="off"
              data-testid="query-input"
            />
            <button
              type="submit"
              disabled={inputDisabled || !query.trim()}
              className="rounded-xl bg-[var(--accent)] px-6 py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-sm transition-colors hover:bg-[var(--accent-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:opacity-50"
              data-testid="find-deals"
            >
              {isRunning ? 'Finding deals…' : 'Find deals'}
            </button>
          </div>
        </form>
      </div>

      {phase === 'empty' && (
        <p
          className="ds-animate-in mt-10 text-center text-sm leading-relaxed text-[var(--text-faint)]"
          data-testid="empty-state"
        >
          Type a {mode === 'url' ? 'product URL' : mode === 'category' ? 'category' : 'product name'} to
          find the best deals across Indian shopping sites.
        </p>
      )}

      {isRunning && <ProgressBar step={run?.progress_step ?? 'queued'} />}

      {phase === 'needs_input' && run?.clarifying_question && (
        <ClarifyPrompt
          question={run.clarifying_question}
          onSubmit={handleAnswer}
          submitting={answering}
        />
      )}

      {phase === 'failed' && (
        <div
          className="ds-animate-in mt-8 rounded-2xl border border-[var(--warn-border)] bg-[var(--warn-bg)] p-5 text-sm text-[var(--warn-fg)]"
          role="alert"
          data-testid="error-state"
        >
          <p className="font-medium">
            {error ?? 'Couldn’t reach the research service — try again.'}
          </p>
          <button
            type="button"
            onClick={handleSubmit}
            className="mt-3 rounded-xl border border-[var(--warn-border)] bg-[var(--surface)] px-4 py-2 text-sm font-semibold text-[var(--text)] transition-colors hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            data-testid="retry"
          >
            Retry
          </button>
        </div>
      )}

      {phase === 'completed' && run && (
        <section className="mt-8" data-testid="results-area">
          {run.deals.length > 0 ? (
            <>
              <h2 className="mb-4 text-lg font-semibold text-[var(--text)]">
                Top {run.deals.length} deal{run.deals.length > 1 ? 's' : ''}
              </h2>
              <div className="space-y-3" data-testid="deal-list">
                {run.deals
                  .slice()
                  .sort((a, b) => a.rank - b.rank)
                  .map(deal => (
                    <DealCard key={`${deal.rank}-${deal.site}`} deal={deal} />
                  ))}
              </div>
            </>
          ) : (
            <p
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-muted)]"
              data-testid="no-deals"
            >
              No confident deals found for that — try a more specific {mode === 'category' ? 'category' : 'name'}.
            </p>
          )}
          <CostFooter
            promptTokens={run.prompt_tokens}
            completionTokens={run.completion_tokens}
            costInr={run.cost_inr}
          />
        </section>
      )}
    </main>
  )
}
