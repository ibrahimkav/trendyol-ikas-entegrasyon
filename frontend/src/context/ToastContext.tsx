import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'info'

type ToastItem = { id: string; type: ToastType; message: string }

type ToastContextValue = {
  toast: (t: { type: ToastType; message: string }) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx.toast
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const toast = useCallback((t: { type: ToastType; message: string }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    setItems((s) => [...s, { ...t, id }])
    window.setTimeout(() => {
      setItems((s) => s.filter((x) => x.id !== id))
    }, 6000)
  }, [])

  const dismiss = useCallback((id: string) => {
    setItems((s) => s.filter((x) => x.id !== id))
  }, [])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-4 z-[100] flex max-w-md flex-col gap-2 sm:right-6"
        aria-live="polite"
        aria-relevant="additions"
      >
        {items.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${
              t.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
                : t.type === 'error'
                  ? 'border-red-200 bg-red-50 text-red-950'
                  : 'border-sky-200 bg-sky-50 text-sky-950'
            }`}
            role="status"
          >
            {t.type === 'success' ? (
              <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
            ) : t.type === 'error' ? (
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" aria-hidden />
            ) : (
              <Info className="mt-0.5 h-5 w-5 shrink-0 text-sky-600" aria-hidden />
            )}
            <p className="min-w-0 flex-1 leading-snug">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="shrink-0 rounded-lg p-1 opacity-70 hover:bg-black/5 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-trendyol-primary"
              aria-label="Kapat"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
