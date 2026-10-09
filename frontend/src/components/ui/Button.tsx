import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from './utils'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2.5 text-sm gap-2',
  lg: 'px-5 py-3 text-base gap-2',
}

// primary = coral (ana CTA), secondary = maroon dolu ("Temizle" vb. — melontik'te outline değil)
const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-hover focus-visible:ring-brand',
  secondary: 'bg-secondary text-white hover:bg-secondary-hover focus-visible:ring-secondary',
  outline: 'border border-app-border bg-app-surface text-text-primary hover:bg-app-surface-muted focus-visible:ring-brand',
  ghost: 'bg-transparent text-text-secondary hover:bg-app-surface-muted focus-visible:ring-brand',
  danger: 'bg-danger text-white hover:bg-danger/90 focus-visible:ring-danger',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  leftIcon,
  rightIcon,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        sizeClasses[size],
        variantClasses[variant],
        className,
      )}
      {...rest}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </button>
  )
}
