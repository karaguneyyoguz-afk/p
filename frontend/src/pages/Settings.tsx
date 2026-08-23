import { useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import {
  useTokenInfo,
  useRefreshToken,
  useErrors,
  useClearErrors,
  useClearMailLogs,
  useValidateTurkishId,
  useValidateTaxId,
  useCheckProfanity,
} from '@/api/hooks'
import { useToast } from '@/components/ui/Toast'
import { Skeleton } from '@/components/ui/Skeleton'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

const buttonClass =
  'rounded-lg border border-enigma-border px-3 py-2 text-sm font-medium text-enigma-text hover:bg-enigma-bg disabled:opacity-50'

function TokenCard() {
  const { data, isLoading } = useTokenInfo()
  const refreshToken = useRefreshToken()
  const toast = useToast()
  const info = data?.token_info

  const handleRefresh = () => {
    refreshToken.mutate(undefined, {
      onSuccess: () => toast.show('Token başarıyla yenilendi', 'success'),
      onError: (error) =>
        toast.show(error instanceof Error ? error.message : 'Token yenilenemedi', 'error'),
    })
  }

  return (
    <Card>
      <CardHeader title="CSM Token Durumu" subtitle="Kimlik doğrulama token bilgisi" />
      <CardBody className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-9 w-full" />
            <div className="flex gap-6">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-8 w-20" />
            </div>
          </div>
        ) : info?.error ? (
          <p className="text-sm text-enigma-danger">{info.error}</p>
        ) : (
          <>
            <div>
              <p className="text-xs font-medium text-enigma-text-muted">Token</p>
              <code className="mt-1 block truncate rounded-lg bg-enigma-bg px-3 py-2 text-sm text-enigma-text">
                {info?.token || 'Token bulunamadı'}
              </code>
            </div>
            <div className="flex gap-6 text-sm">
              <div>
                <p className="text-xs font-medium text-enigma-text-muted">Son Güncelleme</p>
                <p className="text-enigma-text">
                  {info?.acquired_at
                    ? new Date(info.acquired_at).toLocaleString('tr-TR')
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-enigma-text-muted">Geçerlilik</p>
                <p className="text-enigma-text">{info?.expires_in || '—'}</p>
              </div>
            </div>
          </>
        )}
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshToken.isPending}
          className="rounded-lg bg-enigma-primary px-3 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
        >
          Token Yenile
        </button>
      </CardBody>
    </Card>
  )
}

function LogManagementCard() {
  const { data: errorsData } = useErrors()
  const clearErrors = useClearErrors()
  const clearMailLogs = useClearMailLogs()
  const toast = useToast()
  const errors = (errorsData?.errors ?? []).slice(0, 5)

  const handleClearErrors = () => {
    if (!confirm('Tüm hataları temizlemek istediğinizden emin misiniz?')) return
    clearErrors.mutate(undefined, {
      onSuccess: () => toast.show('Hatalar temizlendi', 'success'),
      onError: () => toast.show('Hatalar temizlenemedi', 'error'),
    })
  }

  const handleClearLogs = () => {
    if (!confirm('Tüm işlem loglarını temizlemek istediğinizden emin misiniz?')) return
    clearMailLogs.mutate(undefined, {
      onSuccess: () => toast.show('İşlem logları temizlendi', 'success'),
      onError: () => toast.show('Loglar temizlenemedi', 'error'),
    })
  }

  return (
    <Card>
      <CardHeader
        title="Log Yönetimi"
        subtitle={`${errorsData?.errors.length ?? 0} hata kaydı`}
      />
      <CardBody className="space-y-4">
        {errors.length === 0 ? (
          <p className="text-sm text-enigma-text-muted">Hata yok</p>
        ) : (
          <ul className="space-y-2">
            {errors.map((error, index) => (
              <li
                key={`${error.timestamp}-${index}`}
                className="rounded-lg border border-enigma-border p-3 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-enigma-text">{error.error}</span>
                  {error.status && <StatusBadge status={error.status} />}
                </div>
                <p className="mt-1 text-enigma-text-muted">
                  {new Date(error.timestamp).toLocaleString('tr-TR')}
                  {error.sender_email ? ` · ${error.sender_email}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleClearErrors}
            disabled={clearErrors.isPending}
            className="rounded-lg bg-enigma-danger px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            Hataları Temizle
          </button>
          <button
            type="button"
            onClick={handleClearLogs}
            disabled={clearMailLogs.isPending}
            className={buttonClass}
          >
            Tüm Logları Temizle
          </button>
        </div>
      </CardBody>
    </Card>
  )
}

function ValidationToolsCard() {
  const [turkishId, setTurkishId] = useState('')
  const [taxId, setTaxId] = useState('')
  const [text, setText] = useState('')

  const validateTurkishId = useValidateTurkishId()
  const validateTaxId = useValidateTaxId()
  const checkProfanity = useCheckProfanity()

  return (
    <Card className="lg:col-span-2">
      <CardHeader title="Doğrulama Araçları" subtitle="Hızlı veri doğrulama testleri" />
      <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="space-y-2">
          <label className="text-xs font-medium text-enigma-text-muted">
            TC Kimlik Numarası
          </label>
          <input
            className={inputClass}
            maxLength={11}
            value={turkishId}
            onChange={(e) => setTurkishId(e.target.value)}
            placeholder="11 haneli TC kimlik no"
          />
          <button
            type="button"
            className={buttonClass}
            onClick={() => validateTurkishId.mutate(turkishId)}
            disabled={!turkishId || validateTurkishId.isPending}
          >
            Doğrula
          </button>
          {validateTurkishId.data && (
            <p
              className={
                validateTurkishId.data.is_valid
                  ? 'text-sm text-enigma-success'
                  : 'text-sm text-enigma-danger'
              }
            >
              {validateTurkishId.data.is_valid ? 'Geçerli' : 'Geçersiz'}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-enigma-text-muted">
            Vergi Kimlik Numarası
          </label>
          <input
            className={inputClass}
            maxLength={10}
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
            placeholder="10 haneli VKN"
          />
          <button
            type="button"
            className={buttonClass}
            onClick={() => validateTaxId.mutate(taxId)}
            disabled={!taxId || validateTaxId.isPending}
          >
            Doğrula
          </button>
          {validateTaxId.data && (
            <p
              className={
                validateTaxId.data.is_valid
                  ? 'text-sm text-enigma-success'
                  : 'text-sm text-enigma-danger'
              }
            >
              {validateTaxId.data.is_valid ? 'Geçerli' : 'Geçersiz'}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-enigma-text-muted">
            Uygunsuz İçerik Kontrolü
          </label>
          <textarea
            className={inputClass}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Kontrol edilecek metin"
          />
          <button
            type="button"
            className={buttonClass}
            onClick={() => checkProfanity.mutate(text)}
            disabled={!text || checkProfanity.isPending}
          >
            Kontrol Et
          </button>
          {checkProfanity.data && (
            <p
              className={
                checkProfanity.data.has_profanity
                  ? 'text-sm text-enigma-danger'
                  : 'text-sm text-enigma-success'
              }
            >
              {checkProfanity.data.has_profanity ? 'Uygunsuz içerik' : 'İçerik temiz'}
            </p>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

export function Settings() {
  return (
    <div>
      <PageHeader
        title="Ayarlar"
        description="Token durumu, log yönetimi ve doğrulama araçları"
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TokenCard />
        <LogManagementCard />
        <ValidationToolsCard />
      </div>
    </div>
  )
}
