import type { QueryType } from '@/lib/api'

export interface Mode {
  key: QueryType
  label: string
  hint: string
}

export const MODES: Mode[] = [
  {
    key: 'name',
    label: 'Product name',
    hint: 'Search by the product you have in mind.',
  },
  {
    key: 'url',
    label: 'Product URL',
    hint: 'Paste a listing link — we identify it and compare it across sites.',
  },
  {
    key: 'category',
    label: 'Category',
    hint: 'Explore a category and see the best-value picks.',
  },
]

export default function ModeTabs({
  mode,
  onChange,
  disabled,
}: {
  mode: QueryType
  onChange: (m: QueryType) => void
  disabled?: boolean
}) {
  return (
    <div
      role="tablist"
      aria-label="Search mode"
      className="inline-flex w-full gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-1"
      data-testid="mode-tabs"
    >
      {MODES.map(m => {
        const active = m.key === mode
        return (
          <button
            key={m.key}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            onClick={() => onChange(m.key)}
            data-testid={`mode-${m.key}`}
            data-active={active}
            className={[
              'flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--surface-2)]',
              'disabled:cursor-not-allowed disabled:opacity-50',
              active
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm'
                : 'text-[var(--text-muted)] hover:text-[var(--text)]',
            ].join(' ')}
          >
            {m.label}
          </button>
        )
      })}
    </div>
  )
}
