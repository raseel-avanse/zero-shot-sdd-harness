'use client'

import { useEffect, useRef, useState } from 'react'
import { startRun, pollRun, type RunResult } from '@/lib/api'
import ProgressBar from '@/components/ProgressBar'
import DealCard from '@/components/DealCard'
import CostFooter from '@/components/CostFooter'
import StubInputs from '@/components/StubInputs'

const POLL_MS = 1500

type Phase = 'empty' | 'running' | 'completed' | 'failed'

export default function Home() {
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<Phase>('empty')
  const [run, setRun] = useState<RunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
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
      } else {
        pollRef.current = setTimeout(() => tick(runId), POLL_MS)
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Couldn’t reach the research service — try again.',
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
      const started = await startRun(text)
      pollRef.current = setTimeout(() => tick(started.run_id), POLL_MS)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Couldn’t reach the research service — try again.',
      )
      setPhase('failed')
    }
  }

  const isRunning = phase === 'running'

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">DealScout</h1>
        <p className="mt-2 text-sm text-gray-500">
          Find the best deal across Indian shopping sites.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="product-name" className="mb-1.5 block text-sm font-medium text-gray-700">
            Product name
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="product-name"
              type="text"
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
              placeholder="e.g. Sony WH-1000XM5 headphones"
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={isRunning}
              autoComplete="off"
              data-testid="query-input"
            />
            <button
              type="submit"
              disabled={isRunning || !query.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:opacity-50"
              data-testid="find-deals"
            >
              {isRunning ? 'Finding deals…' : 'Find deals'}
            </button>
          </div>
        </div>
        <StubInputs />
      </form>

      {phase === 'empty' && (
        <p className="mt-12 text-center text-sm text-gray-400" data-testid="empty-state">
          Type a product name to find the best deals across Indian shopping sites.
        </p>
      )}

      {isRunning && <ProgressBar step={run?.progress_step ?? 'queued'} />}

      {phase === 'failed' && (
        <div
          className="mt-8 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700"
          role="alert"
          data-testid="error-state"
        >
          <p className="font-medium">{error ?? 'Something went wrong.'}</p>
          <button
            type="button"
            onClick={handleSubmit}
            className="mt-3 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
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
              <h2 className="mb-4 text-lg font-semibold text-gray-900">
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
              className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-500"
              data-testid="no-deals"
            >
              No confident deals found for that — try a more specific name.
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
