import type { Deal } from '@/lib/api'
import { formatInr } from '@/lib/api'
import QualityBadge from './QualityBadge'

export default function DealCard({ deal }: { deal: Deal }) {
  return (
    <article
      className="ds-animate-in group relative flex gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-6"
      data-testid="deal-card"
    >
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-base font-bold text-[var(--accent)]"
        aria-label={`Rank ${deal.rank}`}
      >
        {deal.rank}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className="text-base font-semibold text-[var(--text)]" data-testid="deal-site">
            {deal.source_url ? (
              <a
                href={deal.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded text-[var(--accent)] underline decoration-transparent underline-offset-4 transition-colors hover:decoration-current focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              >
                {deal.site}
              </a>
            ) : (
              deal.site
            )}
          </h3>
          <span
            className="text-lg font-bold tabular-nums text-[var(--text)]"
            data-testid="deal-price"
          >
            {formatInr(deal.price_inr)}
          </span>
        </div>

        <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-muted)]" data-testid="deal-reason">
          {deal.reason}
        </p>

        <div className="mt-3 flex flex-col gap-1.5">
          <QualityBadge label={deal.quality_label} />
          {deal.quality_reason && (
            <p className="text-xs leading-relaxed text-[var(--text-faint)]" data-testid="quality-reason">
              {deal.quality_reason}
            </p>
          )}
        </div>
      </div>
    </article>
  )
}
