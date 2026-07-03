'use client'

import { useEffect, useRef, useState } from 'react'
import {
  askQuestion,
  getSession,
  getSessions,
  ApiCallError,
  type AnswerResult,
  type Profile,
  type SessionSummary,
  type SessionTurn,
  type UploadResult,
} from '@/lib/api'
import UploadZone from '@/components/UploadZone'
import ProfileCard from '@/components/ProfileCard'
import QuestionBox from '@/components/QuestionBox'
import AnswerCard, { type HistoryItem } from '@/components/AnswerCard'
import SessionPicker from '@/components/SessionPicker'
import { SourceStubs } from '@/components/Stubs'

interface Dataset {
  id: string
  fileName: string
  profile: Profile
}

// Turn the answer-card portion of a persisted turn into the AnswerResult the
// AnswerCard renders. Replayed turns carry no step_trace (live-run only).
function turnToResult(turn: SessionTurn, sessionId: string): AnswerResult {
  return {
    run_id: turn.run_id,
    session_id: sessionId,
    answer: turn.answer,
    method_note: turn.method_note,
    executed_code: turn.executed_code,
    result_repr: turn.result_repr,
    assumptions: turn.assumptions,
    chart_spec: turn.chart_spec,
    token_usage: turn.token_usage,
    attempts: turn.attempts,
    used_fallback: turn.used_fallback,
    // step_trace intentionally omitted for replay.
  }
}

function turnToHistoryItem(turn: SessionTurn, sessionId: string): HistoryItem {
  return {
    id: `turn-${turn.run_id}`,
    question: turn.question,
    status: turn.status === 'completed' || turn.status === 'done' ? 'done' : 'failed',
    result: turnToResult(turn, sessionId),
    error: null,
  }
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  // dataframeLoaded is true when the active session's dataframe is resident and
  // asking is allowed; false → history is read-only and we prompt to re-upload.
  const [dataframeLoaded, setDataframeLoaded] = useState(true)
  // History is newest-first for display; new turns are prepended.
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [running, setRunning] = useState(false)

  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Monotonic generation counter. Any explicit user action (a fresh upload or a
  // session-picker selection) bumps this. loadSession captures the generation it
  // started under and, after its await resolves, only applies its setState calls
  // if no newer action has since superseded it. This prevents the in-flight mount
  // restore from clobbering a just-uploaded/just-selected active session.
  const loadGenRef = useRef(0)
  // Set true by any explicit user action (upload or picker selection). The mount
  // restore checks this AFTER its awaited refreshSessions() resolves, so a user
  // action that happened while the initial fetch was in flight cancels the
  // deferred restore before it can grab a fresh generation and clobber state.
  const userActedRef = useRef(false)
  // Live mirrors of dataset + dataframeLoaded so onAsk never early-returns on a
  // stale render closure (a transient async flip must not swallow a question).
  const datasetRef = useRef<Dataset | null>(null)
  const dataframeLoadedRef = useRef(true)

  useEffect(() => {
    datasetRef.current = dataset
    dataframeLoadedRef.current = dataframeLoaded
  }, [dataset, dataframeLoaded])

  async function refreshSessions(): Promise<SessionSummary[]> {
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      const list = await getSessions()
      setSessions(list)
      return list
    } catch (e) {
      const msg = e instanceof ApiCallError ? e.message : 'Could not load past sessions.'
      setSessionsError(msg)
      return []
    } finally {
      setSessionsLoading(false)
    }
  }

  async function loadSession(id: string, selecting = false) {
    // Capture the generation this load started under; a later upload/selection
    // bumps loadGenRef and invalidates our awaited result.
    const gen = ++loadGenRef.current
    setLoadError(null)
    try {
      const detail = await getSession(id)
      // Superseded by a newer user action while the fetch was in flight — drop
      // this result entirely so we never clobber the fresher active state. The
      // userActedRef check also drops a LATE continuation that resolves after an
      // upload/selection, which would otherwise transiently flip dataframeLoaded.
      if (gen !== loadGenRef.current || (userActedRef.current && !selecting)) return
      setSessionId(detail.session_id)
      setDataset({ id: detail.dataset_id, fileName: detail.title, profile: detail.profile })
      setDataframeLoaded(detail.dataframe_loaded)
      // turns arrive chronologically; show newest-first to match live prepend order.
      const items = detail.turns.map(t => turnToHistoryItem(t, detail.session_id)).reverse()
      setHistory(items)
    } catch (e) {
      if (gen !== loadGenRef.current) return
      const msg = e instanceof ApiCallError ? e.message : 'Could not load this session.'
      setLoadError(msg)
    }
  }

  // On first load, fetch sessions and restore the most-recent one so history
  // survives a page reload. Only auto-restore a session whose dataframe is still
  // resident (dataframe_loaded): after a process restart every session is evicted,
  // and auto-loading an evicted (read-only) session would both surprise the user
  // and race a fresh upload. Evicted sessions remain openable via the picker.
  useEffect(() => {
    let cancelled = false
    void (async () => {
      const list = await refreshSessions()
      if (cancelled || userActedRef.current) return
      if (list.length > 0 && list[0].dataframe_loaded) {
        await loadSession(list[0].session_id)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Register upload intent the moment a file is picked (before the POST resolves)
  // so any in-flight mount restore is superseded at the earliest possible point.
  function onUploadStart() {
    userActedRef.current = true
    loadGenRef.current += 1
  }

  async function onUploaded(result: UploadResult, fileName: string) {
    // Supersede any in-flight mount restore so it cannot clobber this upload.
    userActedRef.current = true
    loadGenRef.current += 1
    setSessionId(result.session_id)
    setDataset({ id: result.dataset_id, fileName, profile: result.profile })
    setDataframeLoaded(true)
    setHistory([])
    setLoadError(null)
    await refreshSessions()
  }

  async function onSelectSession(id: string) {
    if (id === sessionId) return
    userActedRef.current = true
    await loadSession(id, true)
  }

  async function onAsk(question: string) {
    const activeDataset = datasetRef.current
    if (!activeDataset || !dataframeLoadedRef.current) return
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    const pending: HistoryItem = { id, question, status: 'running', result: null, error: null }
    setHistory(h => [pending, ...h])
    setRunning(true)
    try {
      const result = await askQuestion(activeDataset.id, question)
      if (result.session_id) setSessionId(result.session_id)
      setHistory(h => h.map(item => (item.id === id ? { ...item, status: 'done', result } : item)))
      await refreshSessions()
    } catch (e) {
      const msg = e instanceof ApiCallError ? e.message : 'The question failed to run.'
      setHistory(h =>
        h.map(item => (item.id === id ? { ...item, status: 'failed', error: msg } : item)),
      )
    } finally {
      setRunning(false)
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">Data Analyst Agent</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload a CSV, ask a question in plain English, and see the real pandas that answers it.
        </p>
      </header>

      <div className="space-y-6">
        <UploadZone onUploaded={onUploaded} onUploadStart={onUploadStart} />

        <SessionPicker
          sessions={sessions}
          activeSessionId={sessionId}
          loading={sessionsLoading}
          error={sessionsError}
          onSelect={onSelectSession}
        />

        {loadError && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            data-testid="load-error"
          >
            {loadError}
          </div>
        )}

        {dataset && <ProfileCard fileName={dataset.fileName} profile={dataset.profile} />}

        {dataset && !dataframeLoaded && (
          <div
            className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
            data-testid="reupload-prompt"
          >
            <p className="font-medium">This dataset is no longer loaded in memory.</p>
            <p className="mt-1 text-amber-800">
              Your past answers below are preserved. Re-upload{' '}
              <span className="font-medium">{dataset.fileName}</span> above to continue asking
              questions in this session.
            </p>
          </div>
        )}

        <SourceStubs />

        <QuestionBox disabled={!dataset || !dataframeLoaded} running={running} onAsk={onAsk} />

        {history.length === 0 ? (
          dataset ? (
            <p className="py-8 text-center text-sm text-gray-400">
              Ask a question above to see the answer, the executed code, and a chart when one fits.
            </p>
          ) : (
            <p className="py-8 text-center text-sm text-gray-400">
              Upload a dataset to get started.
            </p>
          )
        ) : (
          <section aria-label="Conversation history" className="space-y-4" data-testid="history">
            {history.map(item => (
              <AnswerCard key={item.id} item={item} />
            ))}
          </section>
        )}
      </div>
    </main>
  )
}
