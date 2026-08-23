import type { ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Info } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTicket } from '@/api/hooks'
import { categoryLabel } from '@/lib/reportUtils'
import { ApiError } from '@/api/client'

function formatDate(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function classificationBreadcrumb(classification?: string) {
  if (!classification) return '—'
  return classification
    .split('>')
    .map((part) => categoryLabel(part.trim()))
    .join('  ›  ')
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-enigma-text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-enigma-text">{value}</p>
    </div>
  )
}

export function TicketDetail() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useTicket(ticketId)
  const ticket = data?.ticket

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate('/tickets')}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-enigma-text-muted hover:text-enigma-text"
      >
        <ArrowLeft className="h-4 w-4" />
        Talepler'e dön
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
              {error instanceof ApiError
                ? error.message
                : `#${ticketId} numaralı ticket yüklenemedi`}
            </p>
          </CardBody>
        </Card>
      ) : ticket ? (
        <>
          <PageHeader
            title={`Ticket #${ticket.ticket_id}`}
            description={ticket.subject || undefined}
            action={<StatusBadge status={ticket.status} />}
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Genel Bilgiler" />
              <CardBody className="grid grid-cols-2 gap-4">
                <Field label="Ticket No" value={`#${ticket.ticket_id}`} />
                <Field label="Oluşturulma Tarihi" value={formatDate(ticket.timestamp)} />
                <Field label="Gönderen" value={ticket.sender_email || '—'} />
                <Field label="Konu" value={ticket.subject || '—'} />
                <Field label="Durum" value={<StatusBadge status={ticket.status} />} />
                <Field label="Neden" value={ticket.reason || '—'} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Sınıflandırma" />
              <CardBody className="space-y-4">
                <Field
                  label="Kategori"
                  value={classificationBreadcrumb(ticket.classification)}
                />
                <div className="grid grid-cols-3 gap-4">
                  <Field
                    label="Ticket Tipi (CSM)"
                    value={ticket.ticket_details?.ticket_type ?? '—'}
                  />
                  <Field
                    label="Kategori ID (CSM)"
                    value={ticket.ticket_details?.category ?? '—'}
                  />
                  <Field
                    label="Alt Kategori ID (CSM)"
                    value={ticket.ticket_details?.sub_category ?? '—'}
                  />
                </div>
                <Field
                  label="Alt Kategori Kodu"
                  value={ticket.ticket_details?.sub_category_code || '—'}
                />
              </CardBody>
            </Card>

            <Card className="lg:col-span-2">
              <CardBody className="flex items-start gap-3">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-enigma-info" />
                <p className="text-sm text-enigma-text-muted">
                  <span className="font-medium text-enigma-text">Atanan kişi ve CSM'deki canlı durum</span> bu
                  panelde gösterilmiyor. Mevcut entegrasyon CSM'ye yalnızca ticket{' '}
                  <em>oluşturuyor</em> — CSM'den atama/durum bilgisini geri okuyan bir uç
                  nokta yok. Yukarıdaki "Durum" alanı, bu panelin kendi e-posta→ticket
                  işleme adımının sonucudur (başarılı/başarısız/engellendi), CSM'nin
                  ticket'ı ne aşamada tuttuğunu yansıtmaz.
                </p>
              </CardBody>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader title="E-posta İçeriği" />
              <CardBody>
                <pre className="whitespace-pre-wrap font-sans text-sm text-enigma-text">
                  {ticket.mail_body || ticket.ticket_details?.body_preview || 'İçerik yok'}
                </pre>
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  )
}
