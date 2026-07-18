import type { QualityLabel } from '@/lib/api'

interface Style {
  text: string
  cls: string
  dot: string
  icon: string
}

const STYLES: Record<string, Style> = {
  genuine_discount: {
    text: 'Genuine discount',
    cls: 'bg-[var(--pos-bg)] text-[var(--pos-fg)] border-[var(--pos-border)]',
    dot: 'bg-[var(--pos-fg)]',
    icon: '↓',
  },
  wait: {
    text: 'Wait — usually cheaper',
    cls: 'bg-[var(--warn-bg)] text-[var(--warn-fg)] border-[var(--warn-border)]',
    dot: 'bg-[var(--warn-fg)]',
    icon: '⏳',
  },
  unknown: {
    text: 'Price check unavailable',
    cls: 'bg-[var(--neutral-bg)] text-[var(--neutral-fg)] border-[var(--neutral-border)]',
    dot: 'bg-[var(--neutral-fg)]',
    icon: '—',
  },
}

export default function QualityBadge({
  label,
}: {
  label: QualityLabel | string | null
}) {
  const style = (label && STYLES[label]) || STYLES.unknown
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${style.cls}`}
      data-testid="quality-badge"
      data-label={label ?? 'unknown'}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.text}
    </span>
  )
}
