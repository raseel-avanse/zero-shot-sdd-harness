'use client'

import { useEffect, useRef, useState } from 'react'
import { ApiError, listChatTurns, sendChatMessage, type ChatTurn } from '@/lib/api'
import { ErrorBanner, Markdown } from './ui'

/**
 * Interactive chat bound to one engagement. Conversation memory lives on the
 * backend (each turn = a user message + the assistant reply); we load prior
 * turns on mount (tolerating a missing GET endpoint) and append new ones.
 */
export function ChatPanel({ engagementId }: { engagementId: string }) {
  const [turns, setTurns] = useState<ChatTurn[] | null>(null)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let alive = true
    listChatTurns(engagementId)
      .then((t) => alive && setTurns(t))
      // GET history is optional — start empty if it isn't implemented / fails.
      .catch(() => alive && setTurns([]))
    return () => {
      alive = false
    }
  }, [engagementId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [turns, sending])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const text = message.trim()
    if (!text || sending) return
    setError(null)
    setSending(true)
    try {
      const turn = await sendChatMessage(engagementId, text)
      setTurns((prev) => [...(prev ?? []), turn])
      setMessage('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not send message.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div
      data-testid="chat-panel"
      className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
    >
      <h4 className="mb-3 text-sm font-semibold text-slate-300">Interactive chat</h4>

      <div
        ref={listRef}
        className="mb-3 max-h-72 space-y-3 overflow-y-auto"
        data-testid="chat-history"
      >
        {turns === null && (
          <div className="space-y-2">
            {[0, 1].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded-lg bg-slate-800/60" />
            ))}
          </div>
        )}

        {turns?.length === 0 && !sending && (
          <p className="py-6 text-center text-sm text-slate-500">
            No messages yet — ask a follow-up to direct the assessment. Each reply remembers the
            prior turns of this engagement.
          </p>
        )}

        {turns?.map((t) => (
          <div key={t.turn_id} className="space-y-2">
            <div className="flex justify-end">
              <div
                data-testid="chat-user"
                className="max-w-[85%] rounded-lg rounded-br-sm bg-emerald-600/20 px-3 py-2 text-sm text-emerald-100 ring-1 ring-emerald-500/30"
              >
                {t.message}
              </div>
            </div>
            <div className="flex justify-start">
              <div
                data-testid="chat-assistant"
                className="max-w-[85%] rounded-lg rounded-bl-sm bg-slate-800/70 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700"
              >
                <Markdown>{t.reply}</Markdown>
              </div>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-slate-800/70 px-3 py-2 text-sm text-slate-400 ring-1 ring-slate-700">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <form onSubmit={submit} className="flex gap-2">
        <input
          data-testid="chat-input"
          aria-label="Chat message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={sending}
          placeholder="Ask a follow-up about this engagement…"
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
        />
        <button
          type="submit"
          data-testid="chat-send"
          disabled={sending || !message.trim()}
          className="rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
