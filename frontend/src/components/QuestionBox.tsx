'use client'

import { useState } from 'react'

interface Props {
  disabled: boolean
  running: boolean
  onAsk: (question: string) => void
}

export default function QuestionBox({ disabled, running, onAsk }: Props) {
  const [value, setValue] = useState('')
  const canAsk = !disabled && !running && value.trim().length > 0

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canAsk) return
    onAsk(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={submit} className="flex gap-2" data-testid="question-box">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        disabled={disabled || running}
        placeholder={
          disabled ? 'Upload a dataset to ask a question…' : 'Ask a question about your data…'
        }
        aria-label="Question"
        data-testid="question-input"
        className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      <button
        type="submit"
        disabled={!canAsk}
        data-testid="ask-button"
        className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {running ? 'Asking…' : 'Ask'}
      </button>
    </form>
  )
}
