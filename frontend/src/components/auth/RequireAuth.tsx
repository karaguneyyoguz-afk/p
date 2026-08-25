import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

/** Parent-route guard: redirects to /login if not authenticated. Used as
 * `<Route element={<RequireAuth />}>` wrapping <AppLayout />'s route so the
 * check runs once for the whole app shell, not per-page. */
export function RequireAuth() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-enigma-bg text-sm text-enigma-text-muted">
        Yükleniyor...
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
