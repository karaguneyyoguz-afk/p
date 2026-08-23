import { Server, Mail, LayoutGrid, Play } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { ServiceStatusCard } from '@/components/monitoring/ServiceStatusCard'
import { useServiceLogsSummary, useServiceLogs, useStatus } from '@/api/hooks'
import { actorLabel, actorTone } from '@/lib/reportUtils'

const POLL_INTERVAL = 20_000

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const SERVICE_ACTION_LABELS: Record<string, string> = {
  create_ticket: 'Ticket Oluşturma',
  search_customer: 'Müşteri Arama',
  search_product: 'Ürün Arama',
  auth: 'Token Alma',
  connect: 'Bağlantı',
  'GET /api/run': 'Şimdi Çalıştır',
}

function actionLabel(action: string) {
  return SERVICE_ACTION_LABELS[action] ?? action
}

const ACTOR_ORDER = ['sistem', 'panel', 'cli']

export function Monitoring() {
  const { data: summary, isLoading: isLoadingSummary } = useServiceLogsSummary({
    refetchInterval: POLL_INTERVAL,
  })
  const { data: recentLogs } = useServiceLogs({ limit: 10, refetchInterval: POLL_INTERVAL })
  const { data: status } = useStatus({ refetchInterval: POLL_INTERVAL })

  const actorCounts = summary?.actors ?? {}
  const maxActorCount = Math.max(1, ...Object.values(actorCounts))
  const orderedActors = [
    ...ACTOR_ORDER.filter((a) => a in actorCounts),
    ...Object.keys(actorCounts).filter((a) => !ACTOR_ORDER.includes(a)),
  ]

  return (
    <div>
      <PageHeader
        title="Monitoring"
        description="Servis sağlığı ve sistem aktivitesi — CSM API, Gmail IMAP ve panel çağrıları"
      />

      <div className="mb-4 flex items-center gap-3 rounded-xl border border-enigma-border bg-enigma-surface px-5 py-4">
        <span
          className={`flex h-2.5 w-2.5 rounded-full ${status?.is_running ? 'bg-enigma-warning animate-pulse' : 'bg-enigma-success'}`}
        />
        <p className="text-sm text-enigma-text">
          Sistem şu an{' '}
          <span className="font-medium">{status?.is_running ? 'e-posta işliyor' : 'boşta'}</span>
          {status?.last_run && (
            <span className="text-enigma-text-muted">
              {' '}
              · son çalışma {new Date(status.last_run).toLocaleString('tr-TR')}
            </span>
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {isLoadingSummary ? (
          <>
            <div className="h-40 animate-pulse rounded-xl bg-enigma-border/50" />
            <div className="h-40 animate-pulse rounded-xl bg-enigma-border/50" />
            <div className="h-40 animate-pulse rounded-xl bg-enigma-border/50" />
          </>
        ) : (
          <>
            <ServiceStatusCard label="CSM API" icon={Server} summary={summary?.services.csm_api} />
            <ServiceStatusCard label="Gmail IMAP" icon={Mail} summary={summary?.services.gmail_imap} />
            <ServiceStatusCard label="Panel API" icon={LayoutGrid} summary={summary?.services.panel_api} />
          </>
        )}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader
            title="Kaynak Dağılımı"
            subtitle="İşlemleri hangi süreç tetikledi"
          />
          <CardBody className="space-y-4">
            {orderedActors.length === 0 ? (
              <p className="text-sm text-enigma-text-muted">Henüz veri yok</p>
            ) : (
              orderedActors.map((actor) => {
                const count = actorCounts[actor]
                return (
                  <div key={actor}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <Badge tone={actorTone(actor)}>{actorLabel(actor)}</Badge>
                      <span className="font-medium text-enigma-text-muted">{count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-enigma-bg">
                      <div
                        className="h-full rounded-full bg-enigma-primary"
                        style={{ width: `${(count / maxActorCount) * 100}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
            <p className="pt-2 text-xs text-enigma-text-muted">
              Not: gerçek bir giriş/kullanıcı hesabı sistemi yok — "kaynak" sadece hangi
              sürecin (otomatik izleme, panel, CLI) işlemi tetiklediğini gösterir.
            </p>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Son Servis Aktiviteleri" subtitle="En son 10 çağrı" />
          <CardBody>
            {(recentLogs?.logs.length ?? 0) === 0 ? (
              <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
                Henüz aktivite yok
              </div>
            ) : (
              <ul className="divide-y divide-enigma-border">
                {recentLogs!.logs.map((log, index) => (
                  <li key={`${log.timestamp}-${index}`} className="flex items-center gap-3 py-2.5">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-enigma-bg">
                      <Play className="h-3.5 w-3.5 text-enigma-text-muted" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-enigma-text">
                        {actionLabel(log.action)}
                        {log.detail ? (
                          <span className="text-enigma-text-muted"> · {log.detail}</span>
                        ) : null}
                      </p>
                      <p className="text-xs text-enigma-text-muted">
                        {formatTime(log.timestamp)} · <Badge tone={actorTone(log.actor)}>{actorLabel(log.actor)}</Badge>
                      </p>
                    </div>
                    <StatusBadge status={log.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
