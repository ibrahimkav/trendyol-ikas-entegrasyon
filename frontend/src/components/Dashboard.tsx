import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Download, Info } from 'lucide-react'
import {
  Button,
  ChartContainer,
  DateRangePicker,
  DonutChart,
  DonutLegend,
  KpiCard,
  LineChart,
  PageHeader,
  Sparkline,
} from './ui'
import { fetchDashboardSummary, type DashboardSummary } from '../lib/dashboardData'
import { fetchProductSettings } from '../lib/productSettingsApi'
import { formatCurrencyTRY, formatPercent } from '../lib/format'

const CHART_COLORS = ['#FF6B4A', '#16A34A', '#F59E0B', '#2563EB', '#7A2E1E', '#06B6D4', '#A855F7']
const MAX_RANGE_DAYS = 90

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10)
}

function defaultRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 6)
  return { from: isoDate(from), to: isoDate(to) }
}

function daysBetween(from: string, to: string) {
  return Math.round((new Date(to).getTime() - new Date(from).getTime()) / 86_400_000) + 1
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams()
  const initial = defaultRange()
  const from = params.get('from') || initial.from
  const to = params.get('to') || initial.to

  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [rangeError, setRangeError] = useState<string | null>(null)
  // Onboarding boşluğu (w3-clarity, Phyllis gap-research-ux.md §4.1): kaç ürünün maliyeti eksik —
  // tarih aralığından bağımsız, ürün-geneli bir bilgi olduğu için bir kez çekiliyor. Başarısız olursa
  // banner sayı olmadan da gösterilir (zorlamıyoruz).
  const [missingCostCount, setMissingCostCount] = useState<number | null>(null)

  const load = useCallback(async (f: string, t: string) => {
    setError(false)
    setLoading((prev) => prev || !data)
    try {
      const res = await fetchDashboardSummary(f, t)
      setData(res)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load(from, to)
  }, [from, to, load])

  useEffect(() => {
    fetchProductSettings()
      .then(({ products }) => {
        setMissingCostCount(products.filter((p) => !p.default_cost || p.default_cost <= 0).length)
      })
      .catch(() => setMissingCostCount(null))
  }, [])

  function handleRangeChange(range: { startDate: string; endDate: string }) {
    if (daysBetween(range.startDate, range.endDate) > MAX_RANGE_DAYS) {
      setRangeError(`En fazla ${MAX_RANGE_DAYS} günlük aralık seçebilirsiniz.`)
      return
    }
    setRangeError(null)
    setParams({ from: range.startDate, to: range.endDate })
  }

  // PDF dışa aktarma backend endpoint'i henüz yok (Wave2c) — buton her tıklamada hata toast'ı
  // vermek yerine devre dışı + 'yakında' tooltip ile gösteriliyor (Phyllis w2b-qa notu §A).
  const sparklineData = useMemo(() => data?.daily_net_profit.map((d) => d.net_profit) ?? [], [data])
  const trendData = useMemo(
    () =>
      (data?.daily_net_profit ?? []).map((d) => ({
        label: new Date(d.date).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' }),
        value: d.net_profit,
      })),
    [data],
  )
  const totalCost = useMemo(() => (data ? data.cost_breakdown.reduce((s, c) => s + c.amount, 0) : 0), [data])
  const isEmpty = Boolean(data && data.total_revenue === 0 && totalCost === 0)
  // "Ciro var ama maliyet verisi yok/eksik" hali: isEmpty'den AYRI ve daha sık karşılaşılan bir durum
  // (Trendyol senkronu ciroyu hemen çeker, maliyet girişi her zaman manuel/gecikmeli) — mevcut isEmpty'yi
  // bozmadan, ek bir banner olarak gösteriliyor (Phyllis gap-research-ux.md §4.1).
  const noCostDataRevenue = useMemo(() => (data ? Math.max(0, data.total_revenue - data.cost_bearing_revenue) : 0), [data])
  // w3-cost-entry-followups #8 (hive/docs/cost-entry-ux-review.md) — ÖLÇÜLDÜ: eski koşul
  // `total_revenue > 0` şartına bağlıydı, yani henüz hiç ciro senkronu olmamış (ama ürünleri zaten
  // senkron olmuş, maliyeti eksik) bir mağazada banner HİÇ tetiklenmiyordu — tek giriş noktası
  // sidebar'daki linke kalıyordu. missingCostCount total_revenue'dan bağımsız ayrı çekiliyor,
  // o yüzden ciro sıfırken de eksik-maliyet CTA'sını tetikleyebiliyoruz.
  const hasMissingCost = (missingCostCount ?? 0) > 0
  const showCostGapBanner = Boolean(data && ((data.total_revenue > 0 && noCostDataRevenue > 0.01) || hasMissingCost))

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        actions={
          <Button variant="secondary" leftIcon={<Download className="h-4 w-4" />} disabled title="PDF dışa aktarma yakında eklenecek">
            PDF olarak indir
          </Button>
        }
      />

      <div className="flex flex-col gap-1">
        <DateRangePicker startDate={from} endDate={to} onChange={handleRangeChange} className="w-fit" />
        {rangeError && <p className="text-xs text-danger">{rangeError}</p>}
      </div>

      {error && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          <span>Veriler yüklenemedi. Lütfen tekrar deneyin.</span>
          <Button variant="danger" size="sm" onClick={() => load(from, to)}>
            Tekrar Dene
          </Button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-lg border border-app-border bg-app-surface-muted" />
          ))}
        </div>
      ) : (
        data && (
          <>
            {showCostGapBanner && (
              <div className="flex flex-col gap-2 rounded-lg border border-info/30 bg-info-soft px-4 py-3 text-sm text-info sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-2">
                  <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <span>
                    {data.total_revenue <= 0
                      ? 'Ürünleriniz senkronlandı ama henüz hiçbirine maliyet girilmemiş — kâr hesapları çalışabilmesi için Ürün Ayarları\'ndan maliyet girin.'
                      : data.cost_bearing_revenue <= 0
                        ? 'Toplam Ciro güncel ama henüz hiçbir ürüne maliyet girilmemiş — bu yüzden Net Kâr ve oran KPI\'ları ₺0,00 / %0 görünüyor.'
                        : `Bazı ürünlerde maliyet eksik — ${formatCurrencyTRY(noCostDataRevenue)} tutarındaki ciro henüz kâr hesaplarına dahil edilmiyor, bu yüzden rakamlar olduğundan düşük görünebilir.`}
                    {missingCostCount !== null && missingCostCount > 0 && ` (${missingCostCount} ürünün maliyeti eksik.)`}
                  </span>
                </div>
                <Link
                  to="/product-settings"
                  className="flex-shrink-0 whitespace-nowrap text-sm font-medium text-info underline hover:no-underline"
                >
                  Ürün Ayarları'ndan maliyet gir →
                </Link>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <KpiCard label="Toplam Ciro" value={formatCurrencyTRY(data.total_revenue)} sparkline={<Sparkline data={sparklineData} />} />
              <KpiCard
                label="Maliyeti Olan Ciro"
                value={formatCurrencyTRY(data.cost_bearing_revenue)}
                sparkline={<Sparkline data={sparklineData} />}
              />
              <KpiCard label="Brüt Kâr Tutarı" value={formatCurrencyTRY(data.gross_profit)} sparkline={<Sparkline data={sparklineData} />} />
              <KpiCard label="Net Kâr" value={formatCurrencyTRY(data.net_profit)} sparkline={<Sparkline data={sparklineData} />} />
              <KpiCard
                label="Net Kâr / Satış Fiyatı Oranı"
                value={formatPercent(data.net_profit_to_revenue_pct)}
                tooltip="Net Kâr ÷ Maliyeti Olan Ciro × 100 — yukarıdaki 'Maliyeti Olan Ciro' kartıyla aynı payda, Toplam Ciro değil (sadece maliyeti girilen ürünlerin cirosu)."
                sparkline={<Sparkline data={sparklineData} />}
              />
              <KpiCard
                label="Net Kâr / Ürün Maliyeti Oranı"
                value={formatPercent(data.net_profit_to_cost_pct)}
                tooltip="Net Kâr ÷ Ürün Maliyeti × 100 (Masraf Kalemleri'ndeki 'Ürün Maliyeti' kalemi)."
                sparkline={<Sparkline data={sparklineData} />}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ChartContainer title="Masraf Kalemleri (₺)">
                {isEmpty ? (
                  <p className="py-10 text-center text-sm text-text-muted">Bu tarih aralığında maliyet verisi bulunamadı.</p>
                ) : (
                  <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
                    <DonutChart
                      segments={data.cost_breakdown.map((c, i) => ({ label: c.label, value: c.amount, color: CHART_COLORS[i % CHART_COLORS.length] }))}
                      centerLabel="Toplam Maliyet"
                      centerValue={formatCurrencyTRY(totalCost)}
                    />
                    <div className="w-full flex-1">
                      <DonutLegend
                        segments={data.cost_breakdown.map((c, i) => ({ label: c.label, value: c.amount, color: CHART_COLORS[i % CHART_COLORS.length] }))}
                        formatValue={formatCurrencyTRY}
                      />
                      {data.isFallback && (
                        <p className="mt-3 text-xs text-text-muted">
                          Not: backend henüz melontik'in tam 11 kalemli kırılımını (Hizmet Bedeli, Stopaj, Ceza vb.) desteklemiyor —
                          şimdilik izlenen 4 kalem gösteriliyor.
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </ChartContainer>

              <ChartContainer title="Kâr Performansı">
                {isEmpty ? (
                  <p className="py-10 text-center text-sm text-text-muted">Bu tarih aralığında maliyet verisi bulunamadı.</p>
                ) : (
                  <LineChart data={trendData} formatValue={formatCurrencyTRY} />
                )}
              </ChartContainer>
            </div>
          </>
        )
      )}
    </div>
  )
}
