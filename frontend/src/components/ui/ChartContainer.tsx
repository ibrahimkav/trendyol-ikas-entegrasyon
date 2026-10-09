import type { ReactNode } from 'react'
import { cn } from './utils'

interface ChartContainerProps {
  title: string
  /** Sağ üstteki dönem filtresi/segmented control gibi aksiyon slotu. */
  action?: ReactNode
  /** Grafiğin altına, ayraç çizgisiyle ayrılmış legend/açıklama slotu. */
  legend?: ReactNode
  children: ReactNode
  className?: string
}

/** Grafik sayfalarındaki (Dashboard, Canlı Performans, Raporlar) ortak kart kabuğu. */
export default function ChartContainer({ title, action, legend, children, className }: ChartContainerProps) {
  return (
    <div className={cn('rounded-lg border border-app-border bg-app-surface p-5 shadow-card', className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        {action}
      </div>
      {children}
      {legend && <div className="mt-4 border-t border-app-border pt-4">{legend}</div>}
    </div>
  )
}
