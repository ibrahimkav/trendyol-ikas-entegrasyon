import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Calculator, History as HistoryIcon } from 'lucide-react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import PriceHistory from '../components/PriceHistory'
import {
  PageHeader,
  Input,
  Select,
  RadioGroup,
  Toggle,
  Button,
  ProfitBadge,
  Skeleton,
  formatCurrency,
  cn,
} from '../components/ui'

// Gerçek endpoint (Pam, w2a-pam): POST /api/pricing/calculate — bkz.
// hive/agents/pam-mttzdxq5/w1-backend-auth-notes.md "Wave 2a eki". product_id verilirse cost/category
// backend'de DB'den otomatik doldurulur (biz sadece override etmek istediğimiz alanları göndeririz),
// bu yüzden Ürün Maliyeti/Kategori bu sayfada productId bağlamında ZORUNLU DEĞİL.
const categoryOptions = [
  { value: 'elektronik', label: 'Elektronik' },
  { value: 'giyim', label: 'Giyim' },
  { value: 'ev_yasam', label: 'Ev & Yaşam' },
  { value: 'kozmetik', label: 'Kozmetik' },
  { value: 'spor', label: 'Spor' },
  { value: 'kitap', label: 'Kitap' },
  { value: 'oyuncak', label: 'Oyuncak' },
]

const deliveryTypeOptions = [
  { value: 'standart', label: 'Standart' },
  { value: 'hizli', label: 'Hızlı Teslimat' },
]

const vatOptions = [
  { value: '20', label: '%20' },
  { value: '10', label: '%10' },
  { value: '1', label: '%1' },
  { value: '0', label: '%0' },
]

interface CalculateResult {
  suggested_price: number
  cost: number
  cargo_cost: number
  vat_amount: number
  vat_rate: number
  commission_amount: number
  commission_rate: number
  net_profit: number
  profit_margin_percent: number
}

export default function ProductPricing() {
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const productId = searchParams.get('productId')
  const nameFromQuery = searchParams.get('name')

  const [activeTab, setActiveTab] = useState<'calculator' | 'history'>('calculator')

  // Deep-link ön-doldurma (Pam, w2b-pam): GET /api/financial/product/{id} lokal+store-scoped
  const [prefillLoading, setPrefillLoading] = useState(false)
  const [resolvedName, setResolvedName] = useState<string | null>(nameFromQuery)
  const productName = resolvedName ?? nameFromQuery

  const [microExport, setMicroExport] = useState(false)
  const [cost, setCost] = useState('')
  const [deliveryType, setDeliveryType] = useState('standart')
  const [profitMode, setProfitMode] = useState<'amount' | 'percent'>('amount')
  const [profitValue, setProfitValue] = useState('')
  const [cargoFee, setCargoFee] = useState('')
  const [desi, setDesi] = useState('')
  const [vatRate, setVatRate] = useState('')
  const [category, setCategory] = useState('')
  const [customCommissionEnabled, setCustomCommissionEnabled] = useState(false)
  const [customCommissionValue, setCustomCommissionValue] = useState('')

  const [attemptedSubmit, setAttemptedSubmit] = useState(false)
  const [calculating, setCalculating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState(false)
  const [result, setResult] = useState<CalculateResult | null>(null)
  const [calcError, setCalcError] = useState<string | null>(null)

  useEffect(() => {
    if (!productId) return
    setPrefillLoading(true)
    apiClient
      .get(`/financial/product/${encodeURIComponent(productId)}`)
      .then((res) => {
        const p = res.data
        if (p?.product_name) setResolvedName(p.product_name)
        if (p?.default_cost != null && p.default_cost > 0) setCost(String(p.default_cost))
        if (p?.category) setCategory(p.category)
        if (p?.desi != null && p.desi > 0) setDesi(String(p.desi))
      })
      .catch(() => {
        // Ürün detayı çekilemedi — backend calculate yine product_id'den çözebilir, sessiz geç.
      })
      .finally(() => setPrefillLoading(false))
  }, [productId])

  function handleDifferentProduct() {
    navigate('/product-pricing', { replace: true })
    setResolvedName(null)
    setCost('')
    setCategory('')
    setDesi('')
  }

  // productId bağlamında maliyet backend'den gelebileceği için zorunlu değil; genel hesaplayıcı
  // modunda (productId yok) kullanıcının kendisi girmeli.
  const hasCommissionSource = category !== '' || !!productId || (customCommissionEnabled && customCommissionValue !== '')
  const canCalculate =
    (!!productId || Number(cost) > 0) &&
    cargoFee !== '' &&
    Number(cargoFee) >= 0 &&
    Number(profitValue) > 0 &&
    (microExport || vatRate !== '') &&
    hasCommissionSource

  async function handleCalculate() {
    setAttemptedSubmit(true)
    setApplied(false)
    setCalcError(null)
    if (!canCalculate) {
      setResult(null)
      return
    }
    setCalculating(true)
    try {
      const body: Record<string, unknown> = {
        target_mode: profitMode,
        target_value: Number(profitValue),
        vat_rate: microExport ? 0 : Number(vatRate) / 100,
      }
      if (productId) body.product_id = productId
      if (cost !== '') body.cost = Number(cost)
      if (cargoFee !== '') body.cargo_cost = Number(cargoFee)
      if (category) body.category = category
      // commission_rate fraction olarak gönderilir (ör. %12 için 0.12), category'den türetilen
      // varsayılanı ezer (Pam, w2a-pam eki — bkz. w1-backend-auth-notes.md).
      if (customCommissionEnabled && customCommissionValue !== '') {
        body.commission_rate = Number(customCommissionValue) / 100
      }

      const res = await apiClient.post<CalculateResult>('/pricing/calculate', body)
      setResult(res.data)
    } catch (err: any) {
      setResult(null)
      setCalcError(err?.userMessage || 'Hesaplama isteği başarısız oldu.')
    } finally {
      setCalculating(false)
    }
  }

  async function handleApplyPrice() {
    if (!productId || !result) return
    setApplying(true)
    try {
      await apiClient.post('/financial/profit-margin-list/bulk-price-update', {
        items: [{ product_id: productId, new_price: result.suggested_price }],
      })
      toast({ type: 'success', message: 'Fiyat güncellendi.' })
      setApplied(true)
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Fiyat uygulanamadı.' })
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Ürün Fiyatlandırma" />

      <div className="flex items-center gap-1 border-b border-app-border">
        <button
          type="button"
          onClick={() => setActiveTab('calculator')}
          className={cn(
            'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium',
            activeTab === 'calculator' ? 'border-brand text-brand' : 'border-transparent text-text-secondary hover:text-text-primary',
          )}
        >
          <Calculator className="h-4 w-4" /> Hesaplayıcı
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('history')}
          className={cn(
            'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium',
            activeTab === 'history' ? 'border-brand text-brand' : 'border-transparent text-text-secondary hover:text-text-primary',
          )}
        >
          <HistoryIcon className="h-4 w-4" /> Geçmiş
        </button>
      </div>

      {activeTab === 'history' ? (
        <PriceHistory />
      ) : prefillLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          {productId && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-brand bg-brand-soft px-4 py-3 text-sm text-brand">
              <span>
                <strong>{productName || productId}</strong> için fiyatlandırma yapıyorsunuz. Maliyet/kategori bilgisi girilmezse backend
                kayıtlı veriyi otomatik kullanır.
              </span>
              <button type="button" onClick={handleDifferentProduct} className="font-medium underline">
                Farklı ürün
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary">Seçimler</h3>
              <Toggle label="Mikro İhracat" checked={microExport} onChange={setMicroExport} />
              <Input
                label={`Ürün Maliyeti (₺)${productId ? ' — opsiyonel' : ''}`}
                type="number"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                error={attemptedSubmit && !productId && !(Number(cost) > 0) ? 'Bu alan zorunlu.' : undefined}
              />
              <Select label="Teslimat Tipi" options={deliveryTypeOptions} value={deliveryType} onChange={(e) => setDeliveryType(e.target.value)} />
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary">İstenilen Kâr Oranı / Tutarı</h3>
              <Select
                label="Hesap Türü"
                options={[
                  { value: 'amount', label: 'Tutara Göre (₺)' },
                  { value: 'percent', label: 'Orana Göre (%)' },
                ]}
                value={profitMode}
                onChange={(e) => setProfitMode(e.target.value as 'amount' | 'percent')}
              />
              <Input
                label={profitMode === 'amount' ? 'Kâr Tutarı (₺)' : 'Kâr Oranı (%)'}
                type="number"
                value={profitValue}
                onChange={(e) => setProfitValue(e.target.value)}
                error={attemptedSubmit && !(Number(profitValue) > 0) ? 'Bu alan zorunlu.' : undefined}
              />
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary">Kargo Ücreti</h3>
              <Input
                label="Kargo Ücreti (₺)"
                type="number"
                value={cargoFee}
                onChange={(e) => setCargoFee(e.target.value)}
                error={attemptedSubmit && cargoFee === '' ? 'Bu alan zorunlu.' : undefined}
              />
              <Input
                label="Desi"
                type="number"
                value={desi}
                onChange={(e) => setDesi(e.target.value)}
                hint="Bilgi amaçlı, hesaplamayı etkilemez (backend'de desi→kargo tarife tablosu yok, TODO)."
              />
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary">KDV (%)</h3>
              <RadioGroup name="vat" options={vatOptions} value={vatRate} onChange={setVatRate} />
              {microExport && <p className="text-xs text-text-muted">Mikro ihracatta KDV uygulanmaz (varsayım — iş kuralı teyit edilmeli).</p>}
              {attemptedSubmit && !microExport && vatRate === '' && <p className="text-xs text-danger">Bu alan zorunlu.</p>}
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary">Kategori → Komisyon Oranı</h3>
              <Select
                label={`Kategori${productId ? ' — opsiyonel' : ''}`}
                options={categoryOptions}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="Kategori seçin"
              />
              <Toggle label="Özel komisyon oranı" checked={customCommissionEnabled} onChange={setCustomCommissionEnabled} />
              {customCommissionEnabled && (
                <Input
                  label="Komisyon Oranı (%)"
                  type="number"
                  value={customCommissionValue}
                  onChange={(e) => setCustomCommissionValue(e.target.value)}
                  hint="Girilirse kategori varsayılanının yerine geçer."
                />
              )}
              {attemptedSubmit && category === '' && !productId && !(customCommissionEnabled && customCommissionValue !== '') && (
                <p className="text-xs text-danger">Kategori veya özel komisyon oranından biri zorunlu.</p>
              )}
            </div>

            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-app-border bg-app-surface p-4 text-center shadow-card">
              <span className="text-xs font-medium uppercase tracking-wide text-text-secondary">Önerilen Satış Fiyatı</span>
              <span className="text-3xl font-bold tabular-nums text-text-primary">
                {result !== null ? formatCurrency(result.suggested_price) : '₺ —'}
              </span>
              {result && <ProfitBadge amount={result.net_profit} percent={result.profit_margin_percent} />}
              {calcError && <p className="text-xs text-danger">{calcError}</p>}
              <Button onClick={handleCalculate} disabled={calculating}>
                {calculating ? 'Hesaplanıyor…' : 'Fiyat Oluştur'}
              </Button>
              {productId && result !== null && (
                <Button variant="outline" size="sm" onClick={handleApplyPrice} disabled={applied || applying}>
                  {applied ? 'Uygulandı' : applying ? 'Uygulanıyor…' : 'Bu Fiyatı Uygula'}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
