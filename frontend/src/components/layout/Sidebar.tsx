import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  BarChart3,
  Mail,
  Ticket,
  Settings,
  Sparkles,
  X,
  Activity,
  ScrollText,
  FileSpreadsheet,
  Users as UsersIcon,
} from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '@/contexts/AuthContext'
import type { ScreenKey } from '@/types/api'

const navGroups = [
  {
    label: 'Genel',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true, screen: 'dashboard' as ScreenKey },
      { to: '/reports', label: 'Raporlar', icon: BarChart3, screen: 'reports' as ScreenKey },
    ],
  },
  {
    label: 'İzleme',
    items: [
      { to: '/monitoring', label: 'Monitoring', icon: Activity, screen: 'monitoring' as ScreenKey },
      { to: '/logs', label: 'Loglar', icon: ScrollText, screen: 'logs' as ScreenKey },
    ],
  },
  {
    label: 'İşlemler',
    items: [
      { to: '/emails', label: 'E-postalar', icon: Mail, screen: 'emails' as ScreenKey },
      { to: '/tickets', label: 'Talepler', icon: Ticket, screen: 'tickets' as ScreenKey },
      { to: '/bulk-shift', label: 'Toplu Kaydırma', icon: FileSpreadsheet, screen: 'bulk_shift' as ScreenKey },
      { to: '/settings', label: 'Ayarlar', icon: Settings, screen: 'settings' as ScreenKey },
      { to: '/users', label: 'Kullanıcılar', icon: UsersIcon, screen: 'users' as ScreenKey },
    ],
  },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { hasScreen } = useAuth()
  const visibleGroups = navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => hasScreen(item.screen)) }))
    .filter((group) => group.items.length > 0)

  return (
    <aside
      className={clsx(
        'fixed inset-y-0 left-0 z-40 flex h-screen w-64 shrink-0 flex-col overflow-y-auto bg-enigma-sidebar transition-transform duration-200 ease-in-out',
        'lg:static lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full',
      )}
    >
      <div className="flex h-16 shrink-0 items-center justify-between gap-2 px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-enigma-primary">
            <Sparkles className="h-4.5 w-4.5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-lg font-semibold tracking-tight text-white">
            Enigma
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Menüyü kapat"
          className="text-enigma-sidebar-text hover:text-white lg:hidden"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="mt-2 flex-1 space-y-1 px-3">
        {visibleGroups.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-2 pt-3 text-xs font-semibold uppercase tracking-wider text-enigma-sidebar-text/70">
              {group.label}
            </p>
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onClose}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-enigma-sidebar-active text-enigma-sidebar-text-active'
                      : 'text-enigma-sidebar-text hover:bg-enigma-sidebar-hover hover:text-enigma-sidebar-text-active',
                  )
                }
              >
                <Icon className="h-4.5 w-4.5" strokeWidth={2} />
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="mx-3 mb-4 mt-4 shrink-0 rounded-lg bg-enigma-sidebar-hover p-4">
        <p className="text-sm font-medium text-white">E-posta Otomasyonu</p>
        <p className="mt-1 text-xs text-enigma-sidebar-text">
          CSM ticket motoru aktif
        </p>
      </div>
    </aside>
  )
}
