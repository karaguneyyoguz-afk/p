import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { RefreshCw, Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { useTickets, useReportsByClassification, useReportsBySender } from '@/api/hooks'
import { categoryLabel, topLevelCategory, categoryTone } from '@/lib/reportUtils'

const PAGE_SIZE = 25

const RANGE_OPTIONS = [
  { value: '', label: 'Tüm zamanlar' },
  { value: '7d', label: 'Son 7 gün' },
  { value: '14d', label: 'Son 14 gün' },
  { value: '30d', label: 'Son 30 gün' },
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
  })
}

function initialOf(email: string) {
  return (email.trim()[0] || '?').toUpperCase()
}

export function Tickets() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const [page, setPage] = useState(0)
  const [range, setRange] = useState('')
  const [classification, setClassification] = useState('')
  const [sender, setSender] = useState('')

  // Any filter change (including a Topbar search) always restarts at page 1.
  useEffect(() => setPage(0), [query, range, classification, sender])

  // Unfiltered lookups populate the filter dropdown option lists (same source Reports uses).
  const { data: allCategories } = useReportsByClassification()
  const { data: allSenders } = useReportsBySender({ limit: 20 })

  const { data, isLoading, isError, refetch, isFetching } = useTickets({
    q: query || undefined,
    range: range || undefined,
    classification: classification || undefined,
    sender: sender || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  })

  const tickets = data?.tickets ?? []
  const total = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeStart = total === 0 ? 0 : page * PAGE_SIZE + 1
  const rangeEnd = Math.min(total, (page + 1) * PAGE_SIZE)
  const hasActiveFilters = range !== '' || classification !== '' || sender !== ''

  return (
    <div>
      <PageHeader
        title="Talepler"
        description="Oluşturulan CSM ticket'ları — detay için bir satıra tıklayın"
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">
              Tarih Aralığı
            </label>
            <select
              className={selectClass}
              value={range}
              onChange={(e) => setRange(e.target.value)}
            >
              {RANGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">
              Kategori
            </label>
            <select
              className={selectClass}
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
            >
              <option value="">Tüm kategoriler</option>
              {(allCategories?.categories ?? []).map((c) => (
                <option key={c.name} value={c.name}>
                  {categoryLabel(c.name)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-enigma-text-muted">
              Gönderen
            </label>
            <select
              className={selectClass}
              value={sender}
              onChange={(e) => setSender(e.target.value)}
            >
              <option value="">Tüm gönderenler</option>
              {(allSenders?.senders ?? []).map((s) => (
                <option key={s.sender_email} value={s.sender_email}>
                  {s.sender_email}
                </option>
              ))}
            </select>
          </div>

          <div className="relative min-w-[200px] max-w-sm flex-1">
            <label className="text-xs font-medium text-enigma-text-muted">
              Serbest Arama
            </label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
              <input
                type="text"
                value={query}
                onChange={(e) => {
                  const value = e.target.value
                  setSearchParams(value ? { q: value } : {}, { replace: true })
                }}
                placeholder="Ticket no, gönderen veya konu ara..."
                className="w-full rounded-lg border border-enigma-border bg-enigma-bg py-2 pl-9 pr-3 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20"
              />
            </div>
          </div>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={() => {
                setRange('')
                setClassification('')
                setSender('')
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
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-2 rounded-lg border border-enigma-border px-3 py-2 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-50"
            >
              <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
              Yenile
            </button>
            <span className="text-sm text-enigma-text-muted">
              {total === 0 ? '0 ticket' : `${rangeStart}–${rangeEnd} / ${total} ticket`}
            </span>
          </div>

          {isLoading ? (
            <ListSkeleton />
          ) : isError ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-danger">
              Ticket'lar yüklenemedi
            </div>
          ) : tickets.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
              {query || hasActiveFilters
                ? 'Eşleşen ticket bulunamadı'
                : 'Oluşturulmuş ticket bulunamadı'}
            </div>
          ) : (
            <div className="-mx-5 overflow-x-auto px-5">
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-3 pr-4 font-medium">Ticket No</th>
                    <th className="pb-3 pr-4 font-medium">Tarih</th>
                    <th className="pb-3 pr-4 font-medium">Gönderen</th>
                    <th className="pb-3 pr-4 font-medium">Konu</th>
                    <th className="pb-3 pr-4 font-medium">Kategori</th>
                    <th className="pb-3 pr-4 font-medium">Durum</th>
                    <th className="pb-3 pr-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((ticket, index) => {
                    const topCategory = topLevelCategory(ticket.classification)
                    return (
                      <tr
                        key={`${ticket.ticket_id}-${index}`}
                        onClick={() => navigate(`/tickets/${ticket.ticket_id}`)}
                        className="cursor-pointer border-b border-enigma-border/60 transition-colors last:border-0 hover:bg-enigma-bg"
                      >
                        <td className="whitespace-nowrap py-3.5 pr-4 font-medium text-enigma-primary">
                          #{ticket.ticket_id ?? '-'}
                        </td>
                        <td className="whitespace-nowrap py-3.5 pr-4 text-enigma-text-muted">
                          {formatDate(ticket.timestamp)}
                        </td>
                        <td className="py-3.5 pr-4">
                          <div className="flex items-center gap-2">
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-enigma-primary-light text-xs font-semibold text-enigma-primary">
                              {initialOf(ticket.sender_email || '?')}
                            </span>
                            <span className="max-w-[180px] truncate text-enigma-text">
                              {ticket.sender_email || '-'}
                            </span>
                          </div>
                        </td>
                        <td className="max-w-[200px] truncate py-3.5 pr-4 text-enigma-text-muted">
                          {ticket.subject || '-'}
                        </td>
                        <td className="whitespace-nowrap py-3.5 pr-4">
                          <Badge tone={categoryTone(topCategory)}>
                            {categoryLabel(topCategory)}
                          </Badge>
                        </td>
                        <td className="py-3.5 pr-4">
                          <StatusBadge status={ticket.status} />
                        </td>
                        <td className="py-3.5 pr-2 text-enigma-text-muted">
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
