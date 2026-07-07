'use client'

import { useCallback, useEffect, useState } from 'react'
import { ApiError, listEngagements, type EngagementSummary } from '@/lib/api'
import { RunView } from '@/components/RunView'
import { ScopeForm } from '@/components/ScopeForm'
import { ErrorBanner, Header } from '@/components/ui'

type View = { name: 'list' } | { name: 'new' } | { name: 'run'; id: string }

export default function Home() {
  const [view, setView] = useState<View>({ name: 'list' })
  const [engagements, setEngagements] = useState<EngagementSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setError(null)
    listEngagements()
      .then(setEngagements)
      .catch((e) => {
        setEngagements([])
        setError(e instanceof ApiError ? e.message : 'Failed to load engagements.')
      })
  }, [])

  useEffect(() => {
    if (view.name === 'list') refresh()
  }, [view, refresh])

  return (
    <>
      <Header
        subtitle={
          view.name === 'new'
            ? 'New engagement — define scope'
            : view.name === 'run'
              ? 'Run view'
              : 'Security Assessment Console'
        }
      />
      <main className="mx-auto max-w-5xl px-6 py-8">
        {view.name === 'list' && (
          <EngagementsList
            engagements={engagements}
            error={error}
            onNew={() => setView({ name: 'new' })}
            onOpen={(id) => setView({ name: 'run', id })}
            onRetry={refresh}
          />
        )}
        {view.name === 'new' && (
          <section className="mx-auto max-w-2xl">
            <h2 className="mb-6 text-2xl font-semibold text-slate-50">New engagement</h2>
            <ScopeForm
              onCreated={(id) => setView({ name: 'run', id })}
              onCancel={() => setView({ name: 'list' })}
            />
          </section>
        )}
        {view.name === 'run' && (
          <RunView engagementId={view.id} onBack={() => setView({ name: 'list' })} />
        )}
      </main>
    </>
  )
}

function EngagementsList({
  engagements,
  error,
  onNew,
  onOpen,
  onRetry,
}: {
  engagements: EngagementSummary[] | null
  error: string | null
  onNew: () => void
  onOpen: (id: string) => void
  onRetry: () => void
}) {
  return (
    <section>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-slate-50">Engagements</h2>
        <button
          onClick={onNew}
          data-testid="new-engagement"
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          + New Engagement
        </button>
      </div>

      {error && (
        <div className="space-y-3">
          <ErrorBanner message={error} />
          <button onClick={onRetry} className="text-sm text-emerald-400 hover:text-emerald-300">
            Retry
          </button>
        </div>
      )}

      {!error && engagements === null && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl border border-slate-800 bg-slate-900/40" />
          ))}
        </div>
      )}

      {!error && engagements?.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/40 px-6 py-16 text-center">
          <p className="text-slate-300">No engagements yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Create a scope-gated engagement to start an authorized assessment.
          </p>
          <button
            onClick={onNew}
            className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            + New Engagement
          </button>
        </div>
      )}

      {!error && engagements && engagements.length > 0 && (
        <ul className="space-y-3">
          {engagements.map((e) => (
            <li key={e.engagement_id}>
              <button
                onClick={() => onOpen(e.engagement_id)}
                className="flex w-full items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 text-left transition hover:border-emerald-500/50 hover:bg-slate-900"
              >
                <div>
                  <p className="font-medium text-slate-100">{e.name}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {e.target_type} · created {formatDate(e.created_at)}
                  </p>
                </div>
                <StatusPill status={e.status} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    draft: 'bg-slate-700/50 text-slate-300',
    running: 'bg-amber-500/15 text-amber-300',
    complete: 'bg-emerald-500/15 text-emerald-300',
    completed: 'bg-emerald-500/15 text-emerald-300',
    failed: 'bg-red-500/15 text-red-300',
  }
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${map[status] ?? map.draft}`}>
      {status}
    </span>
  )
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}
