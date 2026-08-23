import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { useErrors } from '@/api/hooks'

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { data } = useErrors({ refetchInterval: 30_000 })
  const errors = data?.errors ?? []
  const recent = errors.slice(0, 5)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Bildirimler"
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-enigma-text-muted transition-colors hover:bg-enigma-bg hover:text-enigma-text"
      >
        <Bell className="h-5 w-5" />
        {errors.length > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-enigma-danger px-1 text-[10px] font-semibold text-white">
            {errors.length > 99 ? '99+' : errors.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 rounded-xl border border-enigma-border bg-enigma-surface shadow-lg">
          <div className="border-b border-enigma-border px-4 py-3">
            <p className="text-sm font-semibold text-enigma-text">Bildirimler</p>
            <p className="text-xs text-enigma-text-muted">
              {errors.length} hata kaydı
            </p>
          </div>
          {recent.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-enigma-text-muted">
              Hata yok
            </p>
          ) : (
            <ul className="max-h-72 divide-y divide-enigma-border overflow-y-auto">
              {recent.map((error, index) => (
                <li key={`${error.timestamp}-${index}`} className="px-4 py-3">
                  <p className="text-sm text-enigma-text">{error.error}</p>
                  <p className="mt-0.5 text-xs text-enigma-text-muted">
                    {formatTime(error.timestamp)}
                    {error.sender_email ? ` · ${error.sender_email}` : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              navigate('/settings')
            }}
            className="block w-full rounded-b-xl border-t border-enigma-border px-4 py-2.5 text-center text-sm font-medium text-enigma-primary hover:bg-enigma-bg"
          >
            Tümünü Gör
          </button>
        </div>
      )}
    </div>
  )
}
