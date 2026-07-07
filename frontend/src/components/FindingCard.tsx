'use client'

import type { Finding } from '@/lib/api'
import { ConfidenceBadge, Markdown, SeverityBadge, StubBadge } from './ui'

const STATUS_LABELS = ['new', 'validated', 'remediated', 'false_positive']

export function FindingCard({ finding }: { finding: Finding }) {
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
        {/* Read-only status controls — P3 stub */}
        <div className="flex items-center gap-1.5">
          {STATUS_LABELS.map((s) => (
            <span
              key={s}
              className={`rounded px-2 py-0.5 text-[11px] ${
                s === finding.status
                  ? 'bg-slate-700 text-slate-100'
                  : 'bg-slate-800/40 text-slate-500'
              }`}
            >
              {s.replace('_', ' ')}
            </span>
          ))}
          <StubBadge phase="P3" />
        </div>
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-500"
          title="Re-test after fix — coming in Phase 2"
        >
          Re-test after fix
        </button>
        <StubBadge phase="P2" />
      </div>
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
