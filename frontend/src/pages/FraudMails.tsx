import { useState, type FormEvent } from 'react'
import { Plus, Eye, Check, X as XIcon, Link2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import {
  useFlaggedMails,
  useFlaggedMail,
  useApproveFlaggedMail,
  useRejectFlaggedMail,
  useTrustedDomains,
  useCreateTrustedDomain,
  useDeleteTrustedDomain,
} from '@/api/hooks'
import type { ContentRuleCategory, FlaggedMail, FlaggedMailStatus, TrustedDomain } from '@/types/api'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

const CATEGORY_LABELS: Record<ContentRuleCategory, string> = {
  kufur: 'Küfür/Hakaret',
  spam: 'Spam',
  tehdit: 'Tehdit',
  yetiskin: 'Yetişkin İçerik',
  diger: 'Diğer',
}

const STATUS_LABELS: Record<FlaggedMailStatus, string> = {
  pending: 'İnceleme Bekliyor',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
}

const STATUS_TONES: Record<FlaggedMailStatus, 'warning' | 'success' | 'danger'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}

export function FraudMails() {
  const [flaggedId, setFlaggedId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState<FlaggedMailStatus | ''>('pending')

  const { data: flaggedData, isLoading: flaggedLoading } = useFlaggedMails({
    status: statusFilter || undefined,
    refetchInterval: 30_000,
  })

  const flaggedMails = flaggedData?.flagged_mails ?? []

  return (
    <div>
      <PageHeader
        title="Şüpheli Mailler"
        description="Uygunsuz içerik kuralına takılan mailler ve mail linkleri için güvenilir kabul edilen alan adları"
      />

      <TrustedDomainsSection />

      <Card>
        <CardHeader
          title="İncelemeyi Bekleyen Mailler"
          subtitle="Uygunsuz içerik kuralına takılan mailler -- otomatik ticket açılmaz, buradan onaylanır/reddedilir"
          action={
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as FlaggedMailStatus | '')}
              className={`${inputClass} w-auto py-1.5 text-xs`}
            >
              <option value="pending">İnceleme Bekleyenler</option>
              <option value="approved">Onaylananlar</option>
              <option value="rejected">Reddedilenler</option>
              <option value="">Hepsi</option>
            </select>
          }
        />
        <CardBody>
          {flaggedLoading ? (
            <div className="h-24 animate-pulse rounded-lg bg-enigma-bg" />
          ) : flaggedMails.length === 0 ? (
            <p className="py-8 text-center text-sm text-enigma-text-muted">Bu filtrede kayıt yok</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-2 pr-4 font-medium">Gönderen</th>
                    <th className="pb-2 pr-4 font-medium">Konu</th>
                    <th className="pb-2 pr-4 font-medium">Önizleme (maskeli)</th>
                    <th className="pb-2 pr-4 font-medium">Kategori</th>
                    <th className="pb-2 pr-4 font-medium">Durum</th>
                    <th className="pb-2 pr-4 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {flaggedMails.map((mail) => (
                    <tr key={mail.id} className="border-b border-enigma-border/60 last:border-0">
                      <td className="py-2.5 pr-4 text-enigma-text">{mail.sender_email}</td>
                      <td className="py-2.5 pr-4 text-enigma-text-muted">{mail.subject || '—'}</td>
                      <td className="max-w-xs truncate py-2.5 pr-4 font-mono text-xs text-enigma-text-muted">
                        {mail.matched_snippet || mail.mail_body}
                      </td>
                      <td className="py-2.5 pr-4">
                        <Badge tone="neutral">{CATEGORY_LABELS[mail.matched_category]}</Badge>
                      </td>
                      <td className="py-2.5 pr-4">
                        <Badge tone={STATUS_TONES[mail.status]}>{STATUS_LABELS[mail.status]}</Badge>
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        <button
                          type="button"
                          onClick={() => setFlaggedId(mail.id)}
                          className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1 text-xs font-medium text-enigma-text hover:bg-enigma-bg"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          İncele
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {flaggedId !== null && <FlaggedMailModal id={flaggedId} onClose={() => setFlaggedId(null)} />}
    </div>
  )
}

function TrustedDomainsSection() {
  const { data, isLoading } = useTrustedDomains()
  const createDomain = useCreateTrustedDomain()
  const deleteDomain = useDeleteTrustedDomain()
  const toast = useToast()

  const [domainInput, setDomainInput] = useState('')
  const [error, setError] = useState<string | null>(null)

  const baseDomains = data?.base_domains ?? []
  const domains = data?.domains ?? []

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    createDomain.mutate(domainInput.trim(), {
      onSuccess: () => {
        toast.show('Alan adı eklendi', 'success')
        setDomainInput('')
      },
      onError: (err) => setError(err instanceof Error ? err.message : 'Eklenemedi'),
    })
  }

  const handleDelete = (domain: TrustedDomain) => {
    if (!window.confirm(`"${domain.domain}" güvenilir listeden çıkarılsın mı?`)) return
    deleteDomain.mutate(domain.id, {
      onError: (e) => toast.show(e instanceof Error ? e.message : 'Silinemedi', 'error'),
    })
  }

  return (
    <Card className="mb-4">
      <CardHeader
        title="Kabul Edilen Linkler"
        subtitle="Mail içeriğinde geçtiğinde şüpheli/harici link olarak işaretlenmeyecek, güvenilir kabul edilen alan adları"
      />
      <CardBody className="space-y-4">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            className={inputClass}
            placeholder="ör. ornek-tedarikci.com (tam link de yapıştırabilirsin)"
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            required
          />
          <button
            type="submit"
            disabled={createDomain.isPending}
            className="flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Ekle
          </button>
        </form>
        {error && <p className="rounded-lg bg-enigma-danger-light px-3 py-2 text-sm text-enigma-danger">{error}</p>}

        {isLoading ? (
          <div className="h-16 animate-pulse rounded-lg bg-enigma-bg" />
        ) : (
          <div className="flex flex-wrap gap-2">
            {baseDomains.map((domain) => (
              <span
                key={domain}
                title="Kod tabanlı temel liste, kaldırılamaz"
                className="flex items-center gap-1.5 rounded-full border border-enigma-border bg-enigma-bg px-3 py-1 text-xs text-enigma-text-muted"
              >
                <Link2 className="h-3 w-3" />
                {domain}
                <Badge tone="info">Kod</Badge>
              </span>
            ))}
            {domains.map((domain) => (
              <span
                key={domain.id}
                className="flex items-center gap-1.5 rounded-full border border-enigma-border bg-enigma-bg px-3 py-1 text-xs text-enigma-text"
              >
                <Link2 className="h-3 w-3" />
                {domain.domain}
                <Badge tone="primary">Panel</Badge>
                <button
                  type="button"
                  onClick={() => handleDelete(domain)}
                  className="ml-1 text-enigma-text-muted hover:text-enigma-danger"
                  aria-label={`${domain.domain} sil`}
                >
                  <XIcon className="h-3 w-3" />
                </button>
              </span>
            ))}
            {baseDomains.length === 0 && domains.length === 0 && (
              <p className="text-sm text-enigma-text-muted">Henüz eklenmiş bir alan adı yok</p>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function FlaggedMailModal({ id, onClose }: { id: number; onClose: () => void }) {
  const [reveal, setReveal] = useState(false)
  const { data, isLoading } = useFlaggedMail(id, reveal)
  const approve = useApproveFlaggedMail()
  const reject = useRejectFlaggedMail()
  const toast = useToast()

  const mail: FlaggedMail | undefined = data?.flagged_mail

  const handleApprove = () => {
    if (!window.confirm('Bu mail onaylanıp normal talep akışına (kategorize/ticket) devam edilsin mi?')) return
    approve.mutate(id, {
      onSuccess: () => {
        toast.show('Onaylandı, ticket akışına gönderildi', 'success')
        onClose()
      },
      onError: (e) => toast.show(e instanceof Error ? e.message : 'İşlem başarısız', 'error'),
    })
  }

  const handleReject = () => {
    if (!window.confirm('Bu mail reddedilsin mi? Gönderene ret maili gidecek.')) return
    reject.mutate(id, {
      onSuccess: () => {
        toast.show('Reddedildi', 'info')
        onClose()
      },
      onError: (e) => toast.show(e instanceof Error ? e.message : 'İşlem başarısız', 'error'),
    })
  }

  return (
    <Modal title="İşaretlenen Mail" subtitle={mail?.subject || undefined} onClose={onClose}>
      {isLoading || !mail ? (
        <div className="h-40 animate-pulse rounded-lg bg-enigma-bg" />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs font-medium text-enigma-text-muted">Gönderen</p>
              <p className="text-enigma-text">{mail.sender_email}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-enigma-text-muted">Kategori</p>
              <p className="text-enigma-text">{CATEGORY_LABELS[mail.matched_category]}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-enigma-text-muted">Tetikleyen kural</p>
              <p className="font-mono text-xs text-enigma-text">
                {reveal ? mail.matched_pattern : '••••••'} ({mail.matched_rule_source === 'db' ? 'panel kuralı' : 'kod listesi'})
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-enigma-text-muted">Durum</p>
              <Badge tone={STATUS_TONES[mail.status]}>{STATUS_LABELS[mail.status]}</Badge>
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <p className="text-xs font-medium text-enigma-text-muted">Mail İçeriği</p>
              <button
                type="button"
                onClick={() => setReveal((v) => !v)}
                className="flex items-center gap-1 text-xs font-medium text-enigma-primary hover:underline"
              >
                <Eye className="h-3.5 w-3.5" />
                {reveal ? 'Maskeyi geri getir' : 'Tam metni göster'}
              </button>
            </div>
            <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-lg bg-enigma-bg p-3 font-sans text-sm text-enigma-text">
              {mail.mail_body}
            </pre>
          </div>

          {mail.status === 'pending' && (
            <div className="flex gap-2 border-t border-enigma-border pt-4">
              <button
                type="button"
                onClick={handleApprove}
                disabled={approve.isPending || reject.isPending}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-enigma-success px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                Onayla
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={approve.isPending || reject.isPending}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-enigma-danger px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <XIcon className="h-4 w-4" />
                Reddet
              </button>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
