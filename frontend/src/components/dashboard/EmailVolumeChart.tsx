import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { DailyVolumePoint } from '@/lib/reportUtils'

function niceYAxisTicks(data: DailyVolumePoint[], tickCount = 5) {
  const max = Math.max(0, ...data.map((d) => d.count))
  const niceMax = max <= tickCount ? tickCount : Math.ceil(max / tickCount) * tickCount
  const step = niceMax / tickCount
  return {
    domain: [0, niceMax] as [number, number],
    ticks: Array.from({ length: tickCount + 1 }, (_, i) => Math.round(i * step)),
  }
}

export function EmailVolumeChart({ data }: { data: DailyVolumePoint[] }) {
  const { domain, ticks } = niceYAxisTicks(data)

  return (
    <ResponsiveContainer width="100%" height={256}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="enigma-volume-fill" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="5%"
              stopColor="var(--color-enigma-primary)"
              stopOpacity={0.35}
            />
            <stop
              offset="95%"
              stopColor="var(--color-enigma-primary)"
              stopOpacity={0}
            />
          </linearGradient>
        </defs>
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
          domain={domain}
          ticks={ticks}
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
          labelFormatter={(label) => `${label}`}
          formatter={(value) => [`${value}`, 'E-posta']}
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke="var(--color-enigma-primary)"
          strokeWidth={2}
          fill="url(#enigma-volume-fill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
