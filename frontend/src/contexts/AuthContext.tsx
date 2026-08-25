import { createContext, useContext, type ReactNode } from 'react'
import { useCurrentUser, useLogin, useLogout } from '@/api/hooks'
import type { CurrentUser, ScreenKey } from '@/types/api'

interface AuthContextValue {
  user: CurrentUser | null
  isLoading: boolean
  effectiveScreens: ScreenKey[]
  hasScreen: (screen: ScreenKey) => boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  logout: () => Promise<void>
  loginError: string | null
  isLoggingIn: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useCurrentUser()
  const loginMutation = useLogin()
  const logoutMutation = useLogout()

  const effectiveScreens = user?.effective_screens ?? []

  const value: AuthContextValue = {
    user: user ?? null,
    isLoading,
    effectiveScreens,
    hasScreen: (screen) => effectiveScreens.includes(screen),
    login: async (email, password) => loginMutation.mutateAsync({ email, password }),
    logout: async () => {
      await logoutMutation.mutateAsync()
    },
    loginError: loginMutation.error instanceof Error ? loginMutation.error.message : null,
    isLoggingIn: loginMutation.isPending,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth, AuthProvider icinde kullanilmali')
  return ctx
}
