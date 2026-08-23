import type { ReactNode } from 'react'
import clsx from 'clsx'

interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-xl border border-enigma-border bg-enigma-surface shadow-sm',
        className,
      )}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
}

export function CardHeader({ title, subtitle, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between border-b border-enigma-border px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-enigma-text">{title}</h3>
        {subtitle && (
          <p className="mt-0.5 text-xs text-enigma-text-muted">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  )
}

export function CardBody({ children, className }: CardProps) {
  return <div className={clsx('p-5', className)}>{children}</div>
}
