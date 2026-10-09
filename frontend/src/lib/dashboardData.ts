import apiClient from '../config/api'

export type CostSegment = { label: string; amount: number }
export type DailyProfit = { date: string; net_profit: number }

export type DashboardSummary = {
  total_revenue: number
  cost_bearing_revenue: number
  gross_profit: number
  net_profit: number
  net_profit_to_revenue_pct: number
  net_profit_to_cost_pct: number
  cost_breakdown: CostSegment[]
  daily_net_profit: DailyProfit[]
  /** true ise gerçek Pam endpoint'i henüz yok, order-profitability'den client-side türetildi (bkz. not). */
  isFallback: boolean
}

type PamDashboardSummary = {
  kpis: {
    total_revenue: number
    cost_bearing_revenue: number
    gross_profit: number
    net_profit: number
    net_profit_to_revenue_ratio: number
    net_profit_to_cost_ratio: number
  }
  expense_breakdown: Array<{ category: string; amount: number }>
  profit_performance: DailyProfit[]
}

/**
 * Dashboard + Canlı Performans'ın ortak veri katmanı.
 *
 * Pam'in gerçek endpoint'i: GET /api/dashboard/summary?start_date&end_date (bkz. Pam'in inbox
 * mesajı 2026-09-12T21-33-26 — ilk tahminim /financial/dashboard-summary?from&to farklı çıktı,
 * burada onun gerçek şekline eşleniyor: kpis.*_ratio backend'de (utils/profitability.py) ZATEN
 * yüzde ölçeğinde (ör. 22.85 = %22,85, isim yanıltıcı ama 0-1 değil) — burada ×100 YAPILMAZ
 * (w3-ratio-kpi-bug: önceki ×100 çifte çarpım hatasıydı, 100 kat şişiriyordu);
 * expense_breakdown[{category,amount}] → cost_breakdown[{label,amount}]; profit_performance
 * aynı {date,net_profit} şekli). Hata/404 durumunda (backend geçici erişilemezse)
 * `/financial/order-profitability`'den client-side yaklaşık hesaba düşülür (isFallback:true).
 */
export async function fetchDashboardSummary(from: string, to: string): Promise<DashboardSummary> {
  try {
    const res = await apiClient.get<PamDashboardSummary>('/dashboard/summary', {
      params: { start_date: from, end_date: to },
    })
    const { kpis, expense_breakdown, profit_performance } = res.data
    return {
      total_revenue: kpis.total_revenue,
      cost_bearing_revenue: kpis.cost_bearing_revenue,
      gross_profit: kpis.gross_profit,
      net_profit: kpis.net_profit,
      net_profit_to_revenue_pct: round2(kpis.net_profit_to_revenue_ratio),
      net_profit_to_cost_pct: round2(kpis.net_profit_to_cost_ratio),
      cost_breakdown: expense_breakdown.map((e) => ({ label: e.category, amount: e.amount })),
      daily_net_profit: profit_performance,
      isFallback: false,
    }
  } catch {
    return fetchDashboardSummaryFallback(from, to)
  }
}

async function fetchDashboardSummaryFallback(from: string, to: string): Promise<DashboardSummary> {
  const res = await apiClient.get('/financial/order-profitability', { params: { limit: 500 } })
  const orders: Array<{
    order_date: string
    total_revenue: number
    vat: number
    commission: number
    cargo_cost: number
    product_cost: number
    net_profit: number
  }> = res.data.orders ?? []

  const inRange = orders.filter((o) => {
    const day = o.order_date?.slice(0, 10)
    return day && day >= from && day <= to
  })

  const sum = (fn: (o: (typeof inRange)[number]) => number) => inRange.reduce((acc, o) => acc + fn(o), 0)

  const totalRevenue = sum((o) => o.total_revenue)
  const totalProductCost = sum((o) => o.product_cost)
  const totalCommission = sum((o) => o.commission)
  const totalCargo = sum((o) => o.cargo_cost)
  const totalVat = sum((o) => o.vat)
  const netProfit = sum((o) => o.net_profit)
  // Brüt Kâr = Ciro − (Ürün Maliyeti + Komisyon + Kargo) = Net Kâr + KDV (Jim'in formülüyle tutarlı)
  const grossProfit = netProfit + totalVat

  const dailyMap = new Map<string, number>()
  for (const o of inRange) {
    const day = o.order_date.slice(0, 10)
    dailyMap.set(day, (dailyMap.get(day) ?? 0) + o.net_profit)
  }
  const dailyNetProfit = Array.from(dailyMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, net_profit]) => ({ date, net_profit }))

  return {
    total_revenue: round2(totalRevenue),
    // Backend henüz "maliyeti girilmiş ürün" ayrımını yapmıyor (Jim'in notu) — fallback'te toplam ciroyla aynı.
    cost_bearing_revenue: round2(totalRevenue),
    gross_profit: round2(grossProfit),
    net_profit: round2(netProfit),
    net_profit_to_revenue_pct: totalRevenue > 0 ? round2((netProfit / totalRevenue) * 100) : 0,
    net_profit_to_cost_pct: totalProductCost > 0 ? round2((netProfit / totalProductCost) * 100) : 0,
    cost_breakdown: [
      { label: 'Ürün Maliyeti', amount: round2(totalProductCost) },
      { label: 'Komisyon', amount: round2(totalCommission) },
      { label: 'Kargo Ücreti', amount: round2(totalCargo) },
      { label: 'Net KDV', amount: round2(totalVat) },
    ],
    daily_net_profit: dailyNetProfit,
    isFallback: true,
  }
}

function round2(n: number) {
  return Math.round(n * 100) / 100
}
