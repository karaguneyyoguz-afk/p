import type { LucideIcon } from 'lucide-react'
import clsx from 'clsx'

interface StatCardProps {
  label: string
  value: string
  icon: LucideIcon
  tone?: 'primary' | 'success' | 'warning' | 'danger'
}

const toneClasses: Record<NonNullable<StatCardProps['tone']>, string> = {
  primary: 'bg-enigma-primary-light text-enigma-primary',
  success: 'bg-enigma-success-light text-enigma-success',
  warning: 'bg-enigma-warning-light text-enigma-warning',
  danger: 'bg-enigma-danger-light text-enigma-danger',
}

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'primary',
}: StatCardProps) {
  return (
    <div className="rounded-xl border border-enigma-border bg-enigma-surface p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span
          className={clsx(
            'flex h-10 w-10 items-center justify-center rounded-lg',
            toneClasses[tone],
          )}
        >
          <Icon className="h-5 w-5" strokeWidth={2} />
        </span>
      </div>
      <p className="mt-4 text-2xl font-semibold text-enigma-text">{value}</p>
      <p className="mt-1 text-sm text-enigma-text-muted">{label}</p>
    </div>
  )
}
