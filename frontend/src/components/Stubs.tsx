'use client'

interface StubButtonProps {
  label: string
  phase: string
}

// A clearly-disabled, non-functional control advertising a future feature.
export function StubButton({ label, phase }: StubButtonProps) {
  return (
    <button
      type="button"
      disabled
      aria-disabled="true"
      title={`Coming soon — ${phase}`}
      data-testid="stub-button"
      className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-400"
    >
      {label}
      <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-gray-500">
        Coming soon
      </span>
    </button>
  )
}

// Panel of alternative data sources — all stubs in Phase 1.
export function SourceStubs() {
  return (
    <section
      aria-label="More data sources (coming soon)"
      className="rounded-xl border border-dashed border-gray-200 bg-white/60 p-4"
      data-testid="source-stubs"
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-400">More data sources</p>
      <div className="flex flex-wrap gap-2">
        <StubButton label="Connect Google Sheets" phase="Phase 3" />
        <StubButton label="Connect JSON API" phase="Phase 3" />
        <StubButton label="Live database" phase="Phase 4" />
      </div>
    </section>
  )
}
