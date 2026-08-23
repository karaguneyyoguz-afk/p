import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Moon, Sun, Menu } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'
import { NotificationBell } from './NotificationBell'
import { WeatherStrip } from './WeatherStrip'

interface TopbarProps {
  onMenuClick: () => void
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    const term = query.trim()
    if (!term) return
    navigate(`/tickets?q=${encodeURIComponent(term)}`)
  }

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-enigma-border bg-enigma-surface px-4 sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Menüyü aç"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-enigma-text-muted hover:bg-enigma-bg hover:text-enigma-text lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <form onSubmit={handleSearch} className="relative w-full max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ticket, gönderen veya konu ara..."
          className="w-full rounded-lg border border-enigma-border bg-enigma-bg py-2 pl-9 pr-3 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20"
        />
      </form>

      <div className="flex shrink-0 items-center gap-2 sm:gap-4">
        <WeatherStrip />

        <button
          type="button"
          onClick={toggle}
          aria-label="Temayı değiştir"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-enigma-text-muted transition-colors hover:bg-enigma-bg hover:text-enigma-text"
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>

        <NotificationBell />

        <div className="flex items-center gap-3 border-l border-enigma-border pl-2 sm:pl-4">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-enigma-text">Enigma Admin</p>
            <p className="text-xs text-enigma-text-muted">Yönetici</p>
          </div>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-enigma-primary-light text-sm font-semibold text-enigma-primary">
            M
          </div>
        </div>
      </div>
    </header>
  )
}
