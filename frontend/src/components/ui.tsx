'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function Header({ subtitle }: { subtitle?: string }) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
        <span className="grid h-9 w-9 place-items-center rounded-md bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30">
          <ShieldIcon />
        </span>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-50">Sentinel</h1>
          <p className="text-xs text-slate-400">{subtitle ?? 'Security Assessment Console'}</p>
        </div>
      </div>
    </header>
  )
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 2l8 4v6c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-4z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  )
}

/** Clearly-labelled non-functional stub for a later phase. */
export function StubBadge({ phase }: { phase: 'P2' | 'P3' }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400 ring-1 ring-amber-500/30"
      title={`Coming in Phase ${phase[1]} — not yet functional`}
    >
      Coming in Phase {phase[1]} · not yet functional
    </span>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
    >
      {message}
    </div>
  )
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-300 ring-red-500/40',
  high: 'bg-orange-500/15 text-orange-300 ring-orange-500/40',
  medium: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
  low: 'bg-sky-500/15 text-sky-300 ring-sky-500/40',
  info: 'bg-slate-500/15 text-slate-300 ring-slate-500/40',
}

export function SeverityBadge({ label, cvss }: { label: string; cvss: number | null }) {
  const key = (label || 'info').toLowerCase()
  const cls = SEVERITY_STYLES[key] ?? SEVERITY_STYLES.info
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ${cls}`}>
      {label || 'info'}
      {cvss != null && <span className="font-mono text-[11px] opacity-80">CVSS {cvss.toFixed(1)}</span>}
    </span>
  )
}

const CONFIDENCE_STYLES: Record<string, string> = {
  confirmed: 'text-emerald-400 ring-emerald-500/40',
  tentative: 'text-amber-400 ring-amber-500/40',
  unconfirmed: 'text-slate-400 ring-slate-500/40',
}

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const key = (confidence || 'unconfirmed').toLowerCase()
  const cls = CONFIDENCE_STYLES[key] ?? CONFIDENCE_STYLES.unconfirmed
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${cls}`}>
      {confidence || 'unconfirmed'}
    </span>
  )
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-console text-sm leading-relaxed text-slate-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ''}</ReactMarkdown>
    </div>
  )
}
