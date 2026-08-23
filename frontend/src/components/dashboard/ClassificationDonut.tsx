import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { CategorySlice } from '@/lib/reportUtils'

const COLORS = [
  'var(--color-enigma-primary)',
  'var(--color-enigma-success)',
  'var(--color-enigma-warning)',
  'var(--color-enigma-info)',
  'var(--color-enigma-danger)',
  '#c4c9d8',
]

export function ClassificationDonut({ data }: { data: CategorySlice[] }) {
  const total = data.reduce((sum, d) => sum + d.value, 0)

  if (total === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-enigma-text-muted">
        Henüz ticket verisi yok
      </div>
    )
  }

  return (
    <div className="flex h-64 items-center gap-4">
      <ResponsiveContainer width="55%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={2}
            strokeWidth={0}
          >
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              borderColor: 'var(--color-enigma-border)',
              fontSize: 13,
            }}
            formatter={(value, name) => [
              `${value} (%${Math.round((Number(value) / total) * 100)})`,
              name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>

      <ul className="flex-1 space-y-2 text-sm">
        {data.map((entry, index) => (
          <li key={entry.name} className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className="truncate text-enigma-text">{entry.name}</span>
            </span>
            <span className="shrink-0 font-medium text-enigma-text-muted">
              {entry.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
