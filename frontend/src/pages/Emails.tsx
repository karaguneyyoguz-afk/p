import { useMemo, useState } from 'react'
import { RefreshCw, Search, Mail as MailIcon } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody } from '@/components/ui/Card'
import { useEmails, useProcessEmail } from '@/api/hooks'
import { useToast } from '@/components/ui/Toast'
import { ListSkeleton } from '@/components/ui/Skeleton'

export function Emails() {
  const { data, isLoading, isError, refetch, isFetching } = useEmails()
  const processEmail = useProcessEmail()
  const toast = useToast()
  const [filter, setFilter] = useState('')

  const emails = useMemo(() => {
    const list = data?.emails ?? []
    if (!filter.trim()) return list
    const term = filter.toLowerCase()
    return list.filter((email) =>
      `${email.from} ${email.subject} ${email.preview}`.toLowerCase().includes(term),
    )
  }, [data, filter])

  const handleProcess = (emailId: string) => {
    toast.show('E-posta işleniyor...', 'info')
    processEmail.mutate(emailId, {
      onSuccess: (result) => {
        if (result.success) {
          toast.show(`Ticket başarıyla oluşturuldu! #${result.ticket_id}`, 'success')
        } else {
          toast.show(result.message || 'İşlem başarısız', 'error')
        }
      },
      onError: (error) => {
        toast.show(error instanceof Error ? error.message : 'İşlem başarısız', 'error')
      },
    })
  }

  return (
    <div>
      <PageHeader
        title="E-postalar"
        description="Gelen kutusundaki okunmamış (veya en son) e-postalar"
      />

      <Card>
        <CardBody>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-2 rounded-lg border border-enigma-border px-3 py-2 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-50"
            >
              <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
              Yenile
            </button>
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="E-posta ara..."
                className="w-full rounded-lg border border-enigma-border bg-enigma-bg py-2 pl-9 pr-3 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20"
              />
            </div>
            {data && (
              <span className="text-sm text-enigma-text-muted">
                {emails.length} / {data.count} e-posta
              </span>
            )}
          </div>

          {isLoading ? (
            <ListSkeleton />
          ) : isError ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-danger">
              E-postalar yüklenemedi
            </div>
          ) : emails.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
              E-posta bulunamadı
            </div>
          ) : (
            <ul className="divide-y divide-enigma-border">
              {emails.map((email) => (
                <li key={email.id} className="flex items-start gap-4 py-4">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-enigma-primary-light text-enigma-primary">
                    <MailIcon className="h-4.5 w-4.5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-enigma-text">
                      {email.from}
                    </p>
                    <p className="truncate text-sm text-enigma-text">{email.subject}</p>
                    <p className="truncate text-xs text-enigma-text-muted">
                      {email.preview}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleProcess(email.id)}
                    disabled={processEmail.isPending}
                    className="shrink-0 rounded-lg bg-enigma-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
                  >
                    İşle
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
