import { cn } from './utils'

interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

/** Etiketsiz anahtar — Toggle ve FilterToggle bunun üzerine kurulu. */
export function Switch({ checked, onChange, disabled }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
        checked ? 'bg-brand' : 'bg-app-surface-muted',
        disabled && 'opacity-50',
      )}
    >
      <span
        className={cn(
          'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-1',
        )}
      />
    </button>
  )
}

interface ToggleProps {
  label?: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

/** Etiketli anahtar (etiket solda). */
export default function Toggle({ label, checked, onChange, disabled, className }: ToggleProps) {
  return (
    <label className={cn('flex items-center gap-3 text-sm text-text-primary', disabled && 'opacity-50', className)}>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
      {label}
    </label>
  )
}
