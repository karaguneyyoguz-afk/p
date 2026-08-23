import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useMailLogDetail } from '@/api/hooks'
import { categoryLabel, actorLabel, actorTone, eventLabel } from '@/lib/reportUtils'
import { ApiError } from '@/api/client'
import type { ReactNode } from 'react'

function formatDate(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function classificationBreadcrumb(classification?: string) {
  if (!classification) return '—'
  return classification.split('>').map((part) => categoryLabel(part.trim())).join('  ›  ')
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-enigma-text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-enigma-text">{value}</p>
    </div>
  )
}

export function LogDetail() {
  const { timestamp } = useParams<{ timestamp: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useMailLogDetail(timestamp)
  const log = data?.log

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate('/logs')}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-enigma-text-muted hover:text-enigma-text"
      >
        <ArrowLeft className="h-4 w-4" />
        Loglar'a dön
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
              {error instanceof ApiError ? error.message : 'Log kaydı yüklenemedi'}
            </p>
          </CardBody>
        </Card>
      ) : log ? (
        <>
          <PageHeader
            title={eventLabel(log.event)}
            description={formatDate(log.timestamp)}
            action={<StatusBadge status={log.status} />}
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Genel Bilgiler" />
              <CardBody className="grid grid-cols-2 gap-4">
                <Field label="Olay" value={eventLabel(log.event)} />
                <Field label="Zaman" value={formatDate(log.timestamp)} />
                <Field label="Gönderen" value={log.sender_email || '—'} />
                <Field label="Konu" value={log.subject || '—'} />
                <Field label="Durum" value={<StatusBadge status={log.status} />} />
                <Field
                  label="Kaynak"
                  value={<Badge tone={actorTone(log.actor)}>{actorLabel(log.actor)}</Badge>}
                />
                <Field label="Neden" value={log.reason || '—'} />
                {log.details && <Field label="Ayrıntı" value={log.details} />}
                {log.ticket_id && (
                  <Field
                    label="Ticket"
                    value={
                      <a
                        href={`/tickets/${log.ticket_id}`}
                        className="text-enigma-primary hover:underline"
                      >
                        #{log.ticket_id}
                      </a>
                    }
                  />
                )}
              </CardBody>
            </Card>

            {log.classification && (
              <Card>
                <CardHeader title="Sınıflandırma" />
                <CardBody className="space-y-4">
                  <Field label="Kategori" value={classificationBreadcrumb(log.classification)} />
                  {log.ticket_details?.sub_category_code && (
                    <Field label="Alt Kategori Kodu" value={log.ticket_details.sub_category_code} />
                  )}
                </CardBody>
              </Card>
            )}

            {(log.mail_body || log.ticket_details?.body_preview) && (
              <Card className="lg:col-span-2">
                <CardHeader title="E-posta İçeriği" />
                <CardBody>
                  <pre className="whitespace-pre-wrap font-sans text-sm text-enigma-text">
                    {log.mail_body || log.ticket_details?.body_preview}
                  </pre>
                </CardBody>
              </Card>
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
