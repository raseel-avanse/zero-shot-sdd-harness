import type { ProgressStep } from '@/lib/api'

// Ordered named steps that reflect real backend work (research-progress spec).
const STEPS: { key: ProgressStep; label: string }[] = [
  { key: 'searching', label: 'Searching Indian shopping sites…' },
  { key: 'reviewing', label: 'Reading reviews & cross-checking prices…' },
  { key: 'ranking', label: 'Ranking deals…' },
  { key: 'done', label: 'Finishing up…' },
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
      className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
      aria-live="polite"
      aria-busy="true"
      data-testid="progress-area"
    >
      <p className="mb-4 text-sm font-medium text-gray-800" data-testid="progress-label">
        {currentLabel}
      </p>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bg-blue-600 transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Research progress"
        />
      </div>
      <ol className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {STEPS.map((s, i) => (
          <li
            key={s.key}
            className={
              i < current
                ? 'text-green-600'
                : i === current
                  ? 'font-semibold text-blue-700'
                  : 'text-gray-400'
            }
          >
            {i < current ? '✓ ' : i === current ? '● ' : '○ '}
            {s.label.replace('…', '')}
          </li>
        ))}
      </ol>
    </section>
  )
}
