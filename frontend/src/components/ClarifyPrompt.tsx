'use client'

import { useState } from 'react'

export default function ClarifyPrompt({
  question,
  onSubmit,
  submitting,
}: {
  question: string
  onSubmit: (answer: string) => void
  submitting?: boolean
}) {
  const [answer, setAnswer] = useState('')

  function handle(e: React.FormEvent) {
    e.preventDefault()
    const text = answer.trim()
    if (!text || submitting) return
    onSubmit(text)
  }

  return (
    <section
      className="ds-animate-in mt-8 rounded-2xl border border-[var(--accent-soft)] bg-[var(--accent-soft)] p-6 shadow-sm"
      data-testid="clarify-prompt"
      aria-live="polite"
    >
      <div className="mb-3 flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-bold text-[var(--accent-fg)]"
        >
          ?
        </span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
            One quick question
          </p>
          <p
            className="mt-1 text-sm font-medium leading-relaxed text-[var(--text)]"
            data-testid="clarify-question"
          >
            {question}
          </p>
        </div>
      </div>

      <form onSubmit={handle} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label htmlFor="clarify-answer" className="sr-only">
          Your answer
        </label>
        <input
          id="clarify-answer"
          type="text"
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          disabled={submitting}
          autoComplete="off"
          autoFocus
          placeholder="Type your answer…"
          data-testid="clarify-input"
          className="flex-1 rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3.5 py-2.5 text-sm text-[var(--text)] shadow-sm transition-colors placeholder:text-[var(--text-faint)] focus:border-[var(--accent)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={submitting || !answer.trim()}
          data-testid="clarify-continue"
          className="rounded-xl bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-[var(--accent-fg)] shadow-sm transition-colors hover:bg-[var(--accent-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--accent-soft)] disabled:opacity-50"
        >
          {submitting ? 'Continuing…' : 'Continue'}
        </button>
      </form>
    </section>
  )
}
