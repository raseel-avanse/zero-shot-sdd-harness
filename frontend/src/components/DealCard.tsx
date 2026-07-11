import type { Deal } from '@/lib/api'
import { formatInr } from '@/lib/api'

export default function DealCard({ deal }: { deal: Deal }) {
  return (
    <article
      className="flex gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
      data-testid="deal-card"
    >
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white"
        aria-label={`Rank ${deal.rank}`}
      >
        {deal.rank}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 className="text-base font-semibold text-gray-900" data-testid="deal-site">
            {deal.source_url ? (
              <a
                href={deal.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded text-blue-700 underline decoration-blue-300 underline-offset-2 hover:decoration-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                {deal.site}
              </a>
            ) : (
              deal.site
            )}
          </h3>
          <span className="text-lg font-bold text-gray-900" data-testid="deal-price">
            {formatInr(deal.price_inr)}
          </span>
        </div>
        <p className="mt-1 text-sm text-gray-600" data-testid="deal-reason">
          {deal.reason}
        </p>
        {/* Phase 1 labelled stub: deal-quality badge. Becomes real in Phase 2. */}
        <span
          className="mt-3 inline-block cursor-not-allowed rounded-full border border-dashed border-gray-300 bg-gray-50 px-2.5 py-0.5 text-xs text-gray-400"
          title="Deal-quality assessment arrives in Phase 2"
          aria-disabled="true"
          data-testid="quality-stub"
        >
          Deal quality · Coming soon
        </span>
      </div>
    </article>
  )
}
