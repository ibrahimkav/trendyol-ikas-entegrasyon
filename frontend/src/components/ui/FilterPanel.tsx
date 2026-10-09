import type { ReactNode } from 'react'
import { cn } from './utils'
import Button from './Button'
import { Switch } from './Toggle'

interface FilterPanelProps {
  title?: string
  children: ReactNode
  onClear?: () => void
  className?: string
}

/** Kâr Marjı Listesi'ndeki "Ürünleri Filtreleyin" sol panel iskeleti. */
export default function FilterPanel({ title = 'Ürünleri Filtreleyin', children, onClear, className }: FilterPanelProps) {
  return (
    <div className={cn('flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        {onClear && (
          <Button variant="secondary" size="sm" onClick={onClear}>
            Filtreleri Temizle
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </div>
  )
}

interface FilterToggleProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}

/** "Kâr eden / Zarar eden ürünleri göster" gibi etiket solda + switch sağda satırı. */
export function FilterToggle({ label, checked, onChange }: FilterToggleProps) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 text-sm text-text-primary">
      {label}
      <Switch checked={checked} onChange={onChange} />
    </label>
  )
}

interface FilterRangeProps {
  label: string
  minValue: string
  maxValue: string
  onMinChange: (value: string) => void
  onMaxChange: (value: string) => void
  minPlaceholder?: string
  maxPlaceholder?: string
}

/** "Min/Max kâr oranı (%)" gibi iki inputlu aralık filtresi. */
export function FilterRange({
  label,
  minValue,
  maxValue,
  onMinChange,
  onMaxChange,
  minPlaceholder = 'Min',
  maxPlaceholder = 'Max',
}: FilterRangeProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-text-secondary">{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={minValue}
          onChange={(e) => onMinChange(e.target.value)}
          placeholder={minPlaceholder}
          className="w-full rounded-sm border border-app-border bg-app-surface px-3 py-2 text-sm text-text-primary focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <span className="text-text-muted">–</span>
        <input
          type="number"
          value={maxValue}
          onChange={(e) => onMaxChange(e.target.value)}
          placeholder={maxPlaceholder}
          className="w-full rounded-sm border border-app-border bg-app-surface px-3 py-2 text-sm text-text-primary focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
      </div>
    </div>
  )
}
