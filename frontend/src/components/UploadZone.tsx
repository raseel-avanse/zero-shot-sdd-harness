'use client'

import { useRef, useState } from 'react'
import { uploadDataset, ApiCallError, type UploadResult } from '@/lib/api'

interface Props {
  onUploaded: (result: UploadResult, fileName: string) => void
  // Fired synchronously the instant a file is chosen, before the async upload —
  // lets the page register user intent so an in-flight session restore cannot
  // land on top of the upload.
  onUploadStart?: () => void
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export default function UploadZone({ onUploaded, onUploadStart }: Props) {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<{ name: string; size: number } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    onUploadStart?.()
    setError(null)
    setLoading(true)
    setCurrent({ name: file.name, size: file.size })
    try {
      const result = await uploadDataset(file)
      onUploaded(result, file.name)
    } catch (e) {
      const msg = e instanceof ApiCallError ? e.message : 'Upload failed.'
      setError(msg)
      setCurrent(null)
    } finally {
      setLoading(false)
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  return (
    <section aria-label="Upload dataset">
      <div
        role="button"
        tabIndex={0}
        aria-disabled={loading}
        onClick={() => !loading && inputRef.current?.click()}
        onKeyDown={e => {
          if ((e.key === 'Enter' || e.key === ' ') && !loading) inputRef.current?.click()
        }}
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'
        } ${loading ? 'cursor-wait opacity-70' : ''}`}
        data-testid="upload-zone"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          data-testid="file-input"
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
            e.target.value = ''
          }}
        />
        {loading ? (
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
            Profiling {current?.name}…
          </div>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-800">Drop a CSV here, or click to choose</p>
            <p className="mt-1 text-xs text-gray-500">CSV files, a few MB max</p>
            {current && (
              <p className="mt-3 text-xs text-gray-600" data-testid="current-file">
                {current.name} · {humanSize(current.size)}
              </p>
            )}
          </>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          data-testid="upload-error"
        >
          {error}
        </div>
      )}
    </section>
  )
}
