'use client'

import { useState } from 'react'
import type { AnswerResult } from '@/lib/api'
import StepStatus from './StepStatus'
import Chart from './Chart'
import { StubButton } from './Stubs'

export interface HistoryItem {
  id: string
  question: string
  status: 'running' | 'done' | 'failed'
  result: AnswerResult | null
  error: string | null
}

interface Props {
  item: HistoryItem
}

function TokenBadge({ prompt, completion, total }: { prompt: number; completion: number; total: number }) {
  const [open, setOpen] = useState(false)
  return (
    <button
      type="button"
      onClick={() => setOpen(o => !o)}
      title={`prompt ${prompt} · completion ${completion}`}
      data-testid="token-badge"
      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-100"
    >
      <span className="font-medium tabular-nums">{total.toLocaleString()}</span> tokens
      {open && (
        <span className="text-gray-400">
          ({prompt} + {completion})
        </span>
      )}
    </button>
  )
}

export default function AnswerCard({ item }: Props) {
  const [showCode, setShowCode] = useState(false)
  const { question, status, result, error } = item

  return (
    <article
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
      data-testid="answer-card"
      data-status={status}
    >
      <p className="text-sm font-medium text-gray-500">Q</p>
      <p className="mb-4 text-base font-semibold text-gray-900" data-testid="answer-question">
        {question}
      </p>

      {status === 'running' && <StepStatus inFlight trace={null} />}

      {status === 'failed' && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          data-testid="answer-error"
        >
          {error ?? 'This question failed to run.'}
        </div>
      )}

      {status === 'done' && result && (
        <div className="space-y-4">
          <p className="whitespace-pre-wrap text-base leading-relaxed text-gray-900" data-testid="answer-text">
            {result.answer}
          </p>

          {result.method_note && (
            <p className="text-sm text-gray-500" data-testid="method-note">
              <span className="font-medium text-gray-600">How: </span>
              {result.method_note}
            </p>
          )}

          {result.used_fallback && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800" data-testid="fallback-flag">
              Computed from a sample (approximate).
            </div>
          )}

          {result.assumptions.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="assumptions">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">Assumptions</p>
              <ul className="list-inside list-disc space-y-1 text-sm text-amber-900">
                {result.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {result.chart_spec && <Chart spec={result.chart_spec} />}

          <div>
            <button
              type="button"
              onClick={() => setShowCode(s => !s)}
              data-testid="show-code-toggle"
              className="text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              {showCode ? 'Hide code' : 'Show code'}
            </button>
            {showCode && (
              <div className="mt-2 space-y-2" data-testid="code-panel">
                <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
                  <code data-testid="executed-code">{result.executed_code}</code>
                </pre>
                {result.result_repr && (
                  <pre className="overflow-x-auto rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs leading-relaxed text-gray-700">
                    <code data-testid="result-repr">{result.result_repr}</code>
                  </pre>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
            <TokenBadge {...result.token_usage} />
            <StepStatus inFlight={false} trace={result.step_trace} attempts={result.attempts} />
            <div className="ml-auto">
              <StubButton label="Export dataset" phase="Phase 5" />
            </div>
          </div>
        </div>
      )}
    </article>
  )
}
