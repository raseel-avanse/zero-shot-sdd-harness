'use client'

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ── Severity signal scale ──────────────────────────────────────────────────
// Meaningful (not decorative): drives rails, chips, tiles and the meter.
export type SeverityKey = 'critical' | 'high' | 'medium' | 'low' | 'info'

export const SEVERITY_ORDER: SeverityKey[] = ['critical', 'high', 'medium', 'low', 'info']

const SEVERITY: Record<SeverityKey, { solid: string; tint: string; ink: string }> = {
  critical: { solid: '#d92d20', tint: '#fef3f2', ink: '#912018' },
  high: { solid: '#dc6803', tint: '#fffaeb', ink: '#93370d' },
  medium: { solid: '#ca8504', tint: '#fefbe8', ink: '#854a0e' },
  low: { solid: '#475467', tint: '#f2f4f7', ink: '#344054' },
  info: { solid: '#4f46e5', tint: '#eef2ff', ink: '#3730a3' },
}

export function severityKey(label: string | null | undefined): SeverityKey {
  const k = (label ?? 'info').toLowerCase()
  return (SEVERITY_ORDER as string[]).includes(k) ? (k as SeverityKey) : 'info'
}

export function severityStyle(key: SeverityKey) {
  return SEVERITY[key]
}

// ── Icons (inline, no network) ──────────────────────────────────────────────
export function ShieldIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2l8 4v6c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-4z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  )
}

// ── Generic pill badge ───────────────────────────────────────────────────────
export function Badge({
  children,
  tone = 'neutral',
  mono = false,
}: {
  children: ReactNode
  tone?: 'neutral' | 'primary' | 'success' | 'warning'
  mono?: boolean
}) {
  const tones: Record<string, string> = {
    neutral: 'bg-canvas text-ink-muted ring-hairline',
    primary: 'bg-primary-tint text-primary ring-primary/25',
    success: 'text-[#067647] ring-[#067647]/25 bg-[#ecfdf3]',
    warning: 'text-[#b54708] ring-[#b54708]/25 bg-[#fffaeb]',
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${
        mono ? 'font-mono' : ''
      } ${tones[tone]}`}
    >
      {children}
    </span>
  )
}

// ── Severity chip (tinted) ───────────────────────────────────────────────────
export function SeverityChip({ label }: { label: string }) {
  const key = severityKey(label)
  const s = SEVERITY[key]
  const style: CSSProperties = { background: s.tint, color: s.ink, boxShadow: `inset 0 0 0 1px ${s.solid}33` }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
      style={style}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.solid }} />
      {label || 'info'}
    </span>
  )
}

/** Severity chip + a mono CVSS badge (technical data → mono). */
export function SeverityBadge({ label, cvss }: { label: string; cvss: number | null }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <SeverityChip label={label} />
      {cvss != null && (
        <span className="rounded-md bg-canvas px-1.5 py-0.5 font-mono text-[11px] font-semibold text-ink ring-1 ring-hairline">
          CVSS {cvss.toFixed(1)}
        </span>
      )}
    </span>
  )
}

const CONFIDENCE_STYLES: Record<string, string> = {
  confirmed: 'text-[#067647] ring-[#067647]/30 bg-[#ecfdf3]',
  tentative: 'text-[#b54708] ring-[#b54708]/30 bg-[#fffaeb]',
  unconfirmed: 'text-ink-muted ring-hairline bg-canvas',
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

// ── Severity summary tile (count per severity) ───────────────────────────────
export function Tile({ severity, count }: { severity: SeverityKey; count: number }) {
  const s = SEVERITY[severity]
  const on = count > 0
  return (
    <div
      className="flex flex-col gap-1 rounded-lg border p-3 transition"
      style={{
        borderColor: on ? `${s.solid}55` : 'var(--color-hairline)',
        background: on ? s.tint : 'var(--color-surface)',
      }}
    >
      <span className="font-mono text-2xl font-semibold leading-none" style={{ color: on ? s.ink : '#98a2b3' }}>
        {count}
      </span>
      <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: on ? s.ink : '#98a2b3' }}>
        {severity}
      </span>
    </div>
  )
}

// ── Surface card ─────────────────────────────────────────────────────────────
export function Card({
  children,
  className = '',
  ...rest
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-xl border border-hairline bg-surface shadow-sm ${className}`} {...rest}>
      {children}
    </div>
  )
}

/** Clearly-labelled non-functional stub for a later phase. */
export function StubBadge({ phase }: { phase: 'P2' | 'P3' }) {
  return (
    <Badge tone="warning">Coming in Phase {phase[1]} · not yet functional</Badge>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-[#fda29b] bg-[#fef3f2] px-4 py-3 text-sm text-[#912018]"
    >
      {message}
    </div>
  )
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-console text-sm leading-relaxed text-ink">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ''}</ReactMarkdown>
    </div>
  )
}
