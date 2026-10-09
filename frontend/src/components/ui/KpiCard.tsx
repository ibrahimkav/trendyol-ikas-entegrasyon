import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import { cn } from './utils'

interface KpiCardProps {
  label: string
  value: string
  delta?: { value: string; positive: boolean }
  /** Genelde <Sparkline /> — kartın sağ altına yerleşir. */
  sparkline?: ReactNode
  icon?: ReactNode
  /** Etiketin yanına bilgi ikonu ekler (ör. oranın neye bölündüğünü açıklamak için). ColoredKpiCard ile aynı desen. */
  tooltip?: string
  className?: string
}

/** Dashboard'daki 6 KPI kartı gibi: etiket + büyük değer + opsiyonel delta rozeti + sparkline slotu. */
export default function KpiCard({ label, value, delta, sparkline, icon, tooltip, className }: KpiCardProps) {
  return (
    <div className={cn('rounded-lg border border-app-border bg-app-surface p-5 shadow-card', className)}>
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-1 text-caption uppercase tracking-wide text-text-secondary">
          {label}
          {tooltip && (
            <span title={tooltip} className="inline-flex cursor-help normal-case tracking-normal">
              <Info className="h-3.5 w-3.5 opacity-70" />
            </span>
          )}
        </span>
        {icon}
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <span className="text-kpi-value tabular-nums text-text-primary">{value}</span>
        {sparkline}
      </div>
      {delta && (
        <span className={cn('mt-2 inline-flex items-center text-xs font-medium', delta.positive ? 'text-success' : 'text-danger')}>
          {delta.positive ? '▲' : '▼'}&nbsp;{delta.value}
        </span>
      )}
    </div>
  )
}
