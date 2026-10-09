import { useCallback, useEffect, useState } from 'react'
import apiClient from '../../config/api'
import { formatCurrency, type DataTableColumn } from '../../components/ui'
import ReportShell from './ReportShell'
import { defaultReportRange } from './reportUtils'

// Gerçek endpoint: GET /api/financial/reports/return-loss (Pam, w2b-pam — return_refunds tablosundan,
// store-scoped). Şekil sebep-bazlı: {total_returns, total_refund_amount, by_reason:[{reason,count,refund_amount}]}.
interface ReasonRow {
  reason: string
  count: number
  refund_amount: number
}

const columns: DataTableColumn<ReasonRow>[] = [
  { key: 'reason', header: 'İade Sebebi', accessor: (r) => r.reason || 'Belirtilmemiş', sortValue: (r) => r.reason },
  { key: 'count', header: 'İade Adedi', align: 'right', accessor: (r) => r.count, sortValue: (r) => r.count },
  {
    key: 'refund_amount',
    header: 'İade Tutarı',
    align: 'right',
    accessor: (r) => <span className="font-medium text-danger">{formatCurrency(r.refund_amount)}</span>,
    sortValue: (r) => r.refund_amount,
  },
]

export default function ReturnLossReport() {
  const [rows, setRows] = useState<ReasonRow[]>([])
  const [totals, setTotals] = useState<{ total_returns: number; total_refund_amount: number }>({ total_returns: 0, total_refund_amount: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState(defaultReportRange())

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/reports/return-loss', {
        params: { start_date: dateRange.startDate, end_date: dateRange.endDate },
      })
      .then((res) => {
        setRows(res.data?.by_reason ?? [])
        setTotals({
          total_returns: res.data?.total_returns ?? 0,
          total_refund_amount: res.data?.total_refund_amount ?? 0,
        })
      })
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <ReportShell
      activeReport="/reports/return-loss-analysis"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.reason || 'unknown'}
      loading={loading}
      error={error}
      onRetry={fetchData}
      dateRange={dateRange}
      onDateChange={setDateRange}
      emptyMessage="Bu dönemde iade kaydı bulunamadı."
      filterSlot={
        <span className="text-sm text-text-secondary">
          Toplam İade: <strong className="text-text-primary">{totals.total_returns}</strong> · Toplam İade Tutarı:{' '}
          <strong className="text-danger">{formatCurrency(totals.total_refund_amount)}</strong>
        </span>
      }
    />
  )
}
