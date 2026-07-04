'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartSpec } from '@/lib/api'

const COLORS = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2']

interface Props {
  spec: ChartSpec
}

// Merge every series into row objects keyed by x so multi-series charts share an axis.
function buildData(spec: ChartSpec): Record<string, unknown>[] {
  const byX = new Map<string, Record<string, unknown>>()
  const order: string[] = []
  for (const series of spec.series) {
    for (const p of series.points) {
      const key = String(p.x)
      if (!byX.has(key)) {
        byX.set(key, { __x: key })
        order.push(key)
      }
      byX.get(key)![series.label] = p.y
    }
  }
  return order.map(k => byX.get(k)!)
}

export default function Chart({ spec }: Props) {
  const data = buildData(spec)
  const isLine = spec.type === 'line'

  return (
    <div className="mt-4" data-testid="chart">
      {spec.title && <p className="mb-2 text-sm font-medium text-gray-700">{spec.title}</p>}
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          {isLine ? (
            <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="__x" tick={{ fontSize: 12 }} label={{ value: spec.x, position: 'insideBottom', offset: -4, fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} label={{ value: spec.y, angle: -90, position: 'insideLeft', fontSize: 11 }} />
              <Tooltip />
              <Legend />
              {spec.series.map((s, i) => (
                <Line key={s.label} type="monotone" dataKey={s.label} stroke={COLORS[i % COLORS.length]} dot={false} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="__x" tick={{ fontSize: 12 }} label={{ value: spec.x, position: 'insideBottom', offset: -4, fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} label={{ value: spec.y, angle: -90, position: 'insideLeft', fontSize: 11 }} />
              <Tooltip />
              <Legend />
              {spec.series.map((s, i) => (
                <Bar key={s.label} dataKey={s.label} fill={COLORS[i % COLORS.length]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
