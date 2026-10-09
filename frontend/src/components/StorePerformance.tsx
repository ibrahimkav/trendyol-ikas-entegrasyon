import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button, ChartContainer, ColoredKpiCard, DataTable, Input, LineChart, PageHeader, type DataTableColumn } from './ui'
import { fetchLivePerformance, type LivePerformance, type TodayProduct } from '../lib/livePerformanceData'
import { formatCurrencyTRY, formatPercent } from '../lib/format'

/** Canlı Performans `/live-performance` — davranış: hive/agents/phyllis-mttzizd9/w2a-interaction-spec.md §5. */
export default function StorePerformance() {
  const [data, setData] = useState<LivePerformance | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  // Ekstra Gider satır-içi düzenleme: backend'de bu alan için endpoint yok, sadece client-side state
  // (spec §5 "auto-save" davranışını taklit eder ama sayfa yenilenince sıfırlanır — TODO Wave2b).
  const [extraCostOverrides, setExtraCostOverrides] = useState<Record<string, number>>({})

  const load = useCallback(async (isRefresh: boolean) => {
    setError(false)
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    try {
      const res = await fetchLivePerformance()
      setData(res)
      setLastUpdated(new Date())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load(false)
  }, [load])

  const trendData = useMemo(
    () => (data?.hourly_profit ?? []).map((h) => ({ label: h.hour, value: h.net_profit })),
    [data],
  )

  const products: TodayProduct[] = useMemo(
    () => (data?.products_today ?? []).map((p) => ({ ...p, extraCost: extraCostOverrides[p.productId] ?? p.extraCost })),
    [data, extraCostOverrides],
  )

  const columns: DataTableColumn<TodayProduct>[] = [
    { key: 'variants', header: 'Varyantlar', accessor: (r) => r.variants, align: 'center', sortValue: (r) => r.variants },
    { key: 'product', header: 'Ürün Bilgisi', accessor: (r) => r.productName, sortValue: (r) => r.productName },
    {
      key: 'cost',
      header: 'Ürün Maliyeti (KDV Dahil)',
      accessor: (r) => formatCurrencyTRY(r.productCostInclVat),
      align: 'right',
      sortValue: (r) => r.productCostInclVat,
    },
    { key: 'stock', header: 'Stok (Adet)', accessor: () => '—', align: 'center' },
    { key: 'return-rate', header: 'İade Oranı', accessor: () => '—', align: 'center' },
    { key: 'delivery-type', header: 'Teslimat Tipi', accessor: () => '—', align: 'center' },
    {
      key: 'extra-cost',
      header: 'Ekstra Gider',
      align: 'right',
      accessor: (r) => (
        <Input
          type="number"
          defaultValue={r.extraCost}
          className="h-8 w-24 text-right"
          onBlur={(e) => {
            const value = Number(e.target.value) || 0
            setExtraCostOverrides((prev) => ({ ...prev, [r.productId]: value }))
          }}
        />
      ),
    },
  ]

  const isEmptyToday = Boolean(data && data.revenue_today === 0 && products.length === 0)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Canlı Performans"
        actions={
          <Button variant="outline" leftIcon={<RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />} onClick={() => load(true)} disabled={refreshing}>
            {refreshing ? 'Güncelleniyor…' : 'Verileri Güncelle'}
          </Button>
        }
      />

      {error && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          <span>Veriler yüklenemedi. Lütfen tekrar deneyin.</span>
          <Button variant="danger" size="sm" onClick={() => load(false)}>
            Tekrar Dene
          </Button>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-6">
          <div className="h-20 w-64 animate-pulse rounded-lg bg-app-surface-muted" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-app-surface-muted" />
            ))}
          </div>
        </div>
      ) : (
        data && (
          <>
            <div>
              <p className="text-caption uppercase tracking-wide text-text-secondary">Bugünkü Net Kârım 💵</p>
              <p className="text-3xl font-bold tabular-nums text-text-primary">{formatCurrencyTRY(data.net_profit_today)}</p>
              {lastUpdated && (
                <p className="mt-1 text-xs text-text-muted">Son güncelleme: {lastUpdated.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</p>
              )}
            </div>

            <ChartContainer title="Kâr Performansı">
              {isEmptyToday ? (
                <p className="py-10 text-center text-sm text-text-muted">Bugün henüz sipariş alınmadı.</p>
              ) : (
                <>
                  <LineChart data={trendData} formatValue={formatCurrencyTRY} />
                  {data.isFallback && (
                    <p className="mt-2 text-xs text-text-muted">
                      Not: gerçek zamanlı canlı-performans endpoint'i henüz yok, saatlik kırılım mevcut sipariş verisinden yaklaşık türetildi
                      (Wave2b'de Pam'in endpoint'iyle değişecek).
                    </p>
                  )}
                </>
              )}
            </ChartContainer>

            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <ColoredKpiCard label="Kâr Tutarı" value={formatCurrencyTRY(data.net_profit_today)} tone="success" tooltip="Kâr Tutarı = Net Satış − Toplam Maliyet" />
              <ColoredKpiCard
                label="Kâr / Ürün Maliyet Oranı"
                value={formatPercent(data.net_profit_to_cost_pct)}
                tone="info"
                tooltip="Kâr Tutarı ÷ Ürün Maliyeti × 100"
              />
              <ColoredKpiCard
                label="Kâr / Satış Fiyat Oranı"
                value={formatPercent(data.net_profit_to_revenue_pct)}
                tone="warning"
                tooltip="Kâr Tutarı ÷ Maliyeti Olan Ciro × 100 — sağdaki 'Ciro' kartıyla AYNI sayı değil, sadece maliyeti girilen ürünlerin cirosu kullanılır (w3-clarity: eski tooltip yanlışlıkla '÷ Ciro' diyordu)."
              />
              <ColoredKpiCard label="Ciro" value={formatCurrencyTRY(data.revenue_today)} tone="neutral" tooltip="Bugünkü toplam sipariş geliri" />
            </div>

            {isEmptyToday ? (
              <div className="rounded-lg border border-app-border bg-app-surface p-10 text-center text-sm text-text-muted shadow-card">
                Bugün henüz sipariş alınmadı.
              </div>
            ) : (
              <div>
                <h2 className="mb-3 text-base font-semibold text-text-primary">Bugün Sipariş Alan Ürünler</h2>
                <DataTable columns={columns} data={products} rowKey={(r) => r.productId} />
              </div>
            )}
          </>
        )
      )}
    </div>
  )
}
