import type { ProgressStep } from '@/lib/api'

// Ordered named steps that reflect real backend work. The P2 "assessing" step
// (deal-quality-flag) sits between ranking and done.
const STEPS: { key: ProgressStep; label: string; short: string }[] = [
  { key: 'searching', label: 'Searching Indian shopping sites…', short: 'Search' },
  { key: 'reviewing', label: 'Reading reviews & cross-checking prices…', short: 'Review' },
  { key: 'ranking', label: 'Ranking deals…', short: 'Rank' },
  { key: 'assessing', label: 'Checking deal quality…', short: 'Assess' },
  { key: 'done', label: 'Finishing up…', short: 'Finish' },
]

function stepIndex(step: ProgressStep | null): number {
  if (!step || step === 'queued') return 0
  const i = STEPS.findIndex(s => s.key === step)
  return i === -1 ? 0 : i
}

export default function ProgressBar({ step }: { step: ProgressStep | null }) {
  const current = stepIndex(step)
  const pct = Math.round(((current + 1) / STEPS.length) * 100)
  const currentLabel = STEPS[Math.min(current, STEPS.length - 1)].label

  return (
    <section
      className="ds-animate-in mt-8 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm"
      aria-live="polite"
      aria-busy="true"
      data-testid="progress-area"
    >
      <div className="mb-4 flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-[var(--accent)] motion-reduce:animate-none"
        />
        <p className="text-sm font-medium text-[var(--text)]" data-testid="progress-label">
          {currentLabel}
        </p>
      </div>

      <div className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Research progress"
        />
      </div>

      <ol className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
        {STEPS.map((s, i) => (
          <li
            key={s.key}
            className={[
              'flex items-center gap-1.5',
              i < current
                ? 'text-[var(--pos-fg)]'
                : i === current
                  ? 'font-semibold text-[var(--accent)]'
                  : 'text-[var(--text-faint)]',
            ].join(' ')}
          >
            <span aria-hidden="true">{i < current ? '✓' : i === current ? '●' : '○'}</span>
            {s.short}
          </li>
        ))}
      </ol>
    </section>
  )
}
