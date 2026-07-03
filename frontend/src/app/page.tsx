'use client'

import { useState } from 'react'
import { askQuestion, ApiCallError, type Profile, type UploadResult } from '@/lib/api'
import UploadZone from '@/components/UploadZone'
import ProfileCard from '@/components/ProfileCard'
import QuestionBox from '@/components/QuestionBox'
import AnswerCard, { type HistoryItem } from '@/components/AnswerCard'
import { SourceStubs } from '@/components/Stubs'

interface Dataset {
  id: string
  fileName: string
  profile: Profile
}

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [running, setRunning] = useState(false)

  function onUploaded(result: UploadResult, fileName: string) {
    setDataset({ id: result.dataset_id, fileName, profile: result.profile })
    setHistory([])
  }

  async function onAsk(question: string) {
    if (!dataset) return
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    const pending: HistoryItem = { id, question, status: 'running', result: null, error: null }
    // Newest at top.
    setHistory(h => [pending, ...h])
    setRunning(true)
    try {
      const result = await askQuestion(dataset.id, question)
      setHistory(h =>
        h.map(item => (item.id === id ? { ...item, status: 'done', result } : item)),
      )
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
        <UploadZone onUploaded={onUploaded} />

        {dataset && <ProfileCard fileName={dataset.fileName} profile={dataset.profile} />}

        <SourceStubs />

        <QuestionBox disabled={!dataset} running={running} onAsk={onAsk} />

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
