import { useCallback, useEffect, useState } from 'react'
import apiClient from '../../config/api'
import { Badge, ProfitBadge, formatCurrency, type DataTableColumn } from '../../components/ui'
import ReportShell from './ReportShell'
import { defaultReportRange } from './reportUtils'

// Gerçek endpoint: GET /api/financial/reports/product-profitability (Pam, w2b-pam — store-scoped,
// ?start_date=&end_date=&sort_by; ürün şekli Kâr Marjı Listesi'yle aynı).
interface ProductRow {
  product_id: string
  product_name: string
  category: string | null
  quantity_sold: number
  revenue: number
  product_cost: number
  commission: number
  cargo_cost: number
  net_profit: number
  profit_margin_percent: number
  has_cost_data: boolean
}

const columns: DataTableColumn<ProductRow>[] = [
  {
    key: 'product_name',
    header: 'Ürün',
    accessor: (r) => (
      <div>
        <p className="font-medium text-text-primary">{r.product_name}</p>
        <p className="text-xs text-text-muted">{r.category || '—'}</p>
      </div>
    ),
    sortValue: (r) => r.product_name,
  },
  { key: 'quantity_sold', header: 'Satılan Adet', align: 'right', accessor: (r) => r.quantity_sold, sortValue: (r) => r.quantity_sold },
  { key: 'revenue', header: 'Ciro', align: 'right', accessor: (r) => formatCurrency(r.revenue), sortValue: (r) => r.revenue },
  { key: 'product_cost', header: 'Ürün Maliyeti', align: 'right', accessor: (r) => formatCurrency(r.product_cost), sortValue: (r) => r.product_cost },
  { key: 'commission', header: 'Komisyon', align: 'right', accessor: (r) => formatCurrency(r.commission), sortValue: (r) => r.commission },
  { key: 'cargo_cost', header: 'Kargo', align: 'right', accessor: (r) => formatCurrency(r.cargo_cost), sortValue: (r) => r.cargo_cost },
  {
    key: 'net_profit',
    header: 'Net Kâr',
    align: 'right',
    accessor: (r) =>
      r.has_cost_data ? <ProfitBadge amount={r.net_profit} percent={r.profit_margin_percent} /> : <Badge tone="warning">Maliyet eksik</Badge>,
    sortValue: (r) => r.net_profit,
  },
]

export default function ProductProfitabilityReport() {
  const [rows, setRows] = useState<ProductRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState(defaultReportRange())

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/reports/product-profitability', {
        params: { start_date: dateRange.startDate, end_date: dateRange.endDate, sort_by: 'net_profit' },
      })
      .then((res) => setRows(res.data?.products ?? []))
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <ReportShell
      activeReport="/reports/product-profitability-analysis"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.product_id}
      loading={loading}
      error={error}
      onRetry={fetchData}
      dateRange={dateRange}
      onDateChange={setDateRange}
    />
  )
}
