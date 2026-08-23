import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  action?: ReactNode
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-enigma-text">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-enigma-text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  )
}
