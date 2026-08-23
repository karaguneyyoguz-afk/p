import { useMemo } from 'react'
import { Mail, Ticket, CheckCircle2, AlertTriangle, Play } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { EmailVolumeChart } from '@/components/dashboard/EmailVolumeChart'
import { ClassificationDonut } from '@/components/dashboard/ClassificationDonut'
import { RecentActivityTable } from '@/components/dashboard/RecentActivityTable'
import { useStatus, useMailLogs, useRunProcessor } from '@/api/hooks'
import { groupByDay, groupByClassification, recentActivity } from '@/lib/reportUtils'
import { useToast } from '@/components/ui/Toast'

const POLL_INTERVAL = 20_000

export function Dashboard() {
  const { data: status, isLoading, isError } = useStatus({
    refetchInterval: POLL_INTERVAL,
  })
  const { data: mailLogs } = useMailLogs({ refetchInterval: POLL_INTERVAL })
  const runProcessor = useRunProcessor()
  const toast = useToast()

  const handleRunNow = () => {
    toast.show('Sistem başlatılıyor...', 'info')
    runProcessor.mutate(undefined, {
      onSuccess: (result) => {
        if (result.success) {
          toast.show(result.message || 'İşlem tamamlandı', 'success')
        } else {
          toast.show(result.error || result.message || 'İşlem başarısız', 'error')
        }
      },
      onError: (error) =>
        toast.show(error instanceof Error ? error.message : 'Çalıştırma hatası', 'error'),
    })
  }

  const logs = mailLogs?.logs ?? []
  const volumeData = useMemo(() => groupByDay(logs), [logs])
  const categoryData = useMemo(() => groupByClassification(logs), [logs])
  const recent = useMemo(() => recentActivity(logs), [logs])

  const successRate =
    status && status.total_emails_processed > 0
      ? Math.round(
          (status.total_tickets_created / status.total_emails_processed) * 100,
        )
      : 0

  const fmt = (value: number) => {
    if (isLoading) return '—'
    if (isError) return 'Hata'
    return value.toLocaleString('tr-TR')
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Sistem geneline hızlı bir bakış"
        action={
          <button
            type="button"
            onClick={handleRunNow}
            disabled={runProcessor.isPending || status?.is_running}
            className="flex items-center gap-2 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {status?.is_running ? 'Çalışıyor...' : 'Şimdi Çalıştır'}
          </button>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="İşlenen E-posta"
          value={fmt(status?.total_emails_processed ?? 0)}
          icon={Mail}
          tone="primary"
        />
        <StatCard
          label="Oluşturulan Ticket"
          value={fmt(status?.total_tickets_created ?? 0)}
          icon={Ticket}
          tone="success"
        />
        <StatCard
          label="Başarı Oranı"
          value={isLoading ? '—' : isError ? 'Hata' : `%${successRate}`}
          icon={CheckCircle2}
          tone="success"
        />
        <StatCard
          label="Hatalar"
          value={fmt(status?.errors_count ?? 0)}
          icon={AlertTriangle}
          tone="danger"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="E-posta Hacmi"
            subtitle="Son 14 gün, günlük işlenen e-posta sayısı"
          />
          <CardBody>
            <EmailVolumeChart data={volumeData} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Kategori Dağılımı"
            subtitle="Oluşturulan ticket'ların sınıflandırması"
          />
          <CardBody>
            <ClassificationDonut data={categoryData} />
          </CardBody>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <CardHeader
            title="Son Aktiviteler"
            subtitle="En son işlenen e-postalar"
          />
          <CardBody>
            <RecentActivityTable logs={recent} />
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
