import { cn } from './utils'

interface RadioOption {
  value: string
  label: string
}

interface RadioGroupProps {
  name: string
  label?: string
  options: RadioOption[]
  value: string
  onChange: (value: string) => void
  className?: string
}

/** Ürün Fiyatlandırma'daki KDV (%20/10/1/0) gibi pill-tarzı radio grubu. */
export default function RadioGroup({ name, label, options, value, onChange, className }: RadioGroupProps) {
  return (
    <fieldset className={cn('flex flex-col gap-2', className)}>
      {label && <legend className="mb-1 text-xs font-medium text-text-secondary">{label}</legend>}
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const checked = opt.value === value
          return (
            <label
              key={opt.value}
              className={cn(
                'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                checked ? 'border-brand bg-brand-soft text-brand' : 'border-app-border text-text-secondary hover:bg-app-surface-muted',
              )}
            >
              <input type="radio" name={name} value={opt.value} checked={checked} onChange={() => onChange(opt.value)} className="sr-only" />
              {opt.label}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
