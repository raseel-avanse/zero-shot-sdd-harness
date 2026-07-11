import { formatCostInr } from '@/lib/api'

export default function CostFooter({
  promptTokens,
  completionTokens,
  costInr,
}: {
  promptTokens: number
  completionTokens: number
  costInr: number | null
}) {
  const total = promptTokens + completionTokens
  return (
    <footer
      className="mt-6 flex items-center justify-center gap-2 border-t border-[var(--border)] pt-4 text-center text-xs text-[var(--text-faint)]"
      data-testid="cost-footer"
    >
      <span aria-hidden="true">◆</span>
      <span>
        This query used{' '}
        <span className="font-semibold tabular-nums text-[var(--text-muted)]">
          {total.toLocaleString('en-IN')}
        </span>{' '}
        tokens
        {costInr != null && (
          <>
            {' · approx '}
            <span className="font-semibold tabular-nums text-[var(--text-muted)]">
              {formatCostInr(costInr)}
            </span>
          </>
        )}
      </span>
    </footer>
  )
}
