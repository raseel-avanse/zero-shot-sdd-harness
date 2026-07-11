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
      className="mt-6 border-t border-gray-200 pt-4 text-center text-sm text-gray-500"
      data-testid="cost-footer"
    >
      This query used{' '}
      <span className="font-medium text-gray-700">{total.toLocaleString('en-IN')}</span> tokens
      {costInr != null && (
        <>
          {' · approx '}
          <span className="font-medium text-gray-700">{formatCostInr(costInr)}</span>
        </>
      )}
    </footer>
  )
}
