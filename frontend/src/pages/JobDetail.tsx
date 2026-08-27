import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useJobDetail } from '@/api/hooks'
import { eventLabel } from '@/lib/reportUtils'
import { ApiError } from '@/api/client'
import type { JobStatus } from '@/types/api'
import type { ReactNode } from 'react'

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

function formatDate(timestamp: string | null) {
  if (!timestamp) return 'Hiç çalışmadı'
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-enigma-text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-enigma-text">{value}</p>
    </div>
  )
}

export function JobDetail() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useJobDetail(name, { refetchInterval: 15_000 })

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate('/jobs')}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-enigma-text-muted hover:text-enigma-text"
      >
        <ArrowLeft className="h-4 w-4" />
        Job'lar'a dön
      </button>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : error ? (
        <Card>
          <CardBody>
            <p className="text-sm text-enigma-danger">
              {error instanceof ApiError ? error.message : 'Job yüklenemedi'}
            </p>
          </CardBody>
        </Card>
      ) : data ? (
        <>
          <PageHeader
            title={data.job.label}
            description={data.job.description}
            action={<Badge tone={STATUS_TONES[data.job.status]}>{STATUS_LABELS[data.job.status]}</Badge>}
          />

          <Card className="mb-4">
            <CardHeader title="Genel Bilgiler" />
            <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Field label="Çalışma Aralığı" value={data.job.interval_label} />
              <Field label="Son Çalışma" value={formatDate(data.job.last_heartbeat)} />
              <Field label="Betik" value={<code className="text-xs">{data.job.entrypoint}</code>} />
              <Field label="Durum" value={<Badge tone={STATUS_TONES[data.job.status]}>{STATUS_LABELS[data.job.status]}</Badge>} />
            </CardBody>
          </Card>

          <Card className="mb-4">
            <CardHeader title="Servis Çağrıları" subtitle="Bu job'un IMAP/CSM gibi dış servislere yaptığı son çağrılar" />
            <CardBody>
              {data.service_logs.length === 0 ? (
                <p className="py-6 text-center text-sm text-enigma-text-muted">Henüz kayıt yok</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                        <th className="pb-2 pr-4 font-medium">Zaman</th>
                        <th className="pb-2 pr-4 font-medium">Servis</th>
                        <th className="pb-2 pr-4 font-medium">Aksiyon</th>
                        <th className="pb-2 pr-4 font-medium">Durum</th>
                        <th className="pb-2 pr-4 font-medium">Detay</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.service_logs.map((log, i) => (
                        <tr key={i} className="border-b border-enigma-border/60 last:border-0">
                          <td className="whitespace-nowrap py-2.5 pr-4 text-enigma-text-muted">{formatDate(log.timestamp)}</td>
                          <td className="py-2.5 pr-4 text-enigma-text">{log.service}</td>
                          <td className="py-2.5 pr-4 text-enigma-text-muted">{log.action}</td>
                          <td className="py-2.5 pr-4">
                            <StatusBadge status={log.status} />
                          </td>
                          <td className="max-w-xs truncate py-2.5 pr-4 text-enigma-text-muted">{log.detail || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Mail İşleme Kayıtları" subtitle="Bu job üzerinden işlenen son mailler" />
            <CardBody>
              {data.mail_logs.length === 0 ? (
                <p className="py-6 text-center text-sm text-enigma-text-muted">Henüz kayıt yok</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                        <th className="pb-2 pr-4 font-medium">Zaman</th>
                        <th className="pb-2 pr-4 font-medium">Olay</th>
                        <th className="pb-2 pr-4 font-medium">Gönderen</th>
                        <th className="pb-2 pr-4 font-medium">Konu</th>
                        <th className="pb-2 pr-4 font-medium">Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.mail_logs.map((log, i) => (
                        <tr
                          key={i}
                          className="cursor-pointer border-b border-enigma-border/60 last:border-0 hover:bg-enigma-bg"
                          onClick={() => navigate(`/logs/${encodeURIComponent(log.timestamp)}`)}
                        >
                          <td className="whitespace-nowrap py-2.5 pr-4 text-enigma-text-muted">{formatDate(log.timestamp)}</td>
                          <td className="py-2.5 pr-4 text-enigma-text">{eventLabel(log.event)}</td>
                          <td className="max-w-[160px] truncate py-2.5 pr-4 text-enigma-text-muted">{log.sender_email || '—'}</td>
                          <td className="max-w-xs truncate py-2.5 pr-4 text-enigma-text-muted">{log.subject || '—'}</td>
                          <td className="py-2.5 pr-4">
                            <StatusBadge status={log.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  )
}
