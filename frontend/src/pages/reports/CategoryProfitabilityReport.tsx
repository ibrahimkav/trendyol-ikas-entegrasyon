import { useCallback, useEffect, useState } from 'react'
import apiClient from '../../config/api'
import { Badge, ProfitBadge, formatCurrency, type DataTableColumn } from '../../components/ui'
import ReportShell from './ReportShell'
import { defaultReportRange } from './reportUtils'

// Gerçek endpoint: GET /api/financial/reports/category-profitability (Pam, w2b-pam — store-scoped).
interface CategoryRow {
  category: string
  product_count: number
  quantity_sold: number
  revenue: number
  product_cost: number
  commission: number
  cargo_cost: number
  net_profit: number
  profit_margin_percent: number
  has_cost_data: boolean
}

const columns: DataTableColumn<CategoryRow>[] = [
  { key: 'category', header: 'Kategori', accessor: (r) => r.category || '—', sortValue: (r) => r.category },
  { key: 'product_count', header: 'Ürün Sayısı', align: 'right', accessor: (r) => r.product_count, sortValue: (r) => r.product_count },
  { key: 'quantity_sold', header: 'Satılan Adet', align: 'right', accessor: (r) => r.quantity_sold, sortValue: (r) => r.quantity_sold },
  { key: 'revenue', header: 'Ciro', align: 'right', accessor: (r) => formatCurrency(r.revenue), sortValue: (r) => r.revenue },
  { key: 'product_cost', header: 'Ürün Maliyeti', align: 'right', accessor: (r) => formatCurrency(r.product_cost), sortValue: (r) => r.product_cost },
  { key: 'commission', header: 'Komisyon', align: 'right', accessor: (r) => formatCurrency(r.commission), sortValue: (r) => r.commission },
  {
    key: 'net_profit',
    header: 'Net Kâr',
    align: 'right',
    accessor: (r) =>
      r.has_cost_data ? <ProfitBadge amount={r.net_profit} percent={r.profit_margin_percent} /> : <Badge tone="warning">Maliyet eksik</Badge>,
    sortValue: (r) => r.net_profit,
  },
]

export default function CategoryProfitabilityReport() {
  const [rows, setRows] = useState<CategoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState(defaultReportRange())

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/reports/category-profitability', {
        params: { start_date: dateRange.startDate, end_date: dateRange.endDate },
      })
      .then((res) => setRows(res.data?.categories ?? []))
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <ReportShell
      activeReport="/reports/category-profitability-analysis"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.category || 'uncategorized'}
      loading={loading}
      error={error}
      onRetry={fetchData}
      dateRange={dateRange}
      onDateChange={setDateRange}
    />
  )
}
