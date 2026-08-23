import type { MailLogEntry } from '@/types/api'
import { StatusBadge } from '@/components/ui/Badge'
import { categoryLabel, topLevelCategory } from '@/lib/reportUtils'

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function RecentActivityTable({ logs }: { logs: MailLogEntry[] }) {
  if (logs.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
        Henüz aktivite yok
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
            <th className="pb-2 pr-4 font-medium">Zaman</th>
            <th className="pb-2 pr-4 font-medium">Gönderen</th>
            <th className="pb-2 pr-4 font-medium">Kategori</th>
            <th className="pb-2 pr-4 font-medium">Durum</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, index) => (
            <tr
              key={`${log.timestamp}-${index}`}
              className="border-b border-enigma-border/60 last:border-0"
            >
              <td className="whitespace-nowrap py-2.5 pr-4 text-enigma-text-muted">
                {formatTime(log.timestamp)}
              </td>
              <td className="max-w-[220px] truncate py-2.5 pr-4 text-enigma-text">
                {log.sender_email || '—'}
              </td>
              <td className="py-2.5 pr-4 text-enigma-text-muted">
                {categoryLabel(topLevelCategory(log.classification))}
              </td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={log.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
