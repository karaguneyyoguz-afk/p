import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import type { ScreenKey } from '@/types/api'

/** Per-route guard: renders children only if the logged-in user's
 * effective_screens includes `screen`, otherwise redirects to /403. Used
 * around each individual route's element in App.tsx (RequireAuth already
 * guarantees a user exists by the time this runs). */
export function RequireScreen({ screen, children }: { screen: ScreenKey; children: ReactNode }) {
  const { hasScreen } = useAuth()

  if (!hasScreen(screen)) {
    return <Navigate to="/403" replace />
  }

  return <>{children}</>
}
