import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Enigma paneli beklenmeyen bir hatayla karşılaştı:', error, info)
  }

  handleReload = () => {
    this.setState({ error: null })
    window.location.reload()
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-enigma-bg p-6">
        <div className="max-w-md rounded-xl border border-enigma-border bg-enigma-surface p-8 text-center shadow-sm">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-enigma-danger-light text-enigma-danger">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-lg font-semibold text-enigma-text">
            Beklenmeyen bir hata oluştu
          </h1>
          <p className="mt-2 text-sm text-enigma-text-muted">
            Enigma paneli bir sorunla karşılaştı. Sayfayı yenilemeyi deneyin; sorun
            devam ederse ekip ile paylaşın.
          </p>
          <pre className="mt-4 max-h-32 overflow-auto rounded-lg bg-enigma-bg p-3 text-left text-xs text-enigma-text-muted">
            {error.message}
          </pre>
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-6 rounded-lg bg-enigma-primary px-4 py-2 text-sm font-medium text-white hover:bg-enigma-primary-dark"
          >
            Sayfayı Yenile
          </button>
        </div>
      </div>
    )
  }
}
