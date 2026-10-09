import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { cn, formatCurrency, formatPercent } from './utils'

export type BadgeTone = 'brand' | 'maroon' | 'success' | 'danger' | 'warning' | 'info' | 'neutral'

const toneClasses: Record<BadgeTone, string> = {
  brand: 'bg-brand-soft text-brand',
  maroon: 'bg-app-surface-muted text-secondary',
  success: 'bg-success-soft text-success',
  danger: 'bg-danger-soft text-danger',
  warning: 'bg-warning-soft text-warning',
  info: 'bg-info-soft text-info',
  neutral: 'bg-app-surface-muted text-text-secondary',
}

interface BadgeProps {
  tone?: BadgeTone
  icon?: ReactNode
  children: ReactNode
  className?: string
}

/** Genel amaçlı rozet (pill). Kâr/zarar için ProfitBadge'i tercih et. */
export function Badge({ tone = 'neutral', icon, children, className }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium', toneClasses[tone], className)}>
      {icon}
      {children}
    </span>
  )
}

interface ProfitBadgeProps {
  /** Kâr (+) veya zarar (-) tutarı, ör. 882.5 */
  amount: number
  /** Yüzde oranı, ör. 64.5 */
  percent?: number
  currency?: string
  className?: string
}

/**
 * Melontik'teki "₺882,50 Kâr (%64,50)" rozeti — tutar+yön rengi+ok ile çift kodlu (renk körlüğüne
 * dayanıklı). Format: Phyllis'in w2a-interaction-spec.md ortak kuralı (₺X.XXX,XX / %X,XX).
 */
export function ProfitBadge({ amount, percent, currency = '₺', className }: ProfitBadgeProps) {
  const isProfit = amount >= 0
  const tone: BadgeTone = isProfit ? 'success' : 'danger'
  const Icon = isProfit ? ArrowUpRight : ArrowDownRight
  const label = isProfit ? 'Kâr' : 'Zarar'

  return (
    <Badge tone={tone} icon={<Icon className="h-3.5 w-3.5" />} className={className}>
      {formatCurrency(Math.abs(amount), currency)} {label}
      {percent !== undefined ? ` (${formatPercent(Math.abs(percent))})` : ''}
    </Badge>
  )
}
