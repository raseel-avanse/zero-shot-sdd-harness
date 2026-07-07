'use client'

import { useState } from 'react'
import { ApiError, createEngagement } from '@/lib/api'
import { ErrorBanner, StubBadge } from './ui'

export function ScopeForm({
  onCreated,
  onCancel,
}: {
  onCreated: (id: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const [targetRef, setTargetRef] = useState('')
  const [allowlist, setAllowlist] = useState<string[]>([''])
  const [roe, setRoe] = useState('')
  const [authorizedBy, setAuthorizedBy] = useState('')
  const [nonDestructive, setNonDestructive] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  function setAllow(i: number, v: string) {
    setAllowlist((a) => a.map((x, j) => (j === i ? v : x)))
  }
  function addAllow() {
    setAllowlist((a) => [...a, ''])
  }
  function removeAllow(i: number) {
    setAllowlist((a) => (a.length === 1 ? a : a.filter((_, j) => j !== i)))
  }

  function validate(): boolean {
    const fe: Record<string, string> = {}
    if (!name.trim()) fe.name = 'Name is required.'
    if (!targetRef.trim()) fe.targetRef = 'Target repo path is required.'
    if (!allowlist.some((a) => a.trim())) fe.allowlist = 'At least one authorized target is required.'
    if (!roe.trim()) fe.roe = 'Rules of engagement are required.'
    if (!authorizedBy.trim()) fe.authorizedBy = 'Authorizer is required for an audit trail.'
    setFieldErrors(fe)
    return Object.keys(fe).length === 0
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!validate()) return
    setSubmitting(true)
    try {
      const { engagement_id } = await createEngagement({
        name: name.trim(),
        target_type: 'repo',
        target_ref: targetRef.trim(),
        authorized_targets: allowlist.map((a) => a.trim()).filter(Boolean),
        rules_of_engagement: roe.trim(),
        authorized_by: authorizedBy.trim(),
        non_destructive_only: nonDestructive,
      })
      onCreated(engagement_id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create engagement.')
    } finally {
      setSubmitting(false)
    }
  }

  const labelCls = 'block text-sm font-medium text-slate-300'
  const inputCls =
    'mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500'

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-xs text-emerald-300">
        Safety-critical: Sentinel will only read paths inside the authorized-targets allowlist. Anything
        outside it is refused in code before any assessment runs.
      </div>

      <div>
        <label htmlFor="eng-name" className={labelCls}>
          Engagement name
        </label>
        <input
          id="eng-name"
          className={inputCls}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Q3 payments-service review"
        />
        {fieldErrors.name && <FieldError msg={fieldErrors.name} />}
      </div>

      <fieldset>
        <legend className={labelCls}>Target type</legend>
        <div className="mt-2 flex gap-3">
          <label className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-slate-100">
            <input type="radio" name="target_type" defaultChecked readOnly />
            Local repository
          </label>
          <label className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-slate-800 px-3 py-2 text-sm text-slate-500">
            <input type="radio" name="target_type" disabled />
            Live app
            <StubBadge phase="P2" />
          </label>
        </div>
      </fieldset>

      <div>
        <label htmlFor="target-ref" className={labelCls}>
          Target repository path
        </label>
        <input
          id="target-ref"
          className={`${inputCls} font-mono`}
          value={targetRef}
          onChange={(e) => setTargetRef(e.target.value)}
          placeholder="/abs/path/to/repo"
        />
        {fieldErrors.targetRef && <FieldError msg={fieldErrors.targetRef} />}
      </div>

      <div>
        <span className={labelCls}>Authorized targets (allowlist)</span>
        <p className="mt-0.5 text-xs text-slate-500">
          Only these paths may be read. The target path above must be inside one of them.
        </p>
        <div className="mt-2 space-y-2">
          {allowlist.map((val, i) => (
            <div key={i} className="flex gap-2">
              <input
                aria-label={`Authorized target ${i + 1}`}
                className={`${inputCls} mt-0 font-mono`}
                value={val}
                onChange={(e) => setAllow(i, e.target.value)}
                placeholder="/abs/path/to/repo"
              />
              <button
                type="button"
                onClick={() => removeAllow(i)}
                disabled={allowlist.length === 1}
                className="rounded-lg border border-slate-700 px-3 text-sm text-slate-400 hover:bg-slate-800 disabled:opacity-40"
                aria-label={`Remove path row ${i + 1}`}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addAllow}
          className="mt-2 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
        >
          + Add path
        </button>
        {fieldErrors.allowlist && <FieldError msg={fieldErrors.allowlist} />}
      </div>

      <div>
        <label htmlFor="roe" className={labelCls}>
          Rules of engagement
        </label>
        <textarea
          id="roe"
          rows={3}
          aria-required
          className={inputCls}
          value={roe}
          onChange={(e) => setRoe(e.target.value)}
          placeholder="Scope notes, constraints, contacts…"
        />
        {fieldErrors.roe && <FieldError msg={fieldErrors.roe} />}
      </div>

      <div>
        <label htmlFor="authorized-by" className={labelCls}>
          Authorized by
        </label>
        <input
          id="authorized-by"
          className={inputCls}
          value={authorizedBy}
          onChange={(e) => setAuthorizedBy(e.target.value)}
          placeholder="Name of the person authorizing this assessment"
        />
        {fieldErrors.authorizedBy && <FieldError msg={fieldErrors.authorizedBy} />}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={nonDestructive}
          onChange={(e) => setNonDestructive(e.target.checked)}
        />
        Non-destructive only (read-only assessment)
      </label>

      <label className="flex cursor-not-allowed items-center gap-2 text-sm text-slate-500">
        <input type="checkbox" disabled />
        Enable live-app active probing
        <StubBadge phase="P2" />
      </label>

      {error && <ErrorBanner message={error} />}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {submitting ? 'Creating…' : 'Create engagement'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function FieldError({ msg }: { msg: string }) {
  return (
    <p role="alert" className="mt-1 text-xs text-red-400">
      {msg}
    </p>
  )
}
