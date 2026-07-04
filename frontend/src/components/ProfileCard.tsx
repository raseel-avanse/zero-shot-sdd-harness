'use client'

import type { Profile } from '@/lib/api'

interface Props {
  fileName: string
  profile: Profile
}

function formatSample(values: unknown[]): string {
  if (!values || values.length === 0) return '—'
  return values
    .slice(0, 4)
    .map(v => (v === null || v === undefined ? 'null' : String(v)))
    .join(', ')
}

export default function ProfileCard({ fileName, profile }: Props) {
  return (
    <section
      aria-label="Dataset profile"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
      data-testid="profile-card"
    >
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-gray-900">{fileName}</h2>
        <span className="text-sm text-gray-600" data-testid="row-count">
          {profile.row_count.toLocaleString()} rows · {profile.columns.length} columns
        </span>
      </div>

      {profile.dq_flags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2" data-testid="dq-flags">
          {profile.dq_flags.map((flag, i) => (
            <span
              key={i}
              className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800"
            >
              {flag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4">Column</th>
              <th className="py-2 pr-4">Type</th>
              <th className="py-2 pr-4">Non-null</th>
              <th className="py-2 pr-4">Nulls</th>
              <th className="py-2">Sample values</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map(col => (
              <tr key={col.name} className="border-b border-gray-100 last:border-0">
                <td className="py-2 pr-4 font-medium text-gray-800">{col.name}</td>
                <td className="py-2 pr-4">
                  <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                    {col.dtype}
                  </code>
                </td>
                <td className="py-2 pr-4 tabular-nums text-gray-700">{col.non_null.toLocaleString()}</td>
                <td className="py-2 pr-4 tabular-nums">
                  <span className={col.null_count > 0 ? 'text-amber-700' : 'text-gray-400'}>
                    {col.null_count.toLocaleString()}
                  </span>
                </td>
                <td className="py-2 text-gray-500">{formatSample(col.sample_values)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
