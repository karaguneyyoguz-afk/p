import { useState, type FormEvent } from 'react'
import { Plus, Trash2, FlaskConical } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/components/ui/Toast'
import {
  useContentRules,
  useCreateContentRule,
  useUpdateContentRule,
  useDeleteContentRule,
  useTestContentRule,
} from '@/api/hooks'
import type { ContentRule, ContentRuleCategory, ContentRuleType } from '@/types/api'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

const CATEGORY_LABELS: Record<ContentRuleCategory, string> = {
  kufur: 'Küfür/Hakaret',
  spam: 'Spam',
  tehdit: 'Tehdit',
  yetiskin: 'Yetişkin İçerik',
  diger: 'Diğer',
}

export function FraudRules() {
  const { data: rulesData, isLoading: rulesLoading } = useContentRules()
  const rules = rulesData?.rules ?? []

  return (
    <div>
      <PageHeader
        title="Uygunsuz İçerik Kelime Tanımı"
        description="Küfür/hakaret/tehdit/spam olarak sayılacak kelime ve kalıpların (regex) tanımlandığı ekran"
      />

      <Card>
        <CardHeader title="Kurallar" subtitle="Koddaki sabit liste ('Kod' etiketli) ve panelden eklenenler ('Panel' etiketli) birlikte gösteriliyor" />
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
                    <th className="pb-2 pr-4 font-medium">Kaynak</th>
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
  const isConfigRule = rule.source === 'config'

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
        <Badge tone={isConfigRule ? 'info' : 'primary'}>{isConfigRule ? 'Kod' : 'Panel'}</Badge>
      </td>
      <td className="py-2.5 pr-4">
        {isConfigRule ? (
          <Badge tone="success">Aktif</Badge>
        ) : (
          <button type="button" onClick={handleToggleActive} disabled={updateRule.isPending}>
            <Badge tone={rule.is_active ? 'success' : 'neutral'}>{rule.is_active ? 'Aktif' : 'Pasif'}</Badge>
          </button>
        )}
      </td>
      <td className="py-2.5 pr-4">
        {isConfigRule ? (
          <span className="text-xs text-enigma-text-muted" title="Bu kural koddaki config.PROFANITY_WORDS listesinden geliyor, panelden düzenlenemez/silinemez.">
            Koddan düzenlenir
          </span>
        ) : (
          <button
            type="button"
            onClick={handleDelete}
            className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1 text-xs font-medium text-enigma-danger hover:bg-enigma-danger-light"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Sil
          </button>
        )}
      </td>
    </tr>
  )
}
