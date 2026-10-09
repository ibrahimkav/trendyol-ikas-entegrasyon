import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Package, RefreshCw, AlertCircle, ExternalLink, Search } from 'lucide-react'
import apiClient from '../config/api'
import { filterOrdersBySearchAndStatus, uniqueOrderStatuses } from '../lib/orderListFilters'

interface OrderRow {
  order_id: string
  order_date: string
  status: string
  total_amount: number
  items?: unknown[]
}

export default function OrdersList() {
  const [period, setPeriod] = useState('7days')
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<{ orders: OrderRow[]; total: number; error?: string }>(`/orders/`, {
        params: { period },
      })
      if (res.data.error) {
        setError(res.data.error)
        setOrders([])
        setTotal(0)
        return
      }
      setOrders(res.data.orders || [])
      setTotal(res.data.total ?? (res.data.orders?.length ?? 0))
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setError(err.response?.data?.detail || err.message || 'Siparişler yüklenemedi')
      setOrders([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [period])

  const statusOptions = useMemo(() => uniqueOrderStatuses(orders), [orders])
  const filteredOrders = useMemo(
    () => filterOrdersBySearchAndStatus(orders, searchQuery, statusFilter),
    [orders, searchQuery, statusFilter]
  )

  const lineCount = (o: OrderRow) => (Array.isArray(o.items) ? o.items.length : 0)

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Siparişler</h1>
          <p className="page-subtitle">
            Trendyol sipariş listeniz; dönem seçerek filtreleyebilirsiniz. Detay için satıra tıklayın.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="min-w-[9.5rem] rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-trendyol-primary/30"
          >
            <option value="all">Tüm zamanlar</option>
            <option value="7days">Son 7 gün</option>
            <option value="15days">Son 15 gün</option>
            <option value="30days">Son 30 gün</option>
            <option value="1month">Son 1 ay</option>
          </select>
          <button type="button" onClick={load} disabled={loading} className="btn-primary disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-200/80 bg-red-50/90 p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {!error && orders.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Sipariş no ara…"
              className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-trendyol-primary/30"
              aria-label="Sipariş numarasına göre ara"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="min-w-[10rem] rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-trendyol-primary/30"
            aria-label="Durum filtresi"
          >
            <option value="all">Tüm durumlar</option>
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="dashboard-section-head">
          <h2 className="dashboard-section-title">Liste</h2>
          <span className="text-sm text-slate-500">
            {loading
              ? 'Yükleniyor…'
              : searchQuery.trim() || statusFilter !== 'all'
                ? `${filteredOrders.length} gösteriliyor · ${total} toplam`
                : `${total} kayıt`}
          </span>
        </div>
        <div className="dashboard-section-body space-y-2">
          {!loading && orders.length === 0 && !error && (
            <p className="py-8 text-center text-sm text-slate-500">Bu dönemde sipariş bulunamadı.</p>
          )}
          {!loading && orders.length > 0 && filteredOrders.length === 0 && (
            <p className="py-8 text-center text-sm text-slate-500">Filtreye uygun sipariş yok.</p>
          )}
          {filteredOrders.map((o) => (
            <Link
              key={String(o.order_id)}
              to={`/orders/${encodeURIComponent(String(o.order_id))}`}
              className="dashboard-list-row gap-3"
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <Package className="h-5 w-5 shrink-0 text-slate-400" />
                <div className="min-w-0">
                  <p className="font-semibold text-slate-900">#{o.order_id}</p>
                  <p className="text-xs text-slate-500">
                    {o.order_date
                      ? (() => {
                          try {
                            return new Date(o.order_date).toLocaleString('tr-TR')
                          } catch {
                            return o.order_date
                          }
                        })()
                      : '—'}{' '}
                    · {lineCount(o)} kalem
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-right">
                <span className="font-semibold tabular-nums text-slate-900">
                  {typeof o.total_amount === 'number' ? `${o.total_amount.toFixed(2)} ₺` : '—'}
                </span>
                <span className="max-w-[10rem] truncate rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                  {o.status}
                </span>
              </div>
              <ExternalLink className="hidden h-4 w-4 shrink-0 text-slate-400 sm:block" aria-hidden />
            </Link>
          ))}
        </div>
      </div>

      <p className="text-center text-xs text-slate-500">
        Barkod için{' '}
        <Link to="/auto-barcode" className="font-medium text-trendyol-primary hover:underline">
          Barkod
        </Link>{' '}
        veya{' '}
        <Link to="/order-scanner" className="font-medium text-trendyol-primary hover:underline">
          Okut
        </Link>{' '}
        sayfasını kullanın.
      </p>
    </div>
  )
}
