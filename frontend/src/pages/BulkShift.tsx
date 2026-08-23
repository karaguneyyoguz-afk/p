import { useRef, useState, type FormEvent } from 'react'
import { Upload, AlertTriangle, FileSpreadsheet } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { ExportCsvButton } from '@/components/ui/ExportCsvButton'
import { useBulkShiftEnv, useUploadBulkShift } from '@/api/hooks'
import { useToast } from '@/components/ui/Toast'
import type { BulkShiftUploadResponse } from '@/types/api'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

const labelClass = 'text-xs font-medium text-enigma-text-muted'

export function BulkShift() {
  const { data: envInfo } = useBulkShiftEnv()
  const upload = useUploadBulkShift()
  const toast = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [parentTicketUuid, setParentTicketUuid] = useState('')
  const [reporterFirstName, setReporterFirstName] = useState('')
  const [reporterLastName, setReporterLastName] = useState('')
  const [reporterPhone, setReporterPhone] = useState('')
  const [reporterEmail, setReporterEmail] = useState('')
  const [result, setResult] = useState<BulkShiftUploadResponse | null>(null)

  const isPreprod = (envInfo?.environment ?? 'preprod') === 'preprod'

  const canSubmit =
    file &&
    parentTicketUuid.trim() &&
    reporterFirstName.trim() &&
    reporterLastName.trim() &&
    reporterPhone.trim() &&
    reporterEmail.trim()

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!file) return
    setResult(null)
    upload.mutate(
      {
        file,
        parentTicketUuid: parentTicketUuid.trim(),
        reporterFirstName: reporterFirstName.trim(),
        reporterLastName: reporterLastName.trim(),
        reporterPhone: reporterPhone.trim(),
        reporterEmail: reporterEmail.trim(),
      },
      {
        onSuccess: (data) => {
          setResult(data)
          toast.show(
            `${data.success_count} başarılı, ${data.failed_count} hatalı`,
            data.failed_count > 0 ? 'info' : 'success',
          )
        },
        onError: (error) => {
          toast.show(error instanceof Error ? error.message : 'Yükleme başarısız', 'error')
        },
      },
    )
  }

  return (
    <div>
      <PageHeader
        title="Toplu Kaydırma"
        description="Excel'den rezervasyon listesi yükleyip CSM'de toplu kaydırma sub-ticket'ı oluşturun"
      />

      {isPreprod && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-enigma-warning/30 bg-enigma-warning-light px-5 py-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-enigma-warning" />
          <div>
            <p className="text-sm font-medium text-enigma-text">Test Ortamı (Pre-prod)</p>
            <p className="mt-0.5 text-sm text-enigma-text-muted">
              Bu sayfa şu an CSM'nin <strong>pre-prod</strong> ortamına bağlı — gerçek/canlı
              ticket oluşturmaz. Üretime geçmeden önce kategori ID eşlemelerinin doğrulanması
              ve backend'de <code>BULK_SHIFT_ENV=prod</code> yapılması gerekir.
            </p>
          </div>
        </div>
      )}

      <Card className="mb-4">
        <CardHeader
          title="Yükleme"
          subtitle='Excel sütunları: "Rezervasyon No", "Kaydırma Tipi", "Alternatif 1"'
        />
        <CardBody>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className={labelClass}>Excel Dosyası</label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="mt-1 flex w-full items-center gap-3 rounded-lg border border-dashed border-enigma-border bg-enigma-bg px-4 py-4 text-left hover:border-enigma-primary"
              >
                <FileSpreadsheet className="h-5 w-5 shrink-0 text-enigma-text-muted" />
                <span className="text-sm text-enigma-text">
                  {file ? file.name : 'Dosya seçmek için tıklayın (.xlsx)'}
                </span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <div>
              <label className={labelClass}>Üst Ticket UUID</label>
              <input
                className={`${inputClass} mt-1`}
                value={parentTicketUuid}
                onChange={(e) => setParentTicketUuid(e.target.value)}
                placeholder="örn. db61fbfd-7ee8-485b-9370-c1ecac291379"
              />
            </div>

            <div>
              <p className={labelClass}>Raporlayan Kişi</p>
              <div className="mt-1 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <input
                  className={inputClass}
                  value={reporterFirstName}
                  onChange={(e) => setReporterFirstName(e.target.value)}
                  placeholder="Ad"
                />
                <input
                  className={inputClass}
                  value={reporterLastName}
                  onChange={(e) => setReporterLastName(e.target.value)}
                  placeholder="Soyad"
                />
                <input
                  className={inputClass}
                  value={reporterPhone}
                  onChange={(e) => setReporterPhone(e.target.value)}
                  placeholder="Telefon (+90...)"
                />
                <input
                  className={inputClass}
                  type="email"
                  value={reporterEmail}
                  onChange={(e) => setReporterEmail(e.target.value)}
                  placeholder="E-posta"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={!canSubmit || upload.isPending}
              className="flex items-center gap-2 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
            >
              <Upload className="h-4 w-4" />
              {upload.isPending ? 'İşleniyor...' : 'Yükle ve Oluştur'}
            </button>
          </form>
        </CardBody>
      </Card>

      {result && (
        <Card>
          <CardHeader
            title="Sonuçlar"
            subtitle={`${result.total} kayıt · ${result.success_count} başarılı · ${result.failed_count} hatalı`}
            action={
              <ExportCsvButton
                filename="toplu-kaydirma-sonuclar.csv"
                rows={[
                  ['Rezervasyon No', 'Kaydırma Tipi', 'Durum', 'Ticket ID', 'Hata'],
                  ...result.results.map((r) => [
                    r.reservation_no,
                    r.shift_type,
                    r.success ? 'Başarılı' : 'Hatalı',
                    r.ticket_id ?? '',
                    r.error ?? '',
                  ]),
                ]}
              />
            }
          />
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-2 pr-4 font-medium">Rezervasyon No</th>
                    <th className="pb-2 pr-4 font-medium">Kaydırma Tipi</th>
                    <th className="pb-2 pr-4 font-medium">Durum</th>
                    <th className="pb-2 pr-4 font-medium">Ticket / Hata</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((row, index) => (
                    <tr
                      key={`${row.reservation_no}-${index}`}
                      className="border-b border-enigma-border/60 last:border-0"
                    >
                      <td className="py-2.5 pr-4 font-medium text-enigma-text">
                        {row.reservation_no}
                      </td>
                      <td className="py-2.5 pr-4 text-enigma-text-muted">{row.shift_type}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={row.success ? 'success' : 'failed'} />
                      </td>
                      <td className="max-w-xs truncate py-2.5 pr-4 text-enigma-text-muted">
                        {row.success ? `#${row.ticket_id}` : row.error}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
