import { useCallback, useEffect, useState } from 'react'
import apiClient from '../../config/api'
import { Badge, ProfitBadge, formatCurrency, type DataTableColumn } from '../../components/ui'
import ReportShell from './ReportShell'
import { defaultReportRange } from './reportUtils'

// Gerçek endpoint: GET /api/financial/reports/order-profitability (Pam, w2b-pam — store-scoped,
// ?start_date=&end_date=&limit). Sunucu-taraflı tarih filtresi.
interface OrderRow {
  order_id: string
  order_number: string
  order_date: string
  customer_name: string
  status: string
  revenue: number
  product_cost: number
  commission: number
  cargo_cost: number
  gross_profit: number
  net_profit: number
  profit_margin_percent: number
  has_cost_data: boolean
}

const columns: DataTableColumn<OrderRow>[] = [
  { key: 'order_number', header: 'Sipariş No', accessor: (r) => r.order_number, sortValue: (r) => r.order_number },
  { key: 'order_date', header: 'Tarih', accessor: (r) => r.order_date, sortValue: (r) => r.order_date },
  { key: 'customer_name', header: 'Müşteri', accessor: (r) => r.customer_name || '—' },
  { key: 'revenue', header: 'Satış Fiyatı', align: 'right', accessor: (r) => formatCurrency(r.revenue), sortValue: (r) => r.revenue },
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

export default function OrderProfitabilityReport() {
  const [rows, setRows] = useState<OrderRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState(defaultReportRange())

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/reports/order-profitability', {
        params: { start_date: dateRange.startDate, end_date: dateRange.endDate, limit: 200 },
      })
      .then((res) => setRows(res.data?.orders ?? []))
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <ReportShell
      activeReport="/reports/order-profitability-analysis"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.order_id || r.order_number}
      loading={loading}
      error={error}
      onRetry={fetchData}
      dateRange={dateRange}
      onDateChange={setDateRange}
    />
  )
}
