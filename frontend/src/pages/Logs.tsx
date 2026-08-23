import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { RefreshCw, Search, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { ListSkeleton } from '@/components/ui/Skeleton'
import {
  useMailLogs,
  useReportsByClassification,
  useReportsBySender,
  useClearMailLogs,
} from '@/api/hooks'
import { categoryLabel, topLevelCategory, categoryTone, actorLabel, actorTone, eventLabel } from '@/lib/reportUtils'
import { useToast } from '@/components/ui/Toast'

const PAGE_SIZE = 25

const RANGE_OPTIONS = [
  { value: '', label: 'Tüm zamanlar' },
  { value: '7d', label: 'Son 7 gün' },
  { value: '14d', label: 'Son 14 gün' },
  { value: '30d', label: 'Son 30 gün' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'Tüm durumlar' },
  { value: 'success', label: 'Başarılı' },
  { value: 'failed', label: 'Başarısız' },
  { value: 'blocked', label: 'Engellendi' },
  { value: 'rejected', label: 'Reddedildi' },
]

const EVENT_OPTIONS = [
  { value: '', label: 'Tüm olaylar' },
  { value: 'ticket_created', label: 'Ticket Oluşturuldu' },
  { value: 'ticket_not_created', label: 'Ticket Oluşturulamadı' },
  { value: 'email_processed', label: 'E-posta İşlendi' },
  { value: 'email_fetch', label: 'E-posta Alınamadı' },
  { value: 'processor_error', label: 'Sistem Hatası' },
]

const selectClass =
  'rounded-lg border border-enigma-border bg-enigma-surface px-3 py-2 text-sm text-enigma-text focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

function formatDate(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function Logs() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const [page, setPage] = useState(0)
  const [range, setRange] = useState('')
  const [status, setStatus] = useState('')
  const [eventType, setEventType] = useState('')
  const [classification, setClassification] = useState('')
  const [sender, setSender] = useState('')
  const toast = useToast()
  const clearMailLogs = useClearMailLogs()

  useEffect(() => setPage(0), [query, range, status, eventType, classification, sender])

  const { data: allCategories } = useReportsByClassification()
  const { data: allSenders } = useReportsBySender({ limit: 20 })

  const { data, isLoading, isError, refetch, isFetching } = useMailLogs({
    q: query || undefined,
    range: range || undefined,
    status: status || undefined,
    event: eventType || undefined,
    classification: classification || undefined,
    sender: sender || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  })

  const logs = data?.logs ?? []
  const total = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeStart = total === 0 ? 0 : page * PAGE_SIZE + 1
  const rangeEnd = Math.min(total, (page + 1) * PAGE_SIZE)
  const hasActiveFilters =
    range !== '' || status !== '' || eventType !== '' || classification !== '' || sender !== ''

  const handleClear = () => {
    if (!confirm('Tüm işlem loglarını temizlemek istediğinizden emin misiniz?')) return
    clearMailLogs.mutate(undefined, {
      onSuccess: () => toast.show('İşlem logları temizlendi', 'success'),
      onError: () => toast.show('Loglar temizlenemedi', 'error'),
    })
  }

  return (
    <div>
      <PageHeader
        title="Loglar"
        description="E-posta ve ticket işleme kayıtları — detay için bir satıra tıklayın"
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">Tarih Aralığı</label>
            <select className={selectClass} value={range} onChange={(e) => setRange(e.target.value)}>
              {RANGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">Durum</label>
            <select className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">Olay</label>
            <select className={selectClass} value={eventType} onChange={(e) => setEventType(e.target.value)}>
              {EVENT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">Kategori</label>
            <select
              className={selectClass}
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
            >
              <option value="">Tüm kategoriler</option>
              {(allCategories?.categories ?? []).map((c) => (
                <option key={c.name} value={c.name}>{categoryLabel(c.name)}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">Gönderen</label>
            <select className={selectClass} value={sender} onChange={(e) => setSender(e.target.value)}>
              <option value="">Tüm gönderenler</option>
              {(allSenders?.senders ?? []).map((s) => (
                <option key={s.sender_email} value={s.sender_email}>{s.sender_email}</option>
              ))}
            </select>
          </div>

          <div className="relative min-w-[200px] max-w-sm flex-1">
            <label className="text-xs font-medium text-enigma-text-muted">Serbest Arama</label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
              <input
                type="text"
                value={query}
                onChange={(e) => {
                  const value = e.target.value
                  setSearchParams(value ? { q: value } : {}, { replace: true })
                }}
                placeholder="Gönderen, konu, neden ara..."
                className="w-full rounded-lg border border-enigma-border bg-enigma-bg py-2 pl-9 pr-3 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20"
              />
            </div>
          </div>

          {(hasActiveFilters || query) && (
            <button
              type="button"
              onClick={() => {
                setRange('')
                setStatus('')
                setEventType('')
                setClassification('')
                setSender('')
                setSearchParams({}, { replace: true })
              }}
              className="rounded-lg px-3 py-2 text-sm font-medium text-enigma-primary hover:bg-enigma-primary-light"
            >
              Filtreleri Temizle
            </button>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => refetch()}
                disabled={isFetching}
                className="flex items-center gap-2 rounded-lg border border-enigma-border px-3 py-2 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-50"
              >
                <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
                Yenile
              </button>
              <button
                type="button"
                onClick={handleClear}
                disabled={clearMailLogs.isPending}
                className="flex items-center gap-2 rounded-lg border border-enigma-border px-3 py-2 text-sm font-medium text-enigma-danger hover:bg-enigma-danger-light disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                Logları Temizle
              </button>
            </div>
            <span className="text-sm text-enigma-text-muted">
              {total === 0 ? '0 kayıt' : `${rangeStart}–${rangeEnd} / ${total} kayıt`}
            </span>
          </div>

          {isLoading ? (
            <ListSkeleton />
          ) : isError ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-danger">
              Loglar yüklenemedi
            </div>
          ) : logs.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
              {query || hasActiveFilters ? 'Eşleşen kayıt bulunamadı' : 'Henüz işlem logu yok'}
            </div>
          ) : (
            <div className="-mx-5 overflow-x-auto px-5">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-3 pr-4 font-medium">Zaman</th>
                    <th className="pb-3 pr-4 font-medium">Olay</th>
                    <th className="pb-3 pr-4 font-medium">Gönderen</th>
                    <th className="pb-3 pr-4 font-medium">Konu</th>
                    <th className="pb-3 pr-4 font-medium">Kategori</th>
                    <th className="pb-3 pr-4 font-medium">Kaynak</th>
                    <th className="pb-3 pr-4 font-medium">Durum</th>
                    <th className="pb-3 pr-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log, index) => {
                    const topCategory = topLevelCategory(log.classification)
                    return (
                      <tr
                        key={`${log.timestamp}-${index}`}
                        onClick={() => navigate(`/logs/${encodeURIComponent(log.timestamp)}`)}
                        className="cursor-pointer border-b border-enigma-border/60 transition-colors last:border-0 hover:bg-enigma-bg"
                      >
                        <td className="whitespace-nowrap py-3 pr-4 text-enigma-text-muted">
                          {formatDate(log.timestamp)}
                        </td>
                        <td className="whitespace-nowrap py-3 pr-4 text-enigma-text">
                          {eventLabel(log.event)}
                        </td>
                        <td className="max-w-[180px] truncate py-3 pr-4 text-enigma-text">
                          {log.sender_email || '-'}
                        </td>
                        <td className="max-w-[180px] truncate py-3 pr-4 text-enigma-text-muted">
                          {log.subject || '-'}
                        </td>
                        <td className="whitespace-nowrap py-3 pr-4">
                          {log.classification ? (
                            <Badge tone={categoryTone(topCategory)}>{categoryLabel(topCategory)}</Badge>
                          ) : (
                            <span className="text-enigma-text-muted">—</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap py-3 pr-4">
                          <Badge tone={actorTone(log.actor)}>{actorLabel(log.actor)}</Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <StatusBadge status={log.status} />
                        </td>
                        <td className="py-3 pr-2 text-enigma-text-muted">
                          <ChevronRight className="h-4 w-4" />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between border-t border-enigma-border pt-4">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1.5 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Önceki
              </button>
              <span className="text-sm text-enigma-text-muted">
                Sayfa {page + 1} / {pageCount}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={page >= pageCount - 1}
                className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1.5 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-40"
              >
                Sonraki
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
