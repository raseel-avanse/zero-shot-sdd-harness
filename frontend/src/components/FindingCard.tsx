'use client'

import { useState } from 'react'
import {
  ApiError,
  retestFinding,
  updateFindingStatus,
  type Finding,
  type FindingStatus,
} from '@/lib/api'
import { ConfidenceBadge, Markdown, SeverityBadge } from './ui'

const STATUS_LABELS: FindingStatus[] = ['new', 'validated', 'remediated', 'false_positive']

export function FindingCard({
  finding,
  patternLabel,
  onRetested,
  onStatusChanged,
}: {
  finding: Finding
  /** Set when this finding shares a `pattern_ref` with others — flags the group. */
  patternLabel?: string
  onRetested?: (id: string, status: string, confidence: string, evidence?: string) => void
  onStatusChanged?: (id: string, status: string) => void
}) {
  const [retesting, setRetesting] = useState(false)
  const [retestError, setRetestError] = useState<string | null>(null)
  const [retestNote, setRetestNote] = useState<string | null>(null)
  const [statusUpdating, setStatusUpdating] = useState<FindingStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)

  async function handleStatus(next: FindingStatus) {
    if (next === finding.status || statusUpdating) return
    setStatusError(null)
    setStatusUpdating(next)
    try {
      const updated = await updateFindingStatus(finding.id, next)
      onStatusChanged?.(finding.id, updated.status ?? next)
    } catch (err) {
      setStatusError(err instanceof ApiError ? err.message : 'Could not update status.')
    } finally {
      setStatusUpdating(null)
    }
  }

  async function handleRetest() {
    setRetestError(null)
    setRetestNote(null)
    setRetesting(true)
    try {
      const res = await retestFinding(finding.id)
      onRetested?.(res.finding_id, res.status, res.confidence, res.evidence)
      setRetestNote(
        res.status === 'remediated'
          ? 'Re-test passed — the PoC no longer reproduces. Marked remediated.'
          : `Re-test complete — status: ${res.status.replace('_', ' ')}, confidence: ${res.confidence}.`,
      )
    } catch (err) {
      setRetestError(err instanceof ApiError ? err.message : 'Re-test failed.')
    } finally {
      setRetesting(false)
    }
  }

  return (
    <article
      data-testid="finding-card"
      className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg shadow-black/20"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge label={finding.severity_label} cvss={finding.cvss_score} />
            <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-300">
              {finding.category}
            </span>
            <ConfidenceBadge confidence={finding.confidence} />
            {patternLabel && (
              <span
                data-testid="pattern-flag"
                title="Same vulnerability pattern found elsewhere in this target"
                className="inline-flex items-center gap-1 rounded-md bg-fuchsia-500/10 px-2 py-0.5 text-[11px] font-medium text-fuchsia-300 ring-1 ring-fuchsia-500/30"
              >
                ⛓ {patternLabel}
              </span>
            )}
          </div>
          <h3 className="mt-2 text-base font-semibold text-slate-50">{finding.title}</h3>
          <p className="mt-0.5 font-mono text-xs text-emerald-400" data-testid="finding-location">
            {finding.location}
          </p>
        </div>
      </div>

      {finding.description && (
        <Section title="Description">
          <Markdown>{finding.description}</Markdown>
        </Section>
      )}

      {finding.evidence && (
        <Section title="Evidence / PoC">
          <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-300 ring-1 ring-slate-800">
            {finding.evidence}
          </pre>
        </Section>
      )}

      {finding.remediation && (
        <Section title="Remediation">
          <Markdown>{finding.remediation}</Markdown>
        </Section>
      )}

      {finding.suggested_patch && (
        <Section title="Suggested patch">
          <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-xs leading-relaxed ring-1 ring-slate-800">
            <DiffBlock patch={finding.suggested_patch} />
          </pre>
        </Section>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3">
        {/* Finding status lifecycle — click to transition; persists via PATCH. */}
        <div className="flex items-center gap-1.5" data-testid="status-controls" role="group" aria-label="Finding status">
          {STATUS_LABELS.map((s) => {
            const active = s === finding.status
            const busy = statusUpdating === s
            return (
              <button
                key={s}
                type="button"
                onClick={() => handleStatus(s)}
                disabled={active || statusUpdating !== null}
                aria-pressed={active}
                data-testid={active ? 'finding-status-active' : `status-${s}`}
                className={`rounded px-2 py-0.5 text-[11px] transition ${
                  active
                    ? 'bg-emerald-600/25 text-emerald-200 ring-1 ring-emerald-500/40'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-700 hover:text-slate-100 disabled:opacity-50'
                }`}
                title={active ? `Current status: ${s.replace('_', ' ')}` : `Mark as ${s.replace('_', ' ')}`}
              >
                {busy ? 'Saving…' : s.replace('_', ' ')}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={handleRetest}
          disabled={retesting}
          data-testid="retest-button"
          className="rounded-md border border-emerald-600/50 px-3 py-1 text-xs font-medium text-emerald-300 hover:bg-emerald-600/10 disabled:opacity-50"
          title="Re-run validation against the current target state to confirm a fix"
        >
          {retesting ? 'Re-testing…' : 'Re-test after fix'}
        </button>
      </div>

      {retestNote && (
        <p className="mt-2 text-xs text-emerald-400" data-testid="retest-note">
          {retestNote}
        </p>
      )}
      {retestError && (
        <p className="mt-2 text-xs text-red-400" role="alert">
          {retestError}
        </p>
      )}
      {statusError && (
        <p className="mt-2 text-xs text-red-400" role="alert">
          {statusError}
        </p>
      )}
    </article>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</h4>
      {children}
    </div>
  )
}

function DiffBlock({ patch }: { patch: string }) {
  return (
    <code>
      {patch.split('\n').map((line, i) => {
        let color = 'text-slate-400'
        if (line.startsWith('+') && !line.startsWith('+++')) color = 'text-emerald-400'
        else if (line.startsWith('-') && !line.startsWith('---')) color = 'text-red-400'
        else if (line.startsWith('@@')) color = 'text-sky-400'
        return (
          <span key={i} className={`block ${color}`}>
            {line || ' '}
          </span>
        )
      })}
    </code>
  )
}
