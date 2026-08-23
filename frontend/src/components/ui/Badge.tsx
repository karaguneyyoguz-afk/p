import clsx from 'clsx'
import type { ReactNode } from 'react'

type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const toneClasses: Record<Tone, string> = {
  primary: 'bg-enigma-primary-light text-enigma-primary',
  success: 'bg-enigma-success-light text-enigma-success',
  warning: 'bg-enigma-warning-light text-enigma-warning',
  danger: 'bg-enigma-danger-light text-enigma-danger',
  info: 'bg-enigma-info-light text-enigma-info',
  neutral: 'bg-enigma-bg text-enigma-text-muted',
}

const STATUS_TONE: Record<string, Tone> = {
  success: 'success',
  failed: 'danger',
  blocked: 'warning',
  rejected: 'danger',
}

const STATUS_LABEL: Record<string, string> = {
  success: 'Başarılı',
  failed: 'Başarısız',
  blocked: 'Engellendi',
  rejected: 'Reddedildi',
}

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        toneClasses[tone],
      )}
    >
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? 'neutral'
  const label = STATUS_LABEL[status] ?? status
  return <Badge tone={tone}>{label}</Badge>
}
