import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from './utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, hint, className, id, name, ...rest }, ref) => {
  const inputId = id ?? name
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-text-secondary">
          {label}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        ref={ref}
        className={cn(
          'h-11 rounded-md border bg-app-surface px-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1',
          error ? 'border-danger focus:border-danger focus:ring-danger' : 'border-app-border focus:border-brand focus:ring-brand',
          className,
        )}
        {...rest}
      />
      {error ? <span className="text-xs text-danger">{error}</span> : hint ? <span className="text-xs text-text-muted">{hint}</span> : null}
    </div>
  )
})
Input.displayName = 'Input'

export default Input
