import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Package, AlertCircle, Loader2 } from 'lucide-react'
import apiClient from '../config/api'

interface LineItem {
  product_id?: string
  product_name?: string
  name?: string
  quantity: number
  price: number
}

interface OrderDetail {
  order_id: string
  order_number?: string
  order_date: string
  status: string
  total_amount: number
  cargo_tracking_number?: string
  items: LineItem[]
  customer?: {
    first_name?: string
    last_name?: string
    email?: string
    phone?: string
  }
}

export default function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const [data, setData] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!orderId) {
      setError('Sipariş numarası yok')
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await apiClient.get<OrderDetail>(`/orders/${encodeURIComponent(orderId)}`)
        if (!cancelled) setData(res.data)
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string }
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || 'Sipariş yüklenemedi')
          setData(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [orderId])

  return (
    <div className="space-y-6 animate-fade-in">
      <Link
        to="/orders"
        className="inline-flex items-center gap-2 text-sm font-medium text-trendyol-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Sipariş listesine dön
      </Link>

      {loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-600" role="status" aria-live="polite">
          <Loader2 className="h-6 w-6 animate-spin" />
          Yükleniyor…
        </div>
      )}

      {error && !loading && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-200/80 bg-red-50/90 p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {data && !loading && (
        <>
          <div className="page-header">
            <h1 className="page-title">Sipariş #{data.order_number ?? data.order_id}</h1>
            <p className="page-subtitle">
              {data.order_date} · {data.status}
            </p>
          </div>

          <div className="card overflow-hidden">
            <div className="dashboard-section-head">
              <h2 className="dashboard-section-title">Özet</h2>
            </div>
            <div className="dashboard-section-body space-y-2 text-sm text-slate-700">
              <p>
                <span className="font-medium text-slate-500">Tutar:</span>{' '}
                <span className="tabular-nums font-semibold text-slate-900">
                  {(Number(data.total_amount) || 0).toFixed(2)} ₺
                </span>
              </p>
              {data.cargo_tracking_number ? (
                <p>
                  <span className="font-medium text-slate-500">Kargo takip:</span>{' '}
                  {data.cargo_tracking_number}
                </p>
              ) : null}
            </div>
          </div>

          {data.customer && (data.customer.first_name || data.customer.phone || data.customer.email) && (
            <div className="card overflow-hidden">
              <div className="dashboard-section-head">
                <h2 className="dashboard-section-title">Müşteri</h2>
              </div>
              <div className="dashboard-section-body text-sm text-slate-700">
                <p>
                  {[data.customer.first_name, data.customer.last_name].filter(Boolean).join(' ') || '—'}
                </p>
                {data.customer.phone && <p>{data.customer.phone}</p>}
                {data.customer.email && <p className="text-slate-500">{data.customer.email}</p>}
              </div>
            </div>
          )}

          <div className="card overflow-hidden">
            <div className="dashboard-section-head">
              <h2 className="dashboard-section-title">Kalemler</h2>
            </div>
            <div className="dashboard-section-body space-y-2">
              {(data.items || []).map((line, i) => (
                <div key={i} className="dashboard-list-row items-start">
                  <Package className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-900">{line.product_name || line.name || 'Ürün'}</p>
                    <p className="text-xs text-slate-500">
                      {line.quantity} ad · {(Number(line.price) || 0).toFixed(2)} ₺
                    </p>
                  </div>
                </div>
              ))}
              {(!data.items || data.items.length === 0) && (
                <p className="text-sm text-slate-500">Kalem bilgisi yok.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
