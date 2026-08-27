import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import {
  Sparkles,
  Mail,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Zap,
  BarChart3,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const inputClass =
  'w-full rounded-xl border border-enigma-border bg-enigma-bg py-3 pl-11 pr-4 text-sm text-enigma-text placeholder:text-enigma-text-muted transition-all focus:border-enigma-primary focus:outline-none focus:ring-4 focus:ring-enigma-primary/15'

const highlights = [
  { icon: Zap, text: 'Gelen mailden otomatik ticket oluşturma' },
  { icon: ShieldCheck, text: 'Phishing ve uygunsuz içerik koruması' },
  { icon: BarChart3, text: 'Gerçek zamanlı izleme ve raporlama' },
]

export function Login() {
  const { user, isLoading, login, loginError, isLoggingIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
    <div className="flex min-h-screen bg-enigma-bg">
      {/* Marka paneli -- küçük ekranlarda gizlenir */}
      <div className="relative hidden w-[42%] shrink-0 overflow-hidden bg-enigma-sidebar lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              'radial-gradient(circle at 15% 20%, rgba(79,124,255,0.35), transparent 45%), radial-gradient(circle at 85% 75%, rgba(114,57,234,0.3), transparent 50%)',
          }}
        />

        <div className="relative flex items-center gap-2.5">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-enigma-primary shadow-lg shadow-enigma-primary/30">
            <Sparkles className="h-5 w-5 text-white" strokeWidth={2.5} />
          </span>
          <span className="text-xl font-semibold tracking-tight text-white">Enigma</span>
        </div>

        <div className="relative">
          <h1 className="max-w-sm text-3xl font-semibold leading-tight text-white text-balance">
            Mail otomasyonunuzu tek panelden yönetin
          </h1>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-enigma-sidebar-text">
            Müşteri talepleri otomatik ticket'a dönüşsün, ekibiniz gerçek işe odaklansın.
          </p>

          <div className="mt-8 space-y-3.5">
            {highlights.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="h-4 w-4 text-enigma-primary" strokeWidth={2.25} />
                </span>
                <span className="text-sm text-enigma-sidebar-text">{text}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-enigma-sidebar-text/70">
          Tatilbudur Seyahat Acenteliği ve Turizm A.Ş.
        </p>
      </div>

      {/* Form paneli */}
      <div className="flex flex-1 items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-enigma-primary">
              <Sparkles className="h-4.5 w-4.5 text-white" strokeWidth={2.5} />
            </span>
            <span className="text-lg font-semibold text-enigma-text">Enigma</span>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-enigma-text">Tekrar hoş geldiniz</h2>
          <p className="mt-1.5 text-sm text-enigma-text-muted">Devam etmek için hesabınıza giriş yapın</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-enigma-text-muted">
                E-posta
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
                <input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  autoComplete="email"
                  className={inputClass}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ad.soyad@tatilbudur.com"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-enigma-text-muted">
                Şifre
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-enigma-text-muted" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  className={`${inputClass} pr-11`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-enigma-text-muted transition-colors hover:text-enigma-text"
                  aria-label={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {(error || loginError) && (
              <div className="flex items-start gap-2 rounded-xl bg-enigma-danger-light px-3.5 py-2.5 text-sm text-enigma-danger">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error ?? loginError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoggingIn}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-enigma-primary px-4 py-3 text-sm font-medium text-white shadow-lg shadow-enigma-primary/25 transition-all hover:bg-enigma-primary-dark hover:shadow-enigma-primary/35 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
            >
              {isLoggingIn ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Giriş yapılıyor...
                </>
              ) : (
                'Giriş Yap'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
