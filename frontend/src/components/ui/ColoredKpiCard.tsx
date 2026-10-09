import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import { cn } from './utils'

export type KpiTone = 'success' | 'info' | 'warning' | 'brand' | 'neutral'

const toneClasses: Record<KpiTone, string> = {
  success: 'bg-success-soft text-success',
  info: 'bg-info-soft text-info',
  warning: 'bg-warning-soft text-warning',
  brand: 'bg-brand-soft text-brand',
  neutral: 'bg-app-surface-muted text-text-secondary',
}

interface ColoredKpiCardProps {
  label: string
  value: string
  tone?: KpiTone
  /** Bilgi ikonunun title'ı (Canlı Performans'taki "Info" tıklamaları gibi). */
  tooltip?: string
  icon?: ReactNode
  className?: string
}

/** Canlı Performans sayfasındaki 4 renkli KPI kartı deseni (yeşil/cyan/turuncu/gri + Info). */
export default function ColoredKpiCard({ label, value, tone = 'neutral', tooltip, icon, className }: ColoredKpiCardProps) {
  return (
    <div className={cn('rounded-lg p-4', toneClasses[tone], className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium">{label}</span>
        <span className="flex items-center gap-1">
          {icon}
          {tooltip && (
            <span title={tooltip} className="inline-flex cursor-help">
              <Info className="h-3.5 w-3.5 opacity-70" />
            </span>
          )}
        </span>
      </div>
      <p className="mt-1 text-xl font-bold tabular-nums">{value}</p>
    </div>
  )
}
