import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { EmailVolumeChart } from '@/components/dashboard/EmailVolumeChart'
import { SuccessErrorTrendChart } from '@/components/reports/SuccessErrorTrendChart'
import { ClassificationBarChart } from '@/components/reports/ClassificationBarChart'
import { SenderTable } from '@/components/reports/SenderTable'
import { ExportCsvButton } from '@/components/ui/ExportCsvButton'
import { ChartSkeleton } from '@/components/ui/Skeleton'
import {
  useReportsTimeseries,
  useReportsByClassification,
  useReportsBySender,
} from '@/api/hooks'
import { categoryLabel, formatDayLabel } from '@/lib/reportUtils'

const RANGE_OPTIONS = [
  { value: '7d', label: 'Son 7 gün' },
  { value: '14d', label: 'Son 14 gün' },
  { value: '30d', label: 'Son 30 gün' },
]

const selectClass =
  'rounded-lg border border-enigma-border bg-enigma-surface px-3 py-2 text-sm text-enigma-text focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

export function Reports() {
  const [range, setRange] = useState('14d')
  const [classification, setClassification] = useState('')
  const [sender, setSender] = useState('')

  // Unfiltered lookups populate the filter dropdown option lists.
  const { data: allCategories } = useReportsByClassification()
  const { data: allSenders } = useReportsBySender({ limit: 20 })

  const { data: timeseries, isLoading: isLoadingTimeseries } = useReportsTimeseries({
    range,
    classification: classification || undefined,
    sender: sender || undefined,
  })
  const { data: classificationReport, isLoading: isLoadingClassification } =
    useReportsByClassification({
      range,
      sender: sender || undefined,
    })
  const { data: senderReport, isLoading: isLoadingSenders } = useReportsBySender({
    range,
    classification: classification || undefined,
    limit: 10,
  })

  const volumeData = useMemo(
    () =>
      (timeseries?.points ?? []).map((p) => ({
        date: p.date,
        label: formatDayLabel(p.date),
        count: p.count,
      })),
    [timeseries],
  )

  const hasActiveFilters = classification !== '' || sender !== ''

  return (
    <div>
      <PageHeader
        title="Raporlar"
        description="Detaylı, filtrelenebilir e-posta ve ticket raporlaması"
      />

      <Card className="mb-6">
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

          {hasActiveFilters && (
            <button
              type="button"
              onClick={() => {
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Zaman Serisi Trendi"
            subtitle="Seçilen aralıkta işlenen e-posta hacmi"
            action={
              <ExportCsvButton
                filename={`zaman-serisi-${range}.csv`}
                rows={[
                  ['Tarih', 'Toplam', 'Başarılı', 'Hatalı'],
                  ...(timeseries?.points ?? []).map((p) => [
                    p.date,
                    p.count,
                    p.success_count,
                    p.error_count,
                  ]),
                ]}
              />
            }
          />
          <CardBody>
            {isLoadingTimeseries ? (
              <ChartSkeleton />
            ) : (
              <EmailVolumeChart data={volumeData} />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Başarı / Hata Oranı Trendi"
            subtitle="Günlük başarılı ve hatalı işlem sayısı"
          />
          <CardBody>
            {isLoadingTimeseries ? (
              <ChartSkeleton />
            ) : (
              <SuccessErrorTrendChart points={timeseries?.points ?? []} />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Sınıflandırma Dağılımı"
            subtitle="Oluşturulan ticket'ların kategorilere göre dağılımı"
            action={
              <ExportCsvButton
                filename={`siniflandirma-${range}.csv`}
                rows={[
                  ['Kategori', 'Adet'],
                  ...(classificationReport?.categories ?? []).map((c) => [
                    categoryLabel(c.name),
                    c.count,
                  ]),
                ]}
              />
            }
          />
          <CardBody>
            {isLoadingClassification ? (
              <ChartSkeleton />
            ) : (
              <ClassificationBarChart categories={classificationReport?.categories ?? []} />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Gönderen Bazlı Hacim"
            subtitle="En çok yazan 10 gönderen"
            action={
              <ExportCsvButton
                filename={`gonderenler-${range}.csv`}
                rows={[
                  ['Gönderen', 'Adet'],
                  ...(senderReport?.senders ?? []).map((s) => [
                    s.sender_email,
                    s.count,
                  ]),
                ]}
              />
            }
          />
          <CardBody>
            {isLoadingSenders ? (
              <ChartSkeleton />
            ) : (
              <SenderTable senders={senderReport?.senders ?? []} />
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
