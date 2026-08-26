import { useState, type FormEvent } from 'react'
import { Plus, Trash2, FlaskConical, Eye, Check, X as XIcon } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import {
  useContentRules,
  useCreateContentRule,
  useUpdateContentRule,
  useDeleteContentRule,
  useTestContentRule,
  useFlaggedMails,
  useFlaggedMail,
  useApproveFlaggedMail,
  useRejectFlaggedMail,
} from '@/api/hooks'
import type { ContentRule, ContentRuleCategory, ContentRuleType, FlaggedMail, FlaggedMailStatus } from '@/types/api'

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

export function ContentRules() {
  const [flaggedId, setFlaggedId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState<FlaggedMailStatus | ''>('pending')

  const { data: rulesData, isLoading: rulesLoading } = useContentRules()
  const { data: flaggedData, isLoading: flaggedLoading } = useFlaggedMails({
    status: statusFilter || undefined,
    refetchInterval: 30_000,
  })

  const rules = rulesData?.rules ?? []
  const flaggedMails = flaggedData?.flagged_mails ?? []

  return (
    <div>
      <PageHeader
        title="İçerik Kuralları"
        description="Uygunsuz içerik kuralları (kelime/regex) ve incelemeyi bekleyen mailler"
      />

      <Card className="mb-4">
        <CardHeader title="Kurallar" subtitle="Kodda sabit bir liste de ayrıca çalışmaya devam ediyor -- buradakiler ona ek" />
        <CardBody className="space-y-4">
          <NewRuleForm />
          {rulesLoading ? (
            <div className="h-24 animate-pulse rounded-lg bg-enigma-bg" />
          ) : rules.length === 0 ? (
            <p className="py-4 text-center text-sm text-enigma-text-muted">Henüz panelden eklenmiş kural yok</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-2 pr-4 font-medium">Kalıp</th>
                    <th className="pb-2 pr-4 font-medium">Tip</th>
                    <th className="pb-2 pr-4 font-medium">Kategori</th>
                    <th className="pb-2 pr-4 font-medium">Durum</th>
                    <th className="pb-2 pr-4 font-medium">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <RuleRow key={rule.id} rule={rule} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

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

function NewRuleForm() {
  const createRule = useCreateContentRule()
  const testRule = useTestContentRule()
  const toast = useToast()

  const [pattern, setPattern] = useState('')
  const [ruleType, setRuleType] = useState<ContentRuleType>('keyword')
  const [category, setCategory] = useState<ContentRuleCategory>('kufur')
  const [error, setError] = useState<string | null>(null)
  const [testText, setTestText] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    createRule.mutate(
      { pattern: pattern.trim(), rule_type: ruleType, category },
      {
        onSuccess: () => {
          toast.show('Kural eklendi', 'success')
          setPattern('')
        },
        onError: (err) => setError(err instanceof Error ? err.message : 'Eklenemedi'),
      },
    )
  }

  const handleTest = () => {
    testRule.mutate(testText, {
      onSuccess: (data) => {
        setTestResult(
          data.matched
            ? `Eşleşti — kategori: ${CATEGORY_LABELS[data.category!]} (kaynak: ${data.rule_source === 'db' ? 'panel kuralı' : 'kod listesi'})`
            : 'Eşleşme yok — bu metin temiz sayılır.',
        )
      },
    })
  }

  return (
    <div className="space-y-4 rounded-lg border border-enigma-border p-4">
      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
        <input
          className={inputClass}
          placeholder={ruleType === 'regex' ? 'ör. kazandiniz.*tikla' : 'ör. dolandirici'}
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          required
        />
        <select value={ruleType} onChange={(e) => setRuleType(e.target.value as ContentRuleType)} className={`${inputClass} sm:w-32`}>
          <option value="keyword">Kelime</option>
          <option value="regex">Regex</option>
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value as ContentRuleCategory)} className={`${inputClass} sm:w-40`}>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={createRule.isPending}
          className="flex items-center justify-center gap-1.5 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Ekle
        </button>
      </form>
      {error && <p className="rounded-lg bg-enigma-danger-light px-3 py-2 text-sm text-enigma-danger">{error}</p>}

      <div className="flex flex-col gap-2 border-t border-enigma-border pt-3 sm:flex-row sm:items-center">
        <input
          className={inputClass}
          placeholder="Kaydetmeden bir metni dene..."
          value={testText}
          onChange={(e) => setTestText(e.target.value)}
        />
        <button
          type="button"
          onClick={handleTest}
          disabled={!testText || testRule.isPending}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-enigma-border px-4 py-2 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-50"
        >
          <FlaskConical className="h-4 w-4" />
          Test Et
        </button>
      </div>
      {testResult && <p className="text-xs text-enigma-text-muted">{testResult}</p>}
    </div>
  )
}

function RuleRow({ rule }: { rule: ContentRule }) {
  const updateRule = useUpdateContentRule()
  const deleteRule = useDeleteContentRule()
  const toast = useToast()

  const handleDelete = () => {
    if (!window.confirm(`"${rule.pattern}" kuralı silinsin mi?`)) return
    deleteRule.mutate(rule.id, {
      onError: (e) => toast.show(e instanceof Error ? e.message : 'Silinemedi', 'error'),
    })
  }

  const handleToggleActive = () => {
    updateRule.mutate(
      { id: rule.id, is_active: !rule.is_active },
      { onError: (e) => toast.show(e instanceof Error ? e.message : 'Güncellenemedi', 'error') },
    )
  }

  return (
    <tr className="border-b border-enigma-border/60 last:border-0">
      <td className="max-w-xs truncate py-2.5 pr-4 font-mono text-xs text-enigma-text">{rule.pattern}</td>
      <td className="py-2.5 pr-4 text-enigma-text-muted">{rule.rule_type === 'regex' ? 'Regex' : 'Kelime'}</td>
      <td className="py-2.5 pr-4">
        <Badge tone="neutral">{CATEGORY_LABELS[rule.category]}</Badge>
      </td>
      <td className="py-2.5 pr-4">
        <button type="button" onClick={handleToggleActive} disabled={updateRule.isPending}>
          <Badge tone={rule.is_active ? 'success' : 'neutral'}>{rule.is_active ? 'Aktif' : 'Pasif'}</Badge>
        </button>
      </td>
      <td className="py-2.5 pr-4">
        <button
          type="button"
          onClick={handleDelete}
          className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1 text-xs font-medium text-enigma-danger hover:bg-enigma-danger-light"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Sil
        </button>
      </td>
    </tr>
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
