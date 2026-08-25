import { useState, type FormEvent } from 'react'
import { UserPlus, ShieldOff } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeactivateUser,
  useUserOverrides,
  useSetUserOverrides,
} from '@/api/hooks'
import { useAuth } from '@/contexts/AuthContext'
import { ALL_SCREENS, ALL_ROLES, SCREEN_LABELS, ROLE_LABELS } from '@/lib/screens'
import type { Role, ScreenKey, User } from '@/types/api'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

export function Users() {
  const { user: me } = useAuth()
  const { data, isLoading } = useUsers()

  const [showCreate, setShowCreate] = useState(false)
  const [screensUser, setScreensUser] = useState<User | null>(null)

  const users = data?.users ?? []

  return (
    <div>
      <PageHeader
        title="Kullanıcılar"
        description="Panel kullanıcıları, rolleri ve ekran bazlı istisnaları"
        action={
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark"
          >
            <UserPlus className="h-4 w-4" />
            Yeni Kullanıcı
          </button>
        }
      />

      <Card>
        <CardHeader title="Kullanıcı Listesi" />
        <CardBody>
          {isLoading ? (
            <div className="h-32 animate-pulse rounded-lg bg-enigma-bg" />
          ) : users.length === 0 ? (
            <p className="py-8 text-center text-sm text-enigma-text-muted">Henüz kullanıcı yok</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-enigma-border text-xs uppercase tracking-wider text-enigma-text-muted">
                    <th className="pb-2 pr-4 font-medium">E-posta</th>
                    <th className="pb-2 pr-4 font-medium">Rol</th>
                    <th className="pb-2 pr-4 font-medium">Durum</th>
                    <th className="pb-2 pr-4 font-medium">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <UserRow
                      key={u.id}
                      user={u}
                      isSelf={u.id === me?.id}
                      onEditScreens={() => setScreensUser(u)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} />}
      {screensUser && (
        <UserScreensModal user={screensUser} onClose={() => setScreensUser(null)} />
      )}
    </div>
  )
}

function UserRow({
  user,
  isSelf,
  onEditScreens,
}: {
  user: User
  isSelf: boolean
  onEditScreens: () => void
}) {
  const updateUser = useUpdateUser()
  const deactivateUser = useDeactivateUser()
  const toast = useToast()

  const handleRoleChange = (role: Role) => {
    updateUser.mutate(
      { id: user.id, role },
      { onError: (e) => toast.show(e instanceof Error ? e.message : 'Güncellenemedi', 'error') },
    )
  }

  const handleDeactivate = () => {
    if (!window.confirm(`${user.email} pasifleştirilsin mi?`)) return
    deactivateUser.mutate(user.id, {
      onError: (e) => toast.show(e instanceof Error ? e.message : 'İşlem başarısız', 'error'),
    })
  }

  return (
    <tr className="border-b border-enigma-border/60 last:border-0">
      <td className="py-2.5 pr-4 font-medium text-enigma-text">{user.email}</td>
      <td className="py-2.5 pr-4">
        <select
          value={user.role}
          disabled={isSelf}
          onChange={(e) => handleRoleChange(e.target.value as Role)}
          className={`${inputClass} w-auto py-1 disabled:opacity-50`}
        >
          {ALL_ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </td>
      <td className="py-2.5 pr-4">
        <Badge tone={user.is_active ? 'success' : 'neutral'}>
          {user.is_active ? 'Aktif' : 'Pasif'}
        </Badge>
      </td>
      <td className="py-2.5 pr-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onEditScreens}
            className="rounded-lg border border-enigma-border px-3 py-1 text-xs font-medium text-enigma-text hover:bg-enigma-bg"
          >
            Ekran İzinleri
          </button>
          {!isSelf && user.is_active && (
            <button
              type="button"
              onClick={handleDeactivate}
              className="flex items-center gap-1 rounded-lg border border-enigma-border px-3 py-1 text-xs font-medium text-enigma-danger hover:bg-enigma-danger-light"
            >
              <ShieldOff className="h-3.5 w-3.5" />
              Pasifleştir
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const createUser = useCreateUser()
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('operator')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    createUser.mutate(
      { email: email.trim(), password, role },
      {
        onSuccess: () => {
          toast.show('Kullanıcı oluşturuldu', 'success')
          onClose()
        },
        onError: (err) => setError(err instanceof Error ? err.message : 'Oluşturulamadı'),
      },
    )
  }

  return (
    <Modal title="Yeni Kullanıcı" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-xs font-medium text-enigma-text-muted">E-posta</label>
          <input
            type="email"
            required
            className={`${inputClass} mt-1`}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-enigma-text-muted">Şifre (en az 8 karakter)</label>
          <input
            type="password"
            required
            minLength={8}
            className={`${inputClass} mt-1`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-enigma-text-muted">Rol</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className={`${inputClass} mt-1`}
          >
            {ALL_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <p className="rounded-lg bg-enigma-danger-light px-3 py-2 text-sm text-enigma-danger">{error}</p>
        )}

        <button
          type="submit"
          disabled={createUser.isPending}
          className="w-full rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
        >
          {createUser.isPending ? 'Oluşturuluyor...' : 'Oluştur'}
        </button>
      </form>
    </Modal>
  )
}

function UserScreensModal({ user, onClose }: { user: User; onClose: () => void }) {
  const { data, isLoading } = useUserOverrides(user.id)
  const setOverrides = useSetUserOverrides()
  const toast = useToast()

  const roleScreens = new Set(data?.role_screens ?? [])
  const effectiveScreens = new Set(data?.effective_screens ?? [])

  const handleToggle = (screen: ScreenKey, checked: boolean) => {
    // null removes any existing override (falls back to role default) when
    // the requested state already matches the role default -- keeps the
    // override table free of no-op rows, matching build_bulk... no, matching
    // accounts_routes.set_overrides' own no-op check.
    const allow = checked === roleScreens.has(screen) ? null : checked
    setOverrides.mutate(
      { userId: user.id, overrides: { [screen]: allow } as Record<ScreenKey, boolean | null> },
      { onError: (e) => toast.show(e instanceof Error ? e.message : 'Güncellenemedi', 'error') },
    )
  }

  return (
    <Modal title={`Ekran İzinleri — ${user.email}`} subtitle={`Rol: ${data?.role ?? user.role}`} onClose={onClose}>
      {isLoading ? (
        <div className="h-40 animate-pulse rounded-lg bg-enigma-bg" />
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-enigma-text-muted">
            İşaretli olanlar rolden geliyor veya ek olarak verilmiş. İşareti kaldırmak rolün
            verdiği ekranı bu kullanıcıdan alır; rolde olmayan bir ekranı işaretlemek ise ek
            olarak verir.
          </p>
          <div className="divide-y divide-enigma-border rounded-lg border border-enigma-border">
            {ALL_SCREENS.map((screen) => {
              const checked = effectiveScreens.has(screen)
              const isRoleDefault = roleScreens.has(screen)
              return (
                <label
                  key={screen}
                  className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm"
                >
                  <span className="text-enigma-text">{SCREEN_LABELS[screen]}</span>
                  <span className="flex items-center gap-2">
                    {isRoleDefault && !checked && (
                      <Badge tone="warning">rolden kaldırıldı</Badge>
                    )}
                    {!isRoleDefault && checked && <Badge tone="info">ek verildi</Badge>}
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={setOverrides.isPending}
                      onChange={(e) => handleToggle(screen, e.target.checked)}
                      className="h-4 w-4 rounded border-enigma-border accent-enigma-primary"
                    />
                  </span>
                </label>
              )
            })}
          </div>
        </div>
      )}
    </Modal>
  )
}
