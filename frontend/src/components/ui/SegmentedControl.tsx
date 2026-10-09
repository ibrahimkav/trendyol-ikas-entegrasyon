import { cn } from './utils'

interface SegmentedOption<T extends string> {
  value: T
  label: string
}

interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}

/** Genel amaçlı 2+ seçenekli toggle — Kâr Marjı Listesi'ndeki "Yoğunluk: 3 Kolon / 4 Kolon" gibi yerlerde kullan. */
export default function SegmentedControl<T extends string>({ options, value, onChange, className }: SegmentedControlProps<T>) {
  return (
    <div className={cn('inline-flex items-center gap-0.5 rounded-md border border-app-border bg-app-surface p-0.5', className)}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-[6px] px-3 py-1 text-xs font-medium transition-colors',
            value === opt.value ? 'bg-brand-soft text-brand' : 'text-text-secondary hover:bg-app-surface-muted',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
