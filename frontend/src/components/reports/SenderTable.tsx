import type { SenderCount } from '@/types/api'

export function SenderTable({ senders }: { senders: SenderCount[] }) {
  if (senders.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-enigma-text-muted">
        Veri yok
      </div>
    )
  }

  const max = Math.max(...senders.map((s) => s.count))

  return (
    <div className="space-y-3">
      {senders.map((sender) => (
        <div key={sender.sender_email} className="flex items-center gap-3">
          <span className="w-56 shrink-0 truncate text-sm text-enigma-text">
            {sender.sender_email}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-enigma-bg">
            <div
              className="h-full rounded-full bg-enigma-primary"
              style={{ width: `${(sender.count / max) * 100}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-sm font-medium text-enigma-text-muted">
            {sender.count}
          </span>
        </div>
      ))}
    </div>
  )
}
