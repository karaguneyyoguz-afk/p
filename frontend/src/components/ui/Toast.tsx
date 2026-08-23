import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'
import clsx from 'clsx'

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

interface ToastContextValue {
  show: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const TONE_CLASSES: Record<ToastType, string> = {
  success: 'border-enigma-success/30 text-enigma-success',
  error: 'border-enigma-danger/30 text-enigma-danger',
  info: 'border-enigma-primary/30 text-enigma-primary',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (message: string, type: ToastType = 'info') => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, message, type }])
      setTimeout(() => dismiss(id), 4000)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.type]
          return (
            <div
              key={toast.id}
              className={clsx(
                'pointer-events-auto flex items-center gap-2 rounded-lg border bg-enigma-surface px-4 py-3 text-sm text-enigma-text shadow-lg',
                TONE_CLASSES[toast.type],
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="max-w-xs">{toast.message}</span>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="ml-2 text-enigma-text-muted hover:text-enigma-text"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
