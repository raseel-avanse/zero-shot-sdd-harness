// Phase 1 labelled, non-functional stubs. They render the product vision so the
// user sees where DealScout is heading, but are visibly greyed and tagged
// "Coming soon" so they are never mistaken for broken features. Activated in
// Phase 2 (url-input-research, category-exploration, clarifying-question-gate).

function ComingSoonTag() {
  return (
    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      Coming soon
    </span>
  )
}

export default function StubInputs() {
  return (
    <div className="mt-3 space-y-3" data-testid="stub-inputs">
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 opacity-70">
        <div className="mb-1.5 flex items-center gap-2">
          <label
            htmlFor="stub-url"
            className="text-sm font-medium text-gray-500"
          >
            Paste a product URL
          </label>
          <ComingSoonTag />
        </div>
        <input
          id="stub-url"
          type="text"
          disabled
          aria-disabled="true"
          placeholder="https://www.amazon.in/…"
          className="w-full cursor-not-allowed rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-400"
          data-testid="stub-url"
        />
      </div>

      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 opacity-70">
        <div className="mb-1.5 flex items-center gap-2">
          <label
            htmlFor="stub-category"
            className="text-sm font-medium text-gray-500"
          >
            Explore a category
          </label>
          <ComingSoonTag />
        </div>
        <input
          id="stub-category"
          type="text"
          disabled
          aria-disabled="true"
          placeholder="e.g. wireless earbuds under ₹5000"
          className="w-full cursor-not-allowed rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-400"
          data-testid="stub-category"
        />
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 text-sm text-gray-400 opacity-70">
        <span>DealScout may ask one clarifying question when your query is ambiguous.</span>
        <ComingSoonTag />
      </div>
    </div>
  )
}
