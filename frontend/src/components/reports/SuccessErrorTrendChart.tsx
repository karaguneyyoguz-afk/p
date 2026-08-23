import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { formatDayLabel } from '@/lib/reportUtils'
import type { TimeseriesPoint } from '@/types/api'

export function SuccessErrorTrendChart({ points }: { points: TimeseriesPoint[] }) {
  const data = points.map((p) => ({
    label: formatDayLabel(p.date),
    Başarılı: p.success_count,
    Hatalı: p.error_count,
  }))

  return (
    <ResponsiveContainer width="100%" height={256}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--color-enigma-border)"
          vertical={false}
        />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: 'var(--color-enigma-text-muted)' }}
          axisLine={{ stroke: 'var(--color-enigma-border)' }}
          tickLine={false}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fontSize: 12, fill: 'var(--color-enigma-text-muted)' }}
          axisLine={false}
          tickLine={false}
          width={36}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            borderColor: 'var(--color-enigma-border)',
            fontSize: 13,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar
          dataKey="Başarılı"
          stackId="status"
          fill="var(--color-enigma-success)"
          radius={[0, 0, 0, 0]}
        />
        <Bar
          dataKey="Hatalı"
          stackId="status"
          fill="var(--color-enigma-danger)"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}
