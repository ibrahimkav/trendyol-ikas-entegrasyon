import { RefreshCw } from 'lucide-react'
import { cn } from './utils'
import Button from './Button'

interface ErrorBannerProps {
  message?: string
  onRetry?: () => void
  className?: string
}

/** Ortak hata banner'ı — Phyllis'in w2a-interaction-spec.md kuralı: kırmızı banner + "Tekrar Dene". */
export default function ErrorBanner({ message = 'Veriler yüklenemedi. Lütfen tekrar deneyin.', onRetry, className }: ErrorBannerProps) {
  return (
    <div className={cn('flex items-center justify-between gap-3 rounded-lg border border-danger bg-danger-soft px-4 py-3 text-sm text-danger', className)}>
      <span>{message}</span>
      {onRetry && (
        <Button variant="danger" size="sm" leftIcon={<RefreshCw className="h-3.5 w-3.5" />} onClick={onRetry}>
          Tekrar Dene
        </Button>
      )}
    </div>
  )
}
