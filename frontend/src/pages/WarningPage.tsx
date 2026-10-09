import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, TrendingDown, Tag, Layers, ChevronRight, Settings } from 'lucide-react'
import apiClient from '../config/api'
import {
  PageHeader,
  Badge,
  SegmentedControl,
  Skeleton,
  ErrorBanner,
  formatCurrency,
  formatPercent,
  cn,
} from '../components/ui'

// Uyarı Sayfası (melontik /warning-page) — 4 uyarı tipi (Jim melontik-page-spec.md §Uyarı Sayfası):
//   1) min_margin  — minimum kâr marjı altına düşme
//   2) loss_sale   — zararına satış
//   3) bad_campaign — hatalı kampanya kurulumu
//   4) overlap_discount — çakışan indirim
// (1) ve (2) gerçek profit-margin-list verisinden TÜRETİLİYOR. (3)/(4) için backend sinyali henüz yok
// (kampanya kâr-etkisi w2b-jim/w2b-pam'da) → örnek (mock) kayıtlarla gösteriliyor, isFallback rozetli.
type WarningType = 'min_margin' | 'loss_sale' | 'bad_campaign' | 'overlap_discount'

interface WarningItem {
  id: string
  type: WarningType
  title: string
  detail: string
  linkTo?: string
  linkLabel?: string
  isMock?: boolean
}

const MIN_MARGIN_THRESHOLD = 10 // % — bu değerin altı "min kâr marjı altı" uyarısı

const typeMeta: Record<WarningType, { label: string; icon: typeof AlertTriangle; tone: 'danger' | 'warning' | 'info' }> = {
  loss_sale: { label: 'Zararına Satış', icon: TrendingDown, tone: 'danger' },
  min_margin: { label: 'Min. Kâr Marjı Altı', icon: AlertTriangle, tone: 'warning' },
  bad_campaign: { label: 'Hatalı Kampanya', icon: Tag, tone: 'warning' },
  overlap_discount: { label: 'Çakışan İndirim', icon: Layers, tone: 'info' },
}

const MOCK_CAMPAIGN_WARNINGS: WarningItem[] = [
  {
    id: 'mock-camp-1',
    type: 'bad_campaign',
    title: 'Kampanya kâr marjını negatife düşürüyor',
    detail: '"Yaz İndirimi" kampanyası 3 üründe komisyon+indirim sonrası zarar oluşturuyor.',
    linkTo: '/campaign/build-your-campaign',
    linkLabel: 'Kampanyayı incele',
    isMock: true,
  },
  {
    id: 'mock-disc-1',
    type: 'overlap_discount',
    title: 'Çakışan indirim tespit edildi',
    detail: '2 üründe hem sepet kampanyası hem ürün indirimi aynı anda aktif — toplam indirim beklenenden yüksek.',
    linkTo: '/campaign/basket-campaigns',
    linkLabel: 'Sepet kampanyaları',
    isMock: true,
  },
]

const filterOptions: { value: 'all' | WarningType; label: string }[] = [
  { value: 'all', label: 'Tümü' },
  { value: 'loss_sale', label: 'Zararına Satış' },
  { value: 'min_margin', label: 'Min. Marj' },
  { value: 'bad_campaign', label: 'Kampanya' },
  { value: 'overlap_discount', label: 'İndirim' },
]

export default function WarningPage() {
  const [items, setItems] = useState<WarningItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMock, setHasMock] = useState(false)
  const [filter, setFilter] = useState<'all' | WarningType>('all')

  const fetchWarnings = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/profit-margin-list', { params: { profit_filter: 'all' } })
      .then((res) => {
        const products: any[] = res.data?.products ?? []
        const derived: WarningItem[] = []
        for (const p of products) {
          if (!p.has_cost_data) continue
          if (p.net_profit < 0) {
            derived.push({
              id: `loss-${p.product_id}`,
              type: 'loss_sale',
              title: `${p.product_name} zararına satılıyor`,
              detail: `Net kâr ${formatCurrency(p.net_profit)} (${formatPercent(p.profit_margin_percent)}). Fiyat veya maliyet gözden geçirilmeli.`,
              linkTo: `/product-pricing?productId=${encodeURIComponent(p.product_id)}&name=${encodeURIComponent(p.product_name)}`,
              linkLabel: 'Fiyatlandır',
            })
          } else if (p.profit_margin_percent < MIN_MARGIN_THRESHOLD) {
            derived.push({
              id: `margin-${p.product_id}`,
              type: 'min_margin',
              title: `${p.product_name} düşük kâr marjında`,
              detail: `Kâr marjı ${formatPercent(p.profit_margin_percent)}, %${MIN_MARGIN_THRESHOLD} eşiğinin altında.`,
              linkTo: `/product-pricing?productId=${encodeURIComponent(p.product_id)}&name=${encodeURIComponent(p.product_name)}`,
              linkLabel: 'Fiyatlandır',
            })
          }
        }
        setItems([...derived, ...MOCK_CAMPAIGN_WARNINGS])
        setHasMock(true) // kampanya/indirim uyarıları hâlâ mock
      })
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchWarnings()
  }, [fetchWarnings])

  const filtered = useMemo(() => (filter === 'all' ? items : items.filter((i) => i.type === filter)), [items, filter])

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Uyarı Sayfası"
        actions={
          // DEFERRED ENHANCEMENT: uyarı eşiklerini (min kâr marjı vb.) yapılandırılabilir yapmak için
          // Ayarlar'a ayrı bir 'Uyarılar' sekmesi + backend gerekiyor (daha büyük iş, w3-polish kapsamı dışı).
          // Şimdilik link, var olan Ayarlar sayfasına gidiyor (önceki /settings?tab=uyarilar kopuk hedefti).
          <Link to="/settings" className="flex items-center gap-1 text-sm font-medium text-brand hover:underline">
            <Settings className="h-4 w-4" /> Ayarlar
          </Link>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl<'all' | WarningType> options={filterOptions} value={filter} onChange={setFilter} />
        <span className="text-sm text-text-secondary">{filtered.length} uyarı</span>
      </div>

      {hasMock && !error && (
        <div className="flex items-center gap-2 rounded-lg border border-warning bg-warning-soft px-4 py-3 text-sm text-warning">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Kampanya ve çakışan indirim uyarıları için backend sinyali henüz yok — bu iki tip örnek (mock) veri gösteriyor.
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={fetchWarnings} />}

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-app-border bg-app-surface p-16 text-center shadow-card">
          <AlertTriangle className="h-8 w-8 text-success" />
          <p className="text-sm text-text-secondary">
            {filter === 'all' ? 'Aktif uyarı yok — her şey yolunda ✓' : 'Bu filtrede uyarı yok ✓'}
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {filtered.map((item) => {
            const meta = typeMeta[item.type]
            const Icon = meta.icon
            return (
              <li key={item.id} className="flex items-start gap-3 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
                <span
                  className={cn(
                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
                    meta.tone === 'danger' && 'bg-danger-soft text-danger',
                    meta.tone === 'warning' && 'bg-warning-soft text-warning',
                    meta.tone === 'info' && 'bg-info-soft text-info',
                  )}
                >
                  <Icon className="h-5 w-5" />
                </span>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-text-primary">{item.title}</p>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    {item.isMock && <Badge tone="neutral">örnek</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-text-secondary">{item.detail}</p>
                </div>
                {item.linkTo && (
                  <Link
                    to={item.linkTo}
                    className="flex shrink-0 items-center gap-1 self-center text-sm font-medium text-brand hover:underline"
                  >
                    {item.linkLabel} <ChevronRight className="h-4 w-4" />
                  </Link>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
