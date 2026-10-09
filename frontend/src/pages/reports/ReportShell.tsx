import { useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import {
  PageHeader,
  Select,
  DateRangePicker,
  DataTable,
  Skeleton,
  ErrorBanner,
  type DataTableColumn,
} from '../../components/ui'

// Melontik'in Raporlar shell'i (melontik-screens.md §6): "Rapor Seçin" dropdown + tarih aralığı +
// DataTable (Filtrele/font A-/A+/fullscreen/pagination zaten DataTable içinde). 4 alt-rapor bu kabuğu
// paylaşır, sadece kolonlar/veri kaynağı değişir.

export const REPORT_OPTIONS = [
  { value: '/reports/order-profitability-analysis', label: 'Sipariş Kârlılık Analizi' },
  { value: '/reports/product-profitability-analysis', label: 'Ürün Kârlılık Analizi' },
  { value: '/reports/category-profitability-analysis', label: 'Kategori Kârlılık Analizi' },
  { value: '/reports/return-loss-analysis', label: 'İade Zarar Analizi' },
]

interface ReportShellProps<T> {
  /** Aktif raporun route path'i — "Rapor Seçin" dropdown'ında seçili görünür. */
  activeReport: string
  columns: DataTableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string
  loading: boolean
  error: string | null
  onRetry: () => void
  dateRange: { startDate: string; endDate: string }
  onDateChange: (range: { startDate: string; endDate: string }) => void
  /** true ise veri backend'den değil geçici mock'tan geliyor (endpoint henüz yok). */
  isFallback?: boolean
  filterSlot?: ReactNode
  emptyMessage?: string
}

export default function ReportShell<T>({
  activeReport,
  columns,
  rows,
  rowKey,
  loading,
  error,
  onRetry,
  dateRange,
  onDateChange,
  isFallback,
  filterSlot,
  emptyMessage = 'Bu tarih aralığında kayıt bulunamadı.',
}: ReportShellProps<T>) {
  const navigate = useNavigate()
  const activeLabel = useMemo(() => REPORT_OPTIONS.find((o) => o.value === activeReport)?.label ?? 'Raporlar', [activeReport])

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={activeLabel} breadcrumbs={[{ label: 'Raporlar' }, { label: activeLabel }]} />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
        <div className="w-64">
          <Select
            label="Rapor Seçin"
            options={REPORT_OPTIONS}
            value={activeReport}
            onChange={(e) => navigate(e.target.value)}
          />
        </div>
        <DateRangePicker startDate={dateRange.startDate} endDate={dateRange.endDate} onChange={onDateChange} />
      </div>

      {isFallback && !error && (
        <div className="flex items-center gap-2 rounded-lg border border-warning bg-warning-soft px-4 py-3 text-sm text-warning">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Bu rapor için backend endpoint'i henüz hazır değil — örnek (mock) veri gösteriliyor.
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={onRetry} />}

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} rowKey={rowKey} pageSize={50} filterSlot={filterSlot} emptyMessage={emptyMessage} />
      )}
    </div>
  )
}
