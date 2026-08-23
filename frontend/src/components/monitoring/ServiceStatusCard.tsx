import type { LucideIcon } from 'lucide-react'
import clsx from 'clsx'
import type { ServiceHealthSummary } from '@/types/api'

function formatRelative(timestamp: string | null) {
  if (!timestamp) return 'Hiç'
  const diffMs = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'az önce'
  if (minutes < 60) return `${minutes} dk önce`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} sa önce`
  return new Date(timestamp).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' })
}

interface ServiceStatusCardProps {
  label: string
  icon: LucideIcon
  summary?: ServiceHealthSummary
}

export function ServiceStatusCard({ label, icon: Icon, summary }: ServiceStatusCardProps) {
  const hasActivity = (summary?.total ?? 0) > 0
  // Healthy if there's activity and the most recent call succeeded more
  // recently than the most recent failure (or there's never been a failure).
  const isHealthy =
    hasActivity &&
    (!summary?.last_failure_at ||
      (summary?.last_success_at && summary.last_success_at > summary.last_failure_at))

  return (
    <div className="rounded-xl border border-enigma-border bg-enigma-surface p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-enigma-primary-light text-enigma-primary">
          <Icon className="h-5 w-5" strokeWidth={2} />
        </span>
        <span
          className={clsx(
            'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
            !hasActivity
              ? 'bg-enigma-bg text-enigma-text-muted'
              : isHealthy
                ? 'bg-enigma-success-light text-enigma-success'
                : 'bg-enigma-danger-light text-enigma-danger',
          )}
        >
          <span
            className={clsx(
              'h-1.5 w-1.5 rounded-full',
              !hasActivity ? 'bg-enigma-text-muted' : isHealthy ? 'bg-enigma-success' : 'bg-enigma-danger',
            )}
          />
          {!hasActivity ? 'Veri yok' : isHealthy ? 'Aktif' : 'Sorunlu'}
        </span>
      </div>

      <p className="mt-4 text-sm font-semibold text-enigma-text">{label}</p>

      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-enigma-text-muted">Son başarılı</p>
          <p className="mt-0.5 font-medium text-enigma-text">
            {formatRelative(summary?.last_success_at ?? null)}
          </p>
        </div>
        <div>
          <p className="text-enigma-text-muted">Son hata</p>
          <p className="mt-0.5 font-medium text-enigma-text">
            {formatRelative(summary?.last_failure_at ?? null)}
          </p>
        </div>
        <div>
          <p className="text-enigma-text-muted">Başarılı</p>
          <p className="mt-0.5 font-medium text-enigma-success">{summary?.success_count ?? 0}</p>
        </div>
        <div>
          <p className="text-enigma-text-muted">Başarısız</p>
          <p className="mt-0.5 font-medium text-enigma-danger">{summary?.failed_count ?? 0}</p>
        </div>
      </div>
    </div>
  )
}
