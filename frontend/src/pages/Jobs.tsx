import { useNavigate } from 'react-router-dom'
import { ChevronRight, Timer } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useJobs } from '@/api/hooks'
import type { JobStatus } from '@/types/api'

const STATUS_LABELS: Record<JobStatus, string> = {
  active: 'Aktif',
  stale: 'Gecikmiş',
  never_run: 'Hiç Çalışmadı',
}

const STATUS_TONES: Record<JobStatus, 'success' | 'warning' | 'neutral'> = {
  active: 'success',
  stale: 'warning',
  never_run: 'neutral',
}

function formatRelative(timestamp: string | null): string {
  if (!timestamp) return 'Hiç çalışmadı'
  const date = new Date(timestamp)
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 5) return 'az önce'
  if (seconds < 60) return `${seconds} saniye önce`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} dakika önce`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} saat önce`
  return date.toLocaleString('tr-TR', { day: '2-digit', month: 'long', hour: '2-digit', minute: '2-digit' })
}

export function Jobs() {
  const navigate = useNavigate()
  const { data, isLoading } = useJobs({ refetchInterval: 15_000 })
  const jobs = data?.jobs ?? []

  return (
    <div>
      <PageHeader
        title="Job'lar"
        description="Arka planda sürekli/zamanlanmış çalışan işler -- hangi aralıkta çalıştığı ve en son ne zaman çalıştığı"
      />

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.name}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/jobs/${job.name}`)}
              onKeyDown={(e) => e.key === 'Enter' && navigate(`/jobs/${job.name}`)}
              className="cursor-pointer"
            >
              <Card className="transition-colors hover:border-enigma-primary/40">
                <CardBody className="flex items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-enigma-bg">
                      <Timer className="h-5 w-5 text-enigma-text-muted" />
                    </div>
                    <div>
                      <p className="font-medium text-enigma-text">{job.label}</p>
                      <p className="mt-0.5 text-sm text-enigma-text-muted">{job.description}</p>
                      <p className="mt-1.5 text-xs text-enigma-text-muted">
                        <span className="font-medium text-enigma-text">{job.interval_label}</span>
                        {' · '}Son çalışma: {formatRelative(job.last_heartbeat)}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <Badge tone={STATUS_TONES[job.status]}>{STATUS_LABELS[job.status]}</Badge>
                    <ChevronRight className="h-4 w-4 text-enigma-text-muted" />
                  </div>
                </CardBody>
              </Card>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
