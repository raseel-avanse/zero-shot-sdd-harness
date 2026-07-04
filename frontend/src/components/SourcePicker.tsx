'use client'

import { useState } from 'react'
import { loadGoogleSheet, loadJsonApi, ApiCallError, type UploadResult } from '@/lib/api'
import { StubButton } from '@/components/Stubs'

interface Props {
  // Same handler CSV upload uses — so a Sheet/JSON load flows through the exact
  // same downstream (profile → question → answer → session) with zero new code.
  onUploaded: (result: UploadResult, fileName: string) => void
  // Fired synchronously at submit, before the async POST, so an in-flight mount
  // restore is superseded at the earliest point (identical to CSV upload intent).
  onUploadStart?: () => void
}

// Map a server error code to friendly, actionable inline copy. Falls back to the
// server-provided detail when we have no tailored message for the code.
function friendlySheetError(err: ApiCallError): string {
  switch (err.code) {
    case 'INVALID_SHEET_URL':
      return "That doesn't look like a Google Sheets link — paste the full share URL."
    case 'SHEET_NOT_ACCESSIBLE':
      return "This sheet isn't public — share it as 'anyone with the link' and try again."
    case 'PARSE_FAILED':
      return "We couldn't read a table from that sheet. Check the first tab has a header row."
    case 'FETCH_FAILED':
      return "We couldn't reach Google Sheets right now. Try again in a moment."
    case 'FILE_TOO_LARGE':
      return 'That sheet is too large to load. Try a smaller range or export a subset.'
    default:
      return err.message
  }
}

function friendlyJsonError(err: ApiCallError): string {
  switch (err.code) {
    case 'INVALID_URL':
      return "That doesn't look like a valid URL — include the full http(s) address."
    case 'JSON_PARSE_FAILED':
      return "That endpoint didn't return valid JSON. Check the URL and try again."
    case 'NO_TABULAR_DATA':
      return "We couldn't find a list of records. Set the records path (e.g. data.items) to the array."
    case 'FETCH_FAILED':
      return "We couldn't reach that API right now. Try again in a moment."
    case 'FILE_TOO_LARGE':
      return 'That response is too large to load. Try a narrower query or a records path.'
    default:
      return err.message
  }
}

function Spinner() {
  return (
    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
  )
}

export default function SourcePicker({ onUploaded, onUploadStart }: Props) {
  const [sheetUrl, setSheetUrl] = useState('')
  const [sheetLoading, setSheetLoading] = useState(false)
  const [sheetError, setSheetError] = useState<string | null>(null)

  const [jsonUrl, setJsonUrl] = useState('')
  const [recordsPath, setRecordsPath] = useState('')
  const [jsonLoading, setJsonLoading] = useState(false)
  const [jsonError, setJsonError] = useState<string | null>(null)

  async function submitSheet(e: React.FormEvent) {
    e.preventDefault()
    const url = sheetUrl.trim()
    if (!url || sheetLoading) return
    // Register user intent synchronously, before the async POST (mirrors CSV).
    onUploadStart?.()
    setSheetError(null)
    setSheetLoading(true)
    try {
      const result = await loadGoogleSheet(url)
      onUploaded(result, 'Google Sheet')
    } catch (err) {
      setSheetError(err instanceof ApiCallError ? friendlySheetError(err) : 'Could not load the sheet.')
    } finally {
      setSheetLoading(false)
    }
  }

  async function submitJson(e: React.FormEvent) {
    e.preventDefault()
    const url = jsonUrl.trim()
    if (!url || jsonLoading) return
    onUploadStart?.()
    setJsonError(null)
    setJsonLoading(true)
    try {
      const result = await loadJsonApi(url, recordsPath)
      onUploaded(result, 'JSON API')
    } catch (err) {
      setJsonError(err instanceof ApiCallError ? friendlyJsonError(err) : 'Could not load the data.')
    } finally {
      setJsonLoading(false)
    }
  }

  return (
    <section
      aria-label="More data sources"
      className="rounded-xl border border-gray-200 bg-white p-4"
      data-testid="source-picker"
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-400">
        More data sources
      </p>

      <div className="space-y-4">
        {/* Google Sheets */}
        <form onSubmit={submitSheet} className="space-y-2" data-testid="google-sheet-form">
          <label htmlFor="sheet-url" className="block text-sm font-medium text-gray-800">
            Connect Google Sheets
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="sheet-url"
              type="url"
              inputMode="url"
              placeholder="Paste a public Google Sheets share link"
              value={sheetUrl}
              disabled={sheetLoading}
              onChange={e => setSheetUrl(e.target.value)}
              data-testid="sheet-url-input"
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
            />
            <button
              type="submit"
              disabled={sheetLoading || sheetUrl.trim() === ''}
              data-testid="sheet-load-button"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {sheetLoading && <Spinner />}
              {sheetLoading ? 'Loading…' : 'Load'}
            </button>
          </div>
          <p className="text-xs text-gray-500">
            Share the sheet as &ldquo;anyone with the link&rdquo; so we can read it.
          </p>
          {sheetError && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
              data-testid="sheet-error"
            >
              {sheetError}
            </div>
          )}
        </form>

        {/* JSON API */}
        <form onSubmit={submitJson} className="space-y-2" data-testid="json-api-form">
          <label htmlFor="json-url" className="block text-sm font-medium text-gray-800">
            Connect JSON API
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="json-url"
              type="url"
              inputMode="url"
              placeholder="https://api.example.com/data"
              value={jsonUrl}
              disabled={jsonLoading}
              onChange={e => setJsonUrl(e.target.value)}
              data-testid="json-url-input"
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
            />
            <input
              id="records-path"
              type="text"
              placeholder="records path (optional, e.g. data.items)"
              value={recordsPath}
              disabled={jsonLoading}
              onChange={e => setRecordsPath(e.target.value)}
              data-testid="records-path-input"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 sm:w-56"
            />
            <button
              type="submit"
              disabled={jsonLoading || jsonUrl.trim() === ''}
              data-testid="json-load-button"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {jsonLoading && <Spinner />}
              {jsonLoading ? 'Loading…' : 'Load'}
            </button>
          </div>
          <p className="text-xs text-gray-500">
            Point at an endpoint returning a list of records. Use the records path if the array is
            nested.
          </p>
          {jsonError && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
              data-testid="json-error"
            >
              {jsonError}
            </div>
          )}
        </form>

        {/* Live database stays a labelled Phase-4 stub. */}
        <div className="border-t border-gray-100 pt-3">
          <StubButton label="Live database" phase="Phase 4" />
        </div>
      </div>
    </section>
  )
}
