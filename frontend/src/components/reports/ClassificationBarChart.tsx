import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from 'recharts'
import { categoryLabel } from '@/lib/reportUtils'
import type { ClassificationCategory } from '@/types/api'

const COLORS = [
  'var(--color-enigma-primary)',
  'var(--color-enigma-success)',
  'var(--color-enigma-warning)',
  'var(--color-enigma-info)',
  'var(--color-enigma-danger)',
  '#c4c9d8',
]

export function ClassificationBarChart({
  categories,
}: {
  categories: ClassificationCategory[]
}) {
  if (categories.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-enigma-text-muted">
        Henüz ticket verisi yok
      </div>
    )
  }

  const data = categories.map((c) => ({
    name: categoryLabel(c.name),
    count: c.count,
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 44)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 24, left: 8, bottom: 0 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--color-enigma-border)"
          horizontal={false}
        />
        <XAxis
          type="number"
          allowDecimals={false}
          tick={{ fontSize: 12, fill: 'var(--color-enigma-text-muted)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fontSize: 12, fill: 'var(--color-enigma-text)' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            borderColor: 'var(--color-enigma-border)',
            fontSize: 13,
          }}
          formatter={(value) => [`${value}`, 'Ticket']}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
          {data.map((entry, index) => (
            <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
