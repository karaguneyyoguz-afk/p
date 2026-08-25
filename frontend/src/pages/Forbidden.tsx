import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

export function Forbidden() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-20 text-center">
      <ShieldAlert className="h-10 w-10 text-enigma-warning" />
      <h1 className="text-lg font-semibold text-enigma-text">Bu ekrana erişim yetkiniz yok</h1>
      <p className="max-w-sm text-sm text-enigma-text-muted">
        Bu sayfayı görüntülemek için gereken izin hesabınıza tanımlı değil. Gerektiğini
        düşünüyorsanız bir yöneticiyle iletişime geçin.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark"
      >
        Dashboard'a dön
      </Link>
    </div>
  )
}
