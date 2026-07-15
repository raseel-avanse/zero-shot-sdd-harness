'use client'

import { useState } from 'react'
import {
  ApiError,
  retestFinding,
  updateFindingStatus,
  type Finding,
  type FindingStatus,
} from '@/lib/api'
import { ConfidenceBadge, Markdown, SeverityBadge, severityKey, severityStyle } from './ui'
import { owaspRefId } from '@/lib/owasp'

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

  const sev = severityStyle(severityKey(finding.severity_label))
  const owaspRef = finding.owasp_api_ref?.trim() || null
  const owaspId = owaspRefId(owaspRef)

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
      className="animate-stream-in overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm"
    >
      <div className="flex">
        {/* Severity rail */}
        <div className="w-1.5 shrink-0" style={{ background: sev.solid }} aria-hidden="true" />

        <div className="min-w-0 flex-1 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge label={finding.severity_label} cvss={finding.cvss_score} />
                <span className="rounded-md bg-canvas px-2 py-0.5 text-[11px] font-medium text-ink ring-1 ring-hairline">
                  {finding.category}
                </span>
                <ConfidenceBadge confidence={finding.confidence} />
                {owaspRef && (
                  <span
                    data-testid="owasp-badge"
                    title={`OWASP API Security Top 10 (2023): ${owaspRef}`}
                    data-owasp-id={owaspId ?? undefined}
                    className="inline-flex items-center gap-1 rounded-md bg-[#eef2ff] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#3730a3] ring-1 ring-[#4f46e5]/30"
                  >
                    {owaspRef}
                  </span>
                )}
                {patternLabel && (
                  <span
                    data-testid="pattern-flag"
                    title="Same vulnerability pattern found elsewhere in this target"
                    className="inline-flex items-center gap-1 rounded-md bg-[#fdf4ff] px-2 py-0.5 text-[11px] font-medium text-[#a21caf] ring-1 ring-[#a21caf]/25"
                  >
                    ⛓ {patternLabel}
                  </span>
                )}
              </div>
              <h3 className="mt-2 text-base font-semibold text-ink-strong">{finding.title}</h3>
              <p className="mt-0.5 font-mono text-xs text-primary" data-testid="finding-location">
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
              <pre className="overflow-x-auto rounded-lg bg-ink-strong p-3 font-mono text-xs text-slate-200 ring-1 ring-hairline">
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
              <pre className="overflow-x-auto rounded-lg bg-ink-strong p-3 font-mono text-xs leading-relaxed ring-1 ring-hairline">
                <DiffBlock patch={finding.suggested_patch} />
              </pre>
            </Section>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-hairline pt-3">
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
                        ? 'bg-primary-tint text-primary ring-1 ring-primary/30'
                        : 'bg-canvas text-ink-muted ring-1 ring-hairline hover:bg-primary-tint hover:text-primary disabled:opacity-50'
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
              className="rounded-md border border-primary/40 px-3 py-1 text-xs font-medium text-primary transition hover:bg-primary-tint disabled:opacity-50"
              title="Re-run validation against the current target state to confirm a fix"
            >
              {retesting ? 'Re-testing…' : 'Re-test after fix'}
            </button>
          </div>

          {retestNote && (
            <p className="mt-2 text-xs text-success" data-testid="retest-note">
              {retestNote}
            </p>
          )}
          {retestError && (
            <p className="mt-2 text-xs text-[#912018]" role="alert">
              {retestError}
            </p>
          )}
          {statusError && (
            <p className="mt-2 text-xs text-[#912018]" role="alert">
              {statusError}
            </p>
          )}
        </div>
      </div>
    </article>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">{title}</h4>
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
