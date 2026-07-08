'use client'

import { useState } from 'react'
import { ApiError, createEngagement, type TargetType } from '@/lib/api'
import { ErrorBanner } from './ui'

export function ScopeForm({
  onCreated,
  onCancel,
}: {
  onCreated: (id: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState('')
  const [targetType, setTargetType] = useState<TargetType>('repo')
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

  const isLive = targetType === 'live_app'

  function validate(): boolean {
    const fe: Record<string, string> = {}
    if (!name.trim()) fe.name = 'Name is required.'
    if (!targetRef.trim())
      fe.targetRef = isLive ? 'Target base URL is required.' : 'Target repo path is required.'
    else if (isLive && !/^https?:\/\//i.test(targetRef.trim()))
      fe.targetRef = 'Target base URL must start with http:// or https://'
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
        target_type: targetType,
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

  const labelCls = 'block text-sm font-medium text-ink'
  const inputCls =
    'mt-1.5 w-full rounded-lg border border-strong bg-surface px-3 py-2 text-sm text-ink-strong placeholder:text-ink-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary'

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <div className="rounded-lg border border-primary/25 bg-primary-tint px-4 py-3 text-xs text-primary">
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
          <label
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
              !isLive
                ? 'border-primary/40 bg-primary-tint text-ink-strong'
                : 'border-strong text-ink-muted'
            }`}
          >
            <input
              type="radio"
              name="target_type"
              checked={!isLive}
              onChange={() => setTargetType('repo')}
            />
            Local repository
          </label>
          <label
            data-testid="target-type-live"
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
              isLive
                ? 'border-primary/40 bg-primary-tint text-ink-strong'
                : 'border-strong text-ink-muted'
            }`}
          >
            <input
              type="radio"
              name="target_type"
              checked={isLive}
              onChange={() => setTargetType('live_app')}
            />
            Live app
          </label>
        </div>
      </fieldset>

      {isLive && (
        <div
          data-testid="live-nondestructive-notice"
          className="rounded-lg border border-primary/25 bg-primary-tint px-4 py-3 text-xs text-primary"
        >
          Live-app probing is <strong>non-destructive only</strong>: Sentinel issues read-only verbs
          (GET / HEAD / OPTIONS) against allowlisted hosts. State-changing requests and out-of-scope
          hosts are refused in code, independent of the model.
        </div>
      )}

      <div>
        <label htmlFor="target-ref" className={labelCls}>
          {isLive ? 'Target base URL' : 'Target repository path'}
        </label>
        <input
          id="target-ref"
          className={`${inputCls} font-mono`}
          value={targetRef}
          onChange={(e) => setTargetRef(e.target.value)}
          placeholder={isLive ? 'https://app.example.com' : '/abs/path/to/repo'}
        />
        {fieldErrors.targetRef && <FieldError msg={fieldErrors.targetRef} />}
      </div>

      <div>
        <span className={labelCls}>Authorized targets (allowlist)</span>
        <p className="mt-0.5 text-xs text-ink-muted">
          {isLive
            ? 'Only these hosts may be probed. The base URL above must be an allowlisted host.'
            : 'Only these paths may be read. The target path above must be inside one of them.'}
        </p>
        <div className="mt-2 space-y-2">
          {allowlist.map((val, i) => (
            <div key={i} className="flex gap-2">
              <input
                aria-label={`Authorized target ${i + 1}`}
                className={`${inputCls} mt-0 font-mono`}
                value={val}
                onChange={(e) => setAllow(i, e.target.value)}
                placeholder={isLive ? 'https://app.example.com' : '/abs/path/to/repo'}
              />
              <button
                type="button"
                onClick={() => removeAllow(i)}
                disabled={allowlist.length === 1}
                className="rounded-lg border border-strong px-3 text-sm text-ink-muted hover:bg-canvas disabled:opacity-40"
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
          className="mt-2 rounded-lg border border-strong px-3 py-1.5 text-xs text-ink hover:bg-canvas"
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

      <label className="flex items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          checked={nonDestructive}
          onChange={(e) => setNonDestructive(e.target.checked)}
        />
        Non-destructive only (read-only assessment)
      </label>

      {error && <ErrorBanner message={error} />}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-primary-hover disabled:opacity-50"
        >
          {submitting ? 'Creating…' : 'Create engagement'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-strong px-5 py-2.5 text-sm text-ink hover:bg-canvas"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function FieldError({ msg }: { msg: string }) {
  return (
    <p role="alert" className="mt-1 text-xs text-[#912018]">
      {msg}
    </p>
  )
}
