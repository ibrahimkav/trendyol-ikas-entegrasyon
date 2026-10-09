import { Calendar } from 'lucide-react'
import { cn } from './utils'

interface DateRangePickerProps {
  /** ISO yyyy-mm-dd */
  startDate: string
  endDate: string
  onChange: (range: { startDate: string; endDate: string }) => void
  className?: string
}

/** Dashboard'daki "Tarih Aralığı : 2 Eyl 2026 – 9 Eyl 2026" seçici — ek tarih kütüphanesi olmadan native input[type=date]. */
export default function DateRangePicker({ startDate, endDate, onChange, className }: DateRangePickerProps) {
  return (
    <div className={cn('flex items-center gap-2 rounded-md border border-app-border bg-app-surface px-3 py-2', className)}>
      <Calendar className="h-4 w-4 shrink-0 text-text-secondary" />
      <input
        type="date"
        value={startDate}
        onChange={(e) => onChange({ startDate: e.target.value, endDate })}
        className="bg-transparent text-sm text-text-primary focus:outline-none"
        aria-label="Başlangıç tarihi"
      />
      <span className="text-text-muted">–</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => onChange({ startDate, endDate: e.target.value })}
        className="bg-transparent text-sm text-text-primary focus:outline-none"
        aria-label="Bitiş tarihi"
      />
    </div>
  )
}
