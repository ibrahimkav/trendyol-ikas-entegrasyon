import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Download, ExternalLink, Sparkles } from 'lucide-react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import WritebackPreview from '../components/WritebackPreview'
import {
  PageHeader,
  FilterPanel,
  FilterToggle,
  FilterRange,
  Select,
  Input,
  Button,
  Badge,
  SegmentedControl,
  DataTable,
  ProfitBadge,
  Skeleton,
  ErrorBanner,
  ProductThumbnail,
  formatCurrency,
  cn,
  type DataTableColumn,
} from '../components/ui'

// Gerçek endpoint (Pam, w2a-pam — bkz. hive/agents/pam-mttzdxq5/w1-backend-auth-notes.md "Wave 2a eki"):
// GET /api/financial/profit-margin-list — sunucu-taraflı filtre, auth+store gerekir (apiClient zaten
// Authorization header'ını ekliyor). "sku" alanı barcode üzerinden arıyor; "Marka" filtresi backend
// şemasında YOK (Product'ta brand alanı yok) — bu yüzden Marka select'i devre dışı bırakıldı.
interface ProfitMarginProduct {
  product_id: string
  product_name: string
  barcode: string | null
  category: string | null
  thumbnail_url: string | null
  current_price: number
  quantity_sold: number
  revenue: number
  product_cost: number
  commission: number
  cargo_cost: number
  gross_profit: number
  net_profit: number
  profit_margin_percent: number
  has_cost_data: boolean
  is_profitable: boolean
}

type ViewMode = 'grid' | 'table'
type GridDensity = '3' | '4'

const bulkFieldOptions = [
  { value: 'percent', label: 'Kâr Oranı %' },
  { value: 'amount', label: 'Kâr Tutarı ₺' },
  { value: 'price', label: 'Satış Fiyatı ₺' },
]

export default function ProfitMarginList() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const [products, setProducts] = useState<ProfitMarginProduct[]>([])
  const [categoryOptions, setCategoryOptions] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fetchedOnce, setFetchedOnce] = useState(false)

  const [showProfit, setShowProfit] = useState(searchParams.get('profit') !== '0')
  const [showLoss, setShowLoss] = useState(searchParams.get('loss') !== '0')
  const [minMargin, setMinMargin] = useState(searchParams.get('min') ?? '')
  const [maxMargin, setMaxMargin] = useState(searchParams.get('max') ?? '')
  const [skuInput, setSkuInput] = useState(searchParams.get('sku') ?? '')
  const [nameInput, setNameInput] = useState(searchParams.get('name') ?? '')
  const [category, setCategory] = useState(searchParams.get('category') ?? '')
  const skuQuery = useDebouncedValue(skuInput, 400)
  const nameQuery = useDebouncedValue(nameInput, 400)

  const [view, setView] = useState<ViewMode>((searchParams.get('view') as ViewMode) || 'grid')
  const [gridDensity, setGridDensity] = useState<GridDensity>((searchParams.get('density') as GridDensity) || '4')

  const [bulkField, setBulkField] = useState('')
  const [bulkValue, setBulkValue] = useState('')
  const [bulkSubmitting, setBulkSubmitting] = useState(false)

  // "İkisi de kapalı" = hiçbiri gösterilmesin (backend'in profit_filter enum'ında bu mod yok,
  // bu durumda hiç istek atmadan boş state gösteriyoruz).
  const showNothing = !showProfit && !showLoss

  const fetchProducts = useCallback(() => {
    if (showNothing) {
      setProducts([])
      setLoading(false)
      setFetchedOnce(true)
      return
    }
    setLoading(true)
    setError(null)
    const profitFilter = showProfit && showLoss ? 'all' : showProfit ? 'profit' : 'loss'
    const params: Record<string, string> = { profit_filter: profitFilter }
    if (minMargin) params.min_margin = minMargin
    if (maxMargin) params.max_margin = maxMargin
    if (nameQuery) params.product_name = nameQuery
    if (skuQuery) params.sku = skuQuery
    if (category) params.category = category

    apiClient
      .get('/financial/profit-margin-list', { params })
      .then((res) => {
        const list: ProfitMarginProduct[] = res.data?.products ?? []
        setProducts(list)
        setFetchedOnce(true)
        if (!category) {
          const uniqueCategories = Array.from(new Set(list.map((p) => p.category).filter(Boolean))) as string[]
          setCategoryOptions((prev) => Array.from(new Set([...prev, ...uniqueCategories])).sort())
        }
      })
      .catch((err) => {
        setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.')
      })
      .finally(() => setLoading(false))
  }, [showNothing, showProfit, showLoss, minMargin, maxMargin, nameQuery, skuQuery, category])

  useEffect(() => {
    fetchProducts()
  }, [fetchProducts])

  // Filtreler URL query'de tutulur (paylaşılabilir/geri dönülebilir link).
  useEffect(() => {
    const next = new URLSearchParams()
    if (!showProfit) next.set('profit', '0')
    if (!showLoss) next.set('loss', '0')
    if (minMargin) next.set('min', minMargin)
    if (maxMargin) next.set('max', maxMargin)
    if (skuQuery) next.set('sku', skuQuery)
    if (nameQuery) next.set('name', nameQuery)
    if (category) next.set('category', category)
    if (view !== 'grid') next.set('view', view)
    if (gridDensity !== '4') next.set('density', gridDensity)
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showProfit, showLoss, minMargin, maxMargin, skuQuery, nameQuery, category, view, gridDensity])

  const filterKey = `${showProfit}-${showLoss}-${minMargin}-${maxMargin}-${skuQuery}-${nameQuery}-${category}`

  function handleClearFilters() {
    setShowProfit(true)
    setShowLoss(true)
    setMinMargin('')
    setMaxMargin('')
    setSkuInput('')
    setNameInput('')
    setCategory('')
  }

  async function handleBulkUpdate() {
    if (!bulkField || !bulkValue || products.length === 0) return
    setBulkSubmitting(true)
    try {
      const productIds = products.map((p) => p.product_id)
      if (bulkField === 'price') {
        await apiClient.post('/financial/profit-margin-list/bulk-price-update', {
          items: productIds.map((id) => ({ product_id: id, new_price: Number(bulkValue) })),
        })
      } else {
        await apiClient.post('/financial/profit-margin-list/bulk-price-update', {
          product_ids: productIds,
          target_mode: bulkField, // 'amount' | 'percent'
          target_value: Number(bulkValue),
        })
      }
      toast({ type: 'success', message: `${productIds.length} ürün için güncelleme gönderildi.` })
      setBulkField('')
      setBulkValue('')
      fetchProducts()
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Toplu güncelleme başarısız oldu.' })
    } finally {
      setBulkSubmitting(false)
    }
  }

  function handleDownloadReport() {
    toast({ type: 'info', message: 'Rapor indirme özelliği henüz eklenmedi (TODO).' })
  }

  const columns: DataTableColumn<ProfitMarginProduct>[] = useMemo(
    () => [
      {
        key: 'product_name',
        header: 'Ürün',
        accessor: (p) => (
          <div className="flex items-center gap-2.5">
            <ProductThumbnail url={p.thumbnail_url} alt={p.product_name} size={40} />
            <div>
              <p className="font-medium text-text-primary">{p.product_name}</p>
              <p className="text-xs text-text-muted">
                {p.barcode ? `Sku: ${p.barcode}` : `ID: ${p.product_id}`}
                {p.category ? ` · ${p.category}` : ''}
              </p>
            </div>
          </div>
        ),
        sortValue: (p) => p.product_name,
      },
      { key: 'current_price', header: 'Fiyat', align: 'right', accessor: (p) => formatCurrency(p.current_price), sortValue: (p) => p.current_price },
      { key: 'quantity_sold', header: 'Satış Adedi', align: 'right', accessor: (p) => p.quantity_sold, sortValue: (p) => p.quantity_sold },
      {
        key: 'profit',
        header: 'Kâr / Zarar',
        align: 'right',
        accessor: (p) =>
          p.has_cost_data ? (
            <ProfitBadge amount={p.net_profit} percent={p.profit_margin_percent} />
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <Badge tone="warning">Maliyet eksik</Badge>
              <Link
                to="/product-settings"
                className="text-text-muted hover:text-brand"
                title="Ürün Ayarları'ndan maliyet gir"
                aria-label="Ürün Ayarları'ndan maliyet gir"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </span>
          ),
        sortValue: (p) => p.net_profit,
      },
      {
        key: 'actions',
        header: '',
        align: 'right',
        accessor: (p) => (
          <Link to={`/product-pricing?productId=${encodeURIComponent(p.product_id)}&name=${encodeURIComponent(p.product_name)}`}>
            <Button size="sm" variant="outline">
              Fiyatlandır
            </Button>
          </Link>
        ),
      },
    ],
    [],
  )

  const showEmptyNoData = !loading && fetchedOnce && !showNothing && products.length === 0
  const showEmptyNothingSelected = !loading && showNothing

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Kâr Marjı Listesi"
        actions={
          <Button variant="outline" leftIcon={<Download className="h-4 w-4" />} onClick={handleDownloadReport}>
            Raporu İndir
          </Button>
        }
      />

      <div className="rounded-lg border border-warning bg-warning-soft px-4 py-3 text-sm text-warning">
        Bu sayfadan HB/Trendyol liste fiyatları düzenlenebilir, dikkatli olun.
      </div>

      <WritebackPreview />

      {error && <ErrorBanner message={error} onRetry={fetchProducts} />}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_1fr]">
        <FilterPanel onClear={handleClearFilters}>
          <FilterToggle label="Kâr eden ürünleri göster" checked={showProfit} onChange={setShowProfit} />
          <FilterToggle label="Zarar eden ürünleri göster" checked={showLoss} onChange={setShowLoss} />
          <FilterRange
            label="Kâr Oranı (%)"
            minValue={minMargin}
            maxValue={maxMargin}
            onMinChange={setMinMargin}
            onMaxChange={setMaxMargin}
          />
          <Input label="HB/Trendyol Sku No" value={skuInput} onChange={(e) => setSkuInput(e.target.value)} placeholder="Barkod/Sku ara" />
          <Input label="Ürün Adı" value={nameInput} onChange={(e) => setNameInput(e.target.value)} placeholder="Ürün adı ara" />
          <Select
            label="Kategori"
            options={categoryOptions.map((c) => ({ value: c, label: c }))}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Tüm kategoriler"
          />
          <Select label="Marka" options={[]} placeholder="Backend'de marka alanı yok (TODO)" disabled />
        </FilterPanel>

        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
            <div className="flex flex-wrap items-center gap-2">
              <Select
                options={bulkFieldOptions}
                value={bulkField}
                onChange={(e) => setBulkField(e.target.value)}
                placeholder="Girilecek Değeri Seç"
              />
              <Input value={bulkValue} onChange={(e) => setBulkValue(e.target.value)} placeholder="Değer" className="w-28" />
              <Button size="sm" onClick={handleBulkUpdate} disabled={!bulkField || !bulkValue || products.length === 0 || bulkSubmitting}>
                {bulkSubmitting ? 'Güncelleniyor…' : 'Tüm Ürünleri Güncelle'}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setBulkField('')
                  setBulkValue('')
                }}
              >
                Temizle
              </Button>
              {bulkField && bulkValue && (
                <span className="text-xs text-text-secondary">Filtrelenmiş {products.length} ürüne uygulanacak.</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <SegmentedControl
                options={[
                  { value: 'grid', label: 'Kart' },
                  { value: 'table', label: 'Tablo' },
                ]}
                value={view}
                onChange={setView}
              />
              {view === 'grid' && (
                <SegmentedControl
                  options={[
                    { value: '3', label: '3 Kolon' },
                    { value: '4', label: '4 Kolon' },
                  ]}
                  value={gridDensity}
                  onChange={setGridDensity}
                />
              )}
            </div>
          </div>

          {loading && (
            <div className={cn('grid gap-4', gridDensity === '3' ? 'sm:grid-cols-2 lg:grid-cols-3' : 'sm:grid-cols-2 lg:grid-cols-4')}>
              {Array.from({ length: gridDensity === '3' ? 6 : 8 }).map((_, i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          )}

          {showEmptyNothingSelected && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-app-border bg-app-surface p-16 text-center shadow-card">
              <p className="text-sm text-text-secondary">Hiçbir ürün gösterilmiyor — en az bir filtreyi (Kâr eden / Zarar eden) açın.</p>
            </div>
          )}

          {showEmptyNoData && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-app-border bg-app-surface p-16 text-center shadow-card">
              <Sparkles className="h-8 w-8 text-brand" />
              <p className="text-sm text-text-secondary">Bu filtrelere uyan ürün bulunamadı.</p>
              <Button variant="outline" size="sm" onClick={handleClearFilters}>
                Filtreleri Temizle
              </Button>
            </div>
          )}

          {!loading && !showEmptyNoData && !showEmptyNothingSelected && (
            <>
              {view === 'table' ? (
                <DataTable key={filterKey} columns={columns} data={products} rowKey={(p) => p.product_id} pageSize={10} />
              ) : (
                <div
                  className={cn('grid gap-4', gridDensity === '3' ? 'sm:grid-cols-2 lg:grid-cols-3' : 'sm:grid-cols-2 lg:grid-cols-4')}
                >
                  {products.map((p) => (
                    <div key={p.product_id} className="flex flex-col gap-3 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
                      <div className="flex h-28 items-center justify-center rounded-md bg-app-surface-muted">
                        <ProductThumbnail url={p.thumbnail_url} alt={p.product_name} size={96} />
                      </div>
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs text-text-muted">{p.barcode ? `Sku: ${p.barcode}` : `ID: ${p.product_id}`}</p>
                          {p.category && <Badge tone="neutral">{p.category}</Badge>}
                        </div>
                        <p className="line-clamp-2 text-sm font-medium text-text-primary">{p.product_name}</p>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-base font-semibold text-text-primary">{formatCurrency(p.current_price)}</span>
                        {p.has_cost_data ? (
                          <ProfitBadge amount={p.net_profit} percent={p.profit_margin_percent} />
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <Badge tone="warning">Maliyet eksik</Badge>
                            <Link
                              to="/product-settings"
                              className="text-text-muted hover:text-brand"
                              title="Ürün Ayarları'ndan maliyet gir"
                              aria-label="Ürün Ayarları'ndan maliyet gir"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Link>
                          </span>
                        )}
                      </div>
                      <Link to={`/product-pricing?productId=${encodeURIComponent(p.product_id)}&name=${encodeURIComponent(p.product_name)}`}>
                        <Button size="sm" variant="outline" className="w-full">
                          Fiyatlandır
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
