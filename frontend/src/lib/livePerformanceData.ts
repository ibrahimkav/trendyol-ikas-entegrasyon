import apiClient from '../config/api'

export type HourlyProfit = { hour: string; net_profit: number }
export type TodayProduct = {
  productId: string
  variants: number
  productName: string
  productCostInclVat: number
  extraCost: number
}

export type LivePerformance = {
  net_profit_today: number
  revenue_today: number
  net_profit_to_cost_pct: number
  net_profit_to_revenue_pct: number
  hourly_profit: HourlyProfit[]
  products_today: TodayProduct[]
  isFallback: boolean
}

const VAT_RATE = 0.1 // backend/routers/financial.py VAT_RATE ile tutarlı

type PamLivePerformance = {
  net_profit: number
  revenue: number
  net_profit_to_cost_ratio: number
  net_profit_to_revenue_ratio: number
  hourly_profit_series: HourlyProfit[]
  todays_products: Array<{ product_id: string; product_name: string; quantity: number; revenue: number }>
}

/**
 * Canlı Performans veri katmanı. Pam'in gerçek endpoint'i: GET /api/dashboard/live-performance
 * (bkz. Pam'in inbox mesajı 2026-09-12T21-33-26 — ilk tahminim /financial/live-performance farklı
 * çıktı). Pam'in todays_products'ı henüz productCostInclVat/extraCost/variants içermiyor (Product
 * modelinde varyant/KDV-dahil-maliyet kavramı yok, Pam Wave2b'ye flag etti) — bu üçü burada aynı
 * %40+KDV tahminiyle (fallback'teki gibi) client-side türetiliyor, gerçek veri gelince Pam'in
 * şema genişletmesiyle değişecek. Hata/404 durumunda `/orders/`+`/financial/order-profitability`'den
 * client-side yaklaşık hesaba düşülür (isFallback:true).
 * NOT (w3-ratio-kpi-bug): net_profit_to_*_ratio backend'de ZATEN yüzde ölçeğinde — burada ×100
 * YAPILMAZ (önceki çifte çarpım 100 kat şişirme hatasına yol açıyordu).
 */
export async function fetchLivePerformance(): Promise<LivePerformance> {
  try {
    const res = await apiClient.get<PamLivePerformance>('/dashboard/live-performance')
    const d = res.data
    return {
      net_profit_today: d.net_profit,
      revenue_today: d.revenue,
      net_profit_to_cost_pct: round2(d.net_profit_to_cost_ratio),
      net_profit_to_revenue_pct: round2(d.net_profit_to_revenue_ratio),
      hourly_profit: d.hourly_profit_series,
      products_today: d.todays_products.map((p) => ({
        productId: p.product_id,
        variants: p.quantity,
        productName: p.product_name,
        productCostInclVat: round2(p.revenue * 0.4 * (1 + VAT_RATE)),
        extraCost: 0,
      })),
      isFallback: false,
    }
  } catch {
    return fetchLivePerformanceFallback()
  }
}

async function fetchLivePerformanceFallback(): Promise<LivePerformance> {
  const today = new Date().toISOString().slice(0, 10)

  const [profitRes, ordersRes] = await Promise.all([
    apiClient.get('/financial/order-profitability', { params: { limit: 500 } }),
    apiClient.get('/orders/', { params: { period: 'daily' } }),
  ])

  const profitOrders: Array<{ order_date: string; total_revenue: number; product_cost: number; net_profit: number }> =
    profitRes.data.orders ?? []
  const todayProfitOrders = profitOrders.filter((o) => o.order_date?.slice(0, 10) === today)

  const revenueToday = round2(todayProfitOrders.reduce((s, o) => s + o.total_revenue, 0))
  const productCostToday = round2(todayProfitOrders.reduce((s, o) => s + o.product_cost, 0))
  const netProfitToday = round2(todayProfitOrders.reduce((s, o) => s + o.net_profit, 0))

  // Saatlik kırılım için order-profitability'nin GÜVENİLİR "YYYY-MM-DD HH:MM" alanı kullanılıyor
  // (backend/routers/financial.py order_date.strftime formatı) — /orders/ ham listesinin tarih alan
  // adı garantili olmadığından oradan saatlik bucket'lamak toplamla tutarsız çıkabiliyordu.
  const netProfitByHour = new Map<number, number>()
  for (const o of todayProfitOrders) {
    const hour = Number(o.order_date.slice(11, 13))
    if (!Number.isNaN(hour)) netProfitByHour.set(hour, (netProfitByHour.get(hour) ?? 0) + o.net_profit)
  }
  const currentHour = new Date().getHours()
  const hourlyProfit: HourlyProfit[] = []
  for (let h = 0; h <= currentHour; h++) {
    hourlyProfit.push({ hour: `${String(h).padStart(2, '0')}:00`, net_profit: round2(netProfitByHour.get(h) ?? 0) })
  }

  const orders: any[] = ordersRes.data.orders ?? []
  const productMap = new Map<string, { name: string; qty: number; revenue: number }>()

  for (const order of orders) {
    const lines = order.items || order.lines || order.orderLines || []
    for (const line of Array.isArray(lines) ? lines : [lines]) {
      const productId = String(line.product_id || line.productId || line.barcode || 'unknown')
      const name = line.product_name || line.productName || line.name || `Ürün ${productId}`
      const qty = Number(line.quantity ?? 1)
      const priceRaw = line.price ?? line.salePrice ?? line.unitPrice ?? 0
      const price = typeof priceRaw === 'string' ? parseFloat(priceRaw.replace(',', '.')) : priceRaw
      const entry = productMap.get(productId) ?? { name, qty: 0, revenue: 0 }
      entry.qty += qty
      entry.revenue += (price || 0) * qty
      productMap.set(productId, entry)
    }
  }

  // Ürün maliyeti tahmini: backend'in order-profitability'de kullandığı %40 varsayımıyla tutarlı, + KDV.
  const productsToday: TodayProduct[] = Array.from(productMap.entries()).map(([productId, data]) => ({
    productId,
    variants: data.qty,
    productName: data.name,
    productCostInclVat: round2(data.revenue * 0.4 * (1 + VAT_RATE)),
    extraCost: 0,
  }))

  return {
    net_profit_today: netProfitToday,
    revenue_today: revenueToday,
    net_profit_to_cost_pct: productCostToday > 0 ? round2((netProfitToday / productCostToday) * 100) : 0,
    net_profit_to_revenue_pct: revenueToday > 0 ? round2((netProfitToday / revenueToday) * 100) : 0,
    hourly_profit: hourlyProfit,
    products_today: productsToday,
    isFallback: true,
  }
}

function round2(n: number) {
  return Math.round(n * 100) / 100
}
