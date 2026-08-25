import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const inputClass =
  'w-full rounded-lg border border-enigma-border bg-enigma-bg px-3 py-2 text-sm text-enigma-text placeholder:text-enigma-text-muted focus:border-enigma-primary focus:outline-none focus:ring-2 focus:ring-enigma-primary/20'

export function Login() {
  const { user, isLoading, login, loginError, isLoggingIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!isLoading && user) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(email.trim(), password)
    } catch {
      setError(loginError)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-enigma-bg px-4">
      <div className="w-full max-w-sm rounded-xl border border-enigma-border bg-enigma-surface p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-enigma-primary text-white">
            E
          </span>
          <span className="text-lg font-semibold text-enigma-text">Enigma</span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-enigma-text-muted">E-posta</label>
            <input
              type="email"
              required
              autoFocus
              className={`${inputClass} mt-1`}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ad.soyad@tatilbudur.com"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-enigma-text-muted">Şifre</label>
            <input
              type="password"
              required
              className={`${inputClass} mt-1`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {(error || loginError) && (
            <p className="rounded-lg bg-enigma-danger-light px-3 py-2 text-sm text-enigma-danger">
              {error ?? loginError}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoggingIn}
            className="w-full rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark disabled:opacity-50"
          >
            {isLoggingIn ? 'Giriş yapılıyor...' : 'Giriş Yap'}
          </button>
        </form>
      </div>
    </div>
  )
}
