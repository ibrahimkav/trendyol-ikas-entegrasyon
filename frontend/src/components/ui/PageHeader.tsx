import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { cn } from './utils'

interface Breadcrumb {
  label: string
  onClick?: () => void
}

interface PageHeaderProps {
  title: string
  breadcrumbs?: Breadcrumb[]
  /** "PDF olarak indir" gibi sayfa aksiyonları — sağda görünür. */
  actions?: ReactNode
  className?: string
}

/** Sayfa üstü başlık şeridi: breadcrumb + başlık + aksiyon slotu. Routing'e bağlı değildir (onClick ile entegre edilir). */
export default function PageHeader({ title, breadcrumbs, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-2 border-b border-app-border pb-4 sm:flex-row sm:items-center sm:justify-between', className)}>
      <div>
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="mb-1 flex items-center gap-1 text-xs text-text-secondary">
            {breadcrumbs.map((crumb, i) => (
              <span key={crumb.label} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3 w-3" />}
                {crumb.onClick ? (
                  <button type="button" onClick={crumb.onClick} className="hover:text-brand">
                    {crumb.label}
                  </button>
                ) : (
                  <span>{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-xl font-semibold tracking-tight text-text-primary sm:text-2xl">{title}</h1>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
