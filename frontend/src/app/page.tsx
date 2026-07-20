'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, listEngagements, type EngagementSummary } from '@/lib/api'
import { RunView } from '@/components/RunView'
import { ScopeForm } from '@/components/ScopeForm'
import { AppShell, type SessionInfo, type ViewName } from '@/components/shell'
import { Badge, Card, ErrorBanner } from '@/components/ui'

type View = { name: 'list' } | { name: 'new' } | { name: 'run'; id: string }

const IDLE_SESSION: SessionInfo = { running: false, cost: 0, model: 'Gemini' }

export default function Home() {
  const [view, setView] = useState<View>({ name: 'list' })
  const [engagements, setEngagements] = useState<EngagementSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [session, setSession] = useState<SessionInfo>(IDLE_SESSION)
  const [runContext, setRunContext] = useState<string>('')

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

  // Reset the shell session/context when leaving the run view.
  const navigate = useCallback((next: ViewName) => {
    if (next !== 'run') {
      setSession(IDLE_SESSION)
      setRunContext('')
    }
    setView(next === 'new' ? { name: 'new' } : { name: 'list' })
  }, [])

  const breadcrumb = useMemo(() => {
    if (view.name === 'new') return 'New engagement'
    if (view.name === 'run') return `Engagements / ${runContext || 'Assessment'}`
    return 'Engagements'
  }, [view, runContext])

  const activeNav = view.name === 'new' ? 'new' : 'engagements'

  const handleReport = useCallback((info: { name?: string; running: boolean; cost: number }) => {
    setSession({ running: info.running, cost: info.cost, model: 'Gemini' })
    if (info.name) setRunContext(info.name)
  }, [])

  return (
    <AppShell
      active={view.name}
      activeNav={activeNav}
      breadcrumb={breadcrumb}
      session={session}
      onNavigate={navigate}
    >
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
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-ink-strong">New engagement</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Define the authorized scope. Sentinel refuses anything outside it in code.
            </p>
          </div>
          <ScopeForm
            onCreated={(id) => setView({ name: 'run', id })}
            onCancel={() => setView({ name: 'list' })}
          />
        </section>
      )}
      {view.name === 'run' && (
        <RunView engagementId={view.id} onBack={() => navigate('list')} onReport={handleReport} />
      )}
    </AppShell>
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
        <div>
          <h2 className="text-2xl font-semibold text-ink-strong">Engagements</h2>
          <p className="mt-1 text-sm text-ink-muted">Scope-gated, authorized security assessments.</p>
        </div>
        <button
          onClick={onNew}
          data-testid="new-engagement"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-hover"
        >
          New engagement
        </button>
      </div>

      {error && (
        <div className="space-y-3">
          <ErrorBanner message={error} />
          <button onClick={onRetry} className="text-sm font-medium text-primary hover:text-primary-hover">
            Retry
          </button>
        </div>
      )}

      {!error && engagements === null && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[76px] animate-pulse rounded-xl border border-hairline bg-surface" />
          ))}
        </div>
      )}

      {!error && engagements?.length === 0 && (
        <Card className="px-6 py-16 text-center">
          <p className="text-sm font-medium text-ink-strong">No engagements yet</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-ink-muted">
            No engagements yet — create one to begin an authorized, scope-gated assessment.
          </p>
          <button
            onClick={onNew}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-hover"
          >
            New engagement
          </button>
        </Card>
      )}

      {!error && engagements && engagements.length > 0 && (
        <ul className="space-y-3">
          {engagements.map((e) => (
            <li key={e.engagement_id}>
              <button
                onClick={() => onOpen(e.engagement_id)}
                className="flex w-full items-center justify-between rounded-xl border border-hairline bg-surface px-5 py-4 text-left shadow-sm transition hover:border-primary/40 hover:shadow-md"
              >
                <div className="min-w-0">
                  <p className="font-medium text-ink-strong">{e.name}</p>
                  <p className="mt-0.5 font-mono text-xs text-ink-muted">
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
  const tone: Record<string, 'neutral' | 'primary' | 'success' | 'warning'> = {
    draft: 'neutral',
    running: 'warning',
    complete: 'success',
    completed: 'success',
    failed: 'warning',
  }
  return <Badge tone={tone[status] ?? 'neutral'}>{status}</Badge>
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}
