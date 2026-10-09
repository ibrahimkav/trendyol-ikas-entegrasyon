import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import apiClient from '../../config/api'
import { useToast } from '../../context/ToastContext'
import {
  PageHeader,
  Select,
  Input,
  RadioGroup,
  Button,
  ProfitBadge,
  ErrorBanner,
  formatCurrency,
} from '../../components/ui'
import CampaignTabs from './CampaignTabs'

// "Kendi Kampanyanı Oluştur" — satıcının kendi indirim kampanyası + kâr-etkisi.
// Kâr-etkisi GERÇEK endpoint'ten (Pam, w2c-pam): POST /api/campaigns/profit-effect (Jim §2.1 formülü,
// komisyon indirimli fiyattan). Kampanya YAZMA (oluşturma) endpoint'i yok → 'Oluştur' TODO toast.
interface ProductRow {
  product_id: string
  product_name: string
  has_cost_data: boolean
}

interface ProfitEffectItem {
  product_id: string
  product_name: string
  current_price: number
  new_price: number
  current_net_profit: number
  new_net_profit: number
  delta: number
  current_margin_percent: number
  new_margin_percent: number
}

export default function BuildYourCampaign() {
  const toast = useToast()
  const [products, setProducts] = useState<ProductRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [productId, setProductId] = useState('')
  const [discountType, setDiscountType] = useState<'percentage' | 'fixed_amount'>('percentage')
  const [discountValue, setDiscountValue] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const [calcLoading, setCalcLoading] = useState(false)
  const [effect, setEffect] = useState<ProfitEffectItem | null>(null)
  const [effectError, setEffectError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/profit-margin-list', { params: { profit_filter: 'all' } })
      .then((res) => setProducts(res.data?.products ?? []))
      .catch((err) => setError(err?.userMessage || 'Ürünler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [])

  const selected = products.find((p) => p.product_id === productId)

  async function handleCalculate() {
    if (!selected || !(Number(discountValue) > 0)) return
    setCalcLoading(true)
    setEffectError(null)
    setEffect(null)
    try {
      const res = await apiClient.post('/campaigns/profit-effect', {
        product_ids: [productId],
        discount_type: discountType,
        discount_value: Number(discountValue),
        campaign_type: 'build_your_own',
      })
      const item: ProfitEffectItem | undefined = res.data?.items?.[0]
      if (item) {
        setEffect(item)
      } else if ((res.data?.skipped_no_cost_data ?? []).length > 0) {
        setEffectError('Bu ürünün maliyeti girilmemiş — kâr etkisi hesaplanamıyor (Ürün Ayarları\'ndan maliyet girin).')
      } else {
        setEffectError('Kâr etkisi hesaplanamadı.')
      }
    } catch (err: any) {
      setEffectError(err?.userMessage || 'Kâr etkisi hesaplanamadı.')
    } finally {
      setCalcLoading(false)
    }
  }

  function handleCreate() {
    toast({ type: 'info', message: 'Kampanya oluşturma backend entegrasyonu henüz eklenmedi (TODO — kampanya yazma endpoint\'i).' })
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Kampanya" breadcrumbs={[{ label: 'Kampanya' }, { label: 'Kendi Kampanyanı Oluştur' }]} />
      <CampaignTabs />

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Form */}
        <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-5 shadow-card">
          <h3 className="text-sm font-semibold text-text-primary">Kampanya Ayarları</h3>
          <Select
            label="Ürün"
            options={products.map((p) => ({ value: p.product_id, label: p.product_name }))}
            value={productId}
            onChange={(e) => {
              setProductId(e.target.value)
              setEffect(null)
              setEffectError(null)
            }}
            placeholder={loading ? 'Ürünler yükleniyor…' : 'Ürün seçin'}
            disabled={loading}
          />
          <RadioGroup
            name="discountType"
            label="İndirim Tipi"
            options={[
              { value: 'percentage', label: 'Yüzde (%)' },
              { value: 'fixed_amount', label: 'Tutar (₺)' },
            ]}
            value={discountType}
            onChange={(v) => setDiscountType(v as 'percentage' | 'fixed_amount')}
          />
          <Input
            label={discountType === 'percentage' ? 'İndirim Oranı (%)' : 'İndirim Tutarı (₺)'}
            type="number"
            value={discountValue}
            onChange={(e) => setDiscountValue(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Başlangıç" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <Input label="Bitiş" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleCalculate} disabled={!selected || !(Number(discountValue) > 0) || calcLoading}>
              {calcLoading ? 'Hesaplanıyor…' : 'Kâr Etkisini Hesapla'}
            </Button>
            <Button onClick={handleCreate} disabled={!selected || !(Number(discountValue) > 0)}>
              Kampanya Oluştur
            </Button>
          </div>
        </div>

        {/* Kâr-etkisi sonucu */}
        <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-5 shadow-card">
          <h3 className="text-sm font-semibold text-text-primary">Kâr Etkisi</h3>

          {effectError ? (
            <p className="text-sm text-warning">{effectError}</p>
          ) : !effect ? (
            <p className="text-sm text-text-secondary">Ürün ve indirim girip "Kâr Etkisini Hesapla"ya basın.</p>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-caption uppercase tracking-wide text-text-secondary">Mevcut Fiyat</p>
                  <p className="text-lg font-semibold tabular-nums text-text-primary">{formatCurrency(effect.current_price)}</p>
                </div>
                <ArrowRight className="h-5 w-5 text-text-muted" />
                <div>
                  <p className="text-caption uppercase tracking-wide text-text-secondary">Kampanya Fiyatı</p>
                  <p className="text-lg font-semibold tabular-nums text-brand">{formatCurrency(effect.new_price)}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 border-t border-app-border pt-4">
                <div>
                  <p className="text-caption uppercase tracking-wide text-text-secondary">Kâr (Şimdi)</p>
                  <div className="mt-0.5">
                    <ProfitBadge amount={effect.current_net_profit} percent={effect.current_margin_percent} />
                  </div>
                </div>
                <div>
                  <p className="text-caption uppercase tracking-wide text-text-secondary">Kâr (Kampanyada)</p>
                  <div className="mt-0.5">
                    <ProfitBadge amount={effect.new_net_profit} percent={effect.new_margin_percent} />
                  </div>
                </div>
              </div>

              <div className="rounded-md bg-app-surface-muted p-3">
                <p className="text-caption uppercase tracking-wide text-text-secondary">Kâr Değişimi</p>
                <p className={`text-lg font-bold tabular-nums ${effect.delta >= 0 ? 'text-success' : 'text-danger'}`}>
                  {effect.delta >= 0 ? '+' : ''}{formatCurrency(effect.delta)}
                </p>
                {effect.new_net_profit < 0 && <p className="mt-1 text-xs font-medium text-danger">⚠ Bu indirimle ürün zararına satılır.</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
