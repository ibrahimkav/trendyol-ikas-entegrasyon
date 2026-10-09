import { useEffect, type ReactNode } from 'react'
import Button, { type ButtonVariant } from './Button'

interface ConfirmDialogProps {
  open: boolean
  title: string
  /** Çok satırlı olabilir (\n ile) — native confirm()'in mesaj metni gibi. */
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  /** İptal butonu + backdrop + Escape hepsi bunu tetikler. */
  onCancel: () => void
  onConfirm: () => void
  confirmVariant?: ButtonVariant
  /** Onay sırasında (ör. istek atarken) butonları kilitlemek için. */
  loading?: boolean
  /** Onay öncesi ek bir seçim göstermek için (ör. "görselleri de indir" anahtarı). */
  children?: ReactNode
}

/** Native confirm()/alert() yerine kullanılan uygulama-içi onay modal'ı (bkz. w3-confirm-dialogs). */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Devam Et',
  cancelLabel = 'İptal',
  onCancel,
  onConfirm,
  confirmVariant = 'primary',
  loading = false,
  children,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) onCancel()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, loading, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={() => !loading && onCancel()}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="w-full max-w-md rounded-lg bg-app-surface shadow-elevated p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="text-lg font-semibold text-text-primary">
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm text-text-secondary whitespace-pre-line">{description}</p>
        )}
        {children && <div className="mt-4">{children}</div>}
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={loading}>
            {loading ? 'İşleniyor...' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
