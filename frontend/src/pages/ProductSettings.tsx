import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, AlertTriangle, Check, Clock, Download, Loader2, Upload, X, Zap } from 'lucide-react'
import { Badge, Button, DataTable, Input, PageHeader, ProductThumbnail, Toggle, cn, formatCurrency, type DataTableColumn } from '../components/ui'
import { useToast } from '../context/ToastContext'
import {
  bulkUploadProductSettingsCsv,
  downloadProductSettingsTemplate,
  fetchChangeHistory,
  fetchGroupedProductSettings,
  saveGroupedProductSetting,
  saveProductSetting,
  type BulkCostError,
  type BulkCostResponse,
  type ChangeHistoryEntry,
  type GroupedProductSetting,
} from '../lib/productSettingsApi'

type RowState = { cost: string; desi: string; saving: boolean; saved: boolean }

function rowKey(p: GroupedProductSetting): string {
  return p.content_id ?? p.variant_product_ids[0]
}

// w3-cost-completeness — maliyeti girilmemiş ürünün kâr rakamı hesaplanamaz (Dashboard/Kâr Marjı
// bu değeri dışlıyor), o yüzden "girili" burada KAYITLI backend değerine bakar, henüz kaydedilmemiş
// yerel input state'ine değil (UI'da öyle görünmesi kanıt sayılmaz — bkz. w3-bulk-cost-ui dersi).
function hasCost(p: GroupedProductSetting): boolean {
  return p.default_cost > 0
}

// w3-bulk-cost-ui — hata kodlarının Türkçe karşılığı (bkz. hive/docs/bulk-cost-csv.md § Hata kodları).
// Ham kodu asla ekranda gösterme; detay backend'den zaten Türkçe geliyor, ayrı kolonda gösterilir.
const BULK_ERROR_LABELS: Record<string, string> = {
  MISSING_KEY: 'Ürün eşleştirilemedi (content_id ve product_id ikisi de boş)',
  UNKNOWN_KEY: 'Ürün mağazanızda bulunamadı (silinmiş veya başka mağazaya ait olabilir)',
  INVALID_NUMBER: 'Sayı olarak okunamadı',
  NEGATIVE_VALUE: 'Negatif değer geçersiz (maliyet/desi eksi olamaz)',
}

function translateBulkErrorCode(code: string): string {
  return BULK_ERROR_LABELS[code] ?? code
}

// w3-cost-entry-ux-fix (hive/docs/cost-entry-ux-review.md #4) — canlı testte ölçüldü: input
// type="number" alanına gerçek tuş vuruşuyla "150,50" yazınca tarayıcı virgülü sessizce reddedip
// input.value'yu TAMAMEN BOŞ bırakıyor (Chrome, sayı-olmayan ara durumu geçersiz sayıyor) — kullanıcı
// hiç fark etmeden maliyeti 0 kaydediyor. Çözüm: type="text" + manuel ayrıştırma, backend'in
// _parse_tr_number'ıyla aynı mantık (virgül VE nokta ondalık ayracı kabul edilir).
function sanitizeDecimalInput(raw: string): string {
  return raw.replace(/[^0-9.,]/g, '')
}

function parseDecimalInput(raw: string): number {
  const s = raw.trim()
  if (!s) return 0
  let normalized = s
  if (normalized.includes(',') && normalized.includes('.')) {
    normalized =
      normalized.lastIndexOf(',') > normalized.lastIndexOf('.')
        ? normalized.replace(/\./g, '').replace(',', '.')
        : normalized.replace(/,/g, '')
  } else if (normalized.includes(',')) {
    normalized = normalized.replace(',', '.')
  }
  const n = Number(normalized)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

// w3-cost-entry-followups #5 — backend'in GERÇEKTEN döndürdüğü alanlar (product_id, field,
// old_value, new_value, source, changed_at) — "kim" alanı YOK, o yüzden burada da yok.
const HISTORY_FIELD_LABELS: Record<string, string> = {
  default_cost: 'Maliyet',
  desi: 'Desi',
  current_price: 'Fiyat',
}

const HISTORY_SOURCE_LABELS: Record<string, string> = {
  single: 'Tekli kayıt',
  group: 'Toplu (ürün grubu)',
  bulk_csv: 'CSV toplu yükleme',
  bulk_price_update: 'Toplu fiyat güncelleme',
}

function formatHistoryValue(field: string, value: number | null): string {
  if (value == null) return '—'
  return field === 'desi' ? value.toLocaleString('tr-TR') : formatCurrency(value)
}

function formatChangedAt(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/**
 * Ürün Ayarları `/product-settings` — Jim'in spec'i (melontik-page-spec.md): ürün başına
 * MALİYET + DESİ giriş ekranı; komisyon Trendyol API'den otomatik gelir (burada girilmez).
 * Kâr hesapları (Dashboard, Kâr Marjı Listesi, Canlı Performans) bu maliyet verisine dayanır —
 * maliyeti girilmemiş ürünler "Maliyeti Olan Ciro"dan hariç tutulur (Jim'in formül notu).
 *
 * w3-grouped-settings-ui: liste artık content_id (Trendyol ürün kimliği) bazında — aynı ürünün
 * beden varyantları (ör. 9 beden) tek satırda toplanır, kullanıcı ürün başına TEK maliyet+desi
 * girer ve kaydettiğinde TÜM bedenlere yazılır (god'un talimatı — insan beden-bazlı tekrarı istemedi).
 * w3-image-bind-ui: görsel (thumbnail_url) `ProductThumbnail` ile bağlandı, gruplu satırda tek görsel yeter.
 */
export default function ProductSettings() {
  const [products, setProducts] = useState<GroupedProductSetting[]>([])
  const [rows, setRows] = useState<Record<string, RowState>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [search, setSearch] = useState('')
  const [onlyMissingCost, setOnlyMissingCost] = useState(false)
  const toast = useToast()

  // w3-bulk-cost-ui: şablon indir / CSV yükle / dry-run önizleme / uygula akışı.
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [bulkFile, setBulkFile] = useState<File | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkPreview, setBulkPreview] = useState<BulkCostResponse | null>(null)
  const [bulkResult, setBulkResult] = useState<BulkCostResponse | null>(null)

  // w3-cost-entry-followups #5 — "Değişiklik Geçmişi" paneli. Tüm geçmiş bir kez çekilip (ilk açılışta)
  // önbelleğe alınır, panel client-side product_id'ye göre filtreler — her satır için ayrı istek yok.
  const [historyEntries, setHistoryEntries] = useState<ChangeHistoryEntry[] | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState(false)
  const [historyProduct, setHistoryProduct] = useState<GroupedProductSetting | null>(null)

  async function openHistory(p: GroupedProductSetting) {
    setHistoryProduct(p)
    if (historyEntries !== null) return
    setHistoryLoading(true)
    setHistoryError(false)
    try {
      const entries = await fetchChangeHistory()
      setHistoryEntries(entries)
    } catch {
      setHistoryError(true)
    } finally {
      setHistoryLoading(false)
    }
  }

  // Grup kaydı TEK tıklamayla ürünün TÜM bedenlerine yazıyor (bkz. w3-grouped-settings-ui) — backend
  // her bedene (product_id) ayrı bir change-history satırı yazıyor, yoksa bu panel de "aynı ürün 8 kez
  // değişmiş gibi" görünüp kafa karıştırırdı. Aynı alan+kaynak+eski/yeni değer+aynı dakika içindeki
  // kayıtları TEK satıra indiriyoruz (ana tablonun bedenleri tek satırda toplama mantığıyla aynı ruh) —
  // veri uydurmuyoruz, sadece aynı kaydetme eyleminin kaç bedene uygulandığını sayıp gösteriyoruz.
  const productHistory = useMemo(() => {
    if (!historyProduct || !historyEntries) return []
    const ids = new Set(historyProduct.variant_product_ids)
    const matched = historyEntries.filter((e) => ids.has(e.product_id))
    const merged = new Map<string, ChangeHistoryEntry & { variantCount: number }>()
    for (const e of matched) {
      const minuteKey = (e.changed_at ?? '').slice(0, 16)
      const key = `${e.field}|${e.source}|${e.old_value}|${e.new_value}|${minuteKey}`
      const existing = merged.get(key)
      if (existing) {
        existing.variantCount += 1
      } else {
        merged.set(key, { ...e, variantCount: 1 })
      }
    }
    return Array.from(merged.values()).slice(0, 20)
  }, [historyProduct, historyEntries])

  async function loadProducts() {
    setLoading(true)
    setError(false)
    try {
      const { products } = await fetchGroupedProductSettings()
      setProducts(products)
      setRows(
        Object.fromEntries(
          products.map((p) => [
            rowKey(p),
            { cost: String(p.default_cost || ''), desi: String(p.desi || ''), saving: false, saved: false },
          ]),
        ),
      )
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  function bulkErrorToastMessage(err: unknown): string {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 404) return 'Toplu yükleme uç noktası henüz hazır değil — backend ekibi çalışıyor, birazdan tekrar deneyin.'
    return 'CSV işlenemedi. Dosyayı kontrol edip tekrar deneyin.'
  }

  async function handleTemplateDownload() {
    try {
      await downloadProductSettingsTemplate()
    } catch (err) {
      toast({ type: 'error', message: bulkErrorToastMessage(err) })
    }
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBulkFile(file)
    setBulkBusy(true)
    setBulkPreview(null)
    setBulkResult(null)
    try {
      const res = await bulkUploadProductSettingsCsv(file, true)
      setBulkPreview(res)
    } catch (err) {
      toast({ type: 'error', message: bulkErrorToastMessage(err) })
      setBulkFile(null)
    } finally {
      setBulkBusy(false)
    }
  }

  function handleCancelBulkPreview() {
    setBulkPreview(null)
    setBulkFile(null)
  }

  async function handleApplyBulk() {
    if (!bulkFile) return
    setBulkBusy(true)
    try {
      const res = await bulkUploadProductSettingsCsv(bulkFile, false)
      setBulkResult(res)
      setBulkPreview(null)
      setBulkFile(null)
      await loadProducts()
      toast({
        type: res.error_count > 0 ? 'error' : 'success',
        message:
          res.error_count > 0
            ? `${res.updated_variants ?? res.will_update} satır uygulandı, ${res.error_count} satır hata nedeniyle atlandı.`
            : `${res.updated_variants ?? res.will_update} satır uygulandı.`,
      })
    } catch (err) {
      toast({ type: 'error', message: bulkErrorToastMessage(err) })
    } finally {
      setBulkBusy(false)
    }
  }

  const costFilledCount = useMemo(() => products.filter(hasCost).length, [products])
  const costMissingCount = products.length - costFilledCount

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return products.filter((p) => {
      if (onlyMissingCost && hasCost(p)) return false
      if (!q) return true
      return (
        p.product_name.toLowerCase().includes(q) ||
        (p.category ?? '').toLowerCase().includes(q) ||
        p.variant_product_ids.some((id) => id.toLowerCase().includes(q))
      )
    })
  }, [products, search, onlyMissingCost])

  function updateRow(key: string, patch: Partial<RowState>) {
    setRows((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }))
  }

  async function handleSave(p: GroupedProductSetting) {
    const key = rowKey(p)
    const row = rows[key]
    if (!row) return
    const cost = parseDecimalInput(row.cost)
    const desi = parseDecimalInput(row.desi)
    updateRow(key, { saving: true, saved: false })
    try {
      let updatedCount = 1
      if (p.content_id) {
        const res = await saveGroupedProductSetting(p.content_id, { default_cost: cost, desi })
        updatedCount = res.updated_count
      } else {
        await saveProductSetting(p.variant_product_ids[0], { default_cost: cost, desi })
      }
      updateRow(key, { saving: false, saved: true })
      // w3-cost-entry-ux-fix #1 (GERÇEK BUG) — backend yazımı başarılı olsa da `products` state'i
      // yerinde güncellenmezse "Maliyeti eksik" rozeti/üst sayaç/filtre sayfa yenilenene kadar eski
      // (stale) kalıyordu, 53 ürünü takip eden kullanıcı ilerlemesini kaybediyordu. Kaydedilen değer
      // TÜM bedenlere yazıldığı için cost_mixed/desi_mixed de false'a döner.
      setProducts((prev) =>
        prev.map((item) =>
          rowKey(item) === key ? { ...item, default_cost: cost, desi, cost_mixed: false, desi_mixed: false } : item,
        ),
      )
      toast({
        type: 'success',
        message:
          updatedCount > 1
            ? `${p.product_name} — ${updatedCount} bedene uygulandı.`
            : `${p.product_name} kaydedildi.`,
      })
    } catch {
      updateRow(key, { saving: false, saved: false })
      toast({ type: 'error', message: 'Kaydedilemedi, tekrar deneyin.' })
    }
  }

  const columns: DataTableColumn<GroupedProductSetting>[] = [
    {
      key: 'product',
      header: 'Ürün Bilgisi',
      accessor: (r) => (
        <div className="flex items-center gap-2.5">
          <ProductThumbnail url={r.thumbnail_url} alt={r.product_name} size={40} />
          {hasCost(r) ? (
            <span>{r.product_name}</span>
          ) : (
            <div className="flex items-center gap-1.5">
              <span>{r.product_name}</span>
              <Badge
                tone="warning"
                icon={<AlertCircle className="h-3 w-3" />}
                className="shrink-0"
              >
                <span title="Maliyet girilmeyen ürünün kâr rakamı hesaplanamıyor.">Maliyet eksik</span>
              </Badge>
            </div>
          )}
        </div>
      ),
      sortValue: (r) => r.product_name,
    },
    { key: 'category', header: 'Kategori', accessor: (r) => r.category ?? '—' },
    {
      key: 'variants',
      header: 'Bedenler',
      accessor: (r) =>
        r.variant_count > 1 ? (
          <span title={r.variant_product_ids.join(', ')} className="cursor-help underline decoration-dotted">
            {r.variant_count} beden
          </span>
        ) : (
          <span className="font-mono text-xs text-text-secondary">{r.variant_product_ids[0]}</span>
        ),
    },
    {
      key: 'price',
      header: 'Fiyat',
      align: 'right',
      accessor: (r) =>
        r.price_min == null
          ? '—'
          : r.price_min === r.price_max
            ? formatCurrency(r.price_min)
            : `${formatCurrency(r.price_min)} – ${formatCurrency(r.price_max ?? r.price_min)}`,
    },
    {
      key: 'cost',
      header: 'Ürün Maliyeti (₺)',
      align: 'right',
      accessor: (r) => {
        const key = rowKey(r)
        return (
          <div className="flex flex-col items-end gap-0.5">
            <Input
              type="text"
              inputMode="decimal"
              value={rows[key]?.cost ?? ''}
              onChange={(e) => updateRow(key, { cost: sanitizeDecimalInput(e.target.value), saved: false })}
              className="h-9 w-28 text-right"
              placeholder="0,00"
            />
            {r.cost_mixed && (
              <p className="text-[10px] text-amber-600">Bedenler arasında farklı — kaydetmek hepsini eşitler</p>
            )}
          </div>
        )
      },
    },
    {
      key: 'desi',
      header: 'Desi',
      align: 'right',
      accessor: (r) => {
        const key = rowKey(r)
        return (
          <div className="flex flex-col items-end gap-0.5">
            <Input
              type="text"
              inputMode="decimal"
              value={rows[key]?.desi ?? ''}
              onChange={(e) => updateRow(key, { desi: sanitizeDecimalInput(e.target.value), saved: false })}
              className="h-9 w-20 text-right"
              placeholder="0"
            />
            {r.desi_mixed && (
              <p className="text-[10px] text-amber-600">Bedenler arasında farklı — kaydetmek hepsini eşitler</p>
            )}
          </div>
        )
      },
    },
    {
      key: 'action',
      header: '',
      align: 'right',
      accessor: (r) => {
        const key = rowKey(r)
        const row = rows[key]
        return (
          <div className="flex items-center justify-end gap-1.5">
            <button
              type="button"
              onClick={() => openHistory(r)}
              className="rounded-md p-1.5 text-text-muted hover:bg-app-surface-muted hover:text-text-primary"
              title="Değişiklik geçmişi"
              aria-label="Değişiklik geçmişi"
            >
              <Clock className="h-4 w-4" />
            </button>
            <Button size="sm" variant={row?.saved ? 'outline' : 'primary'} onClick={() => handleSave(r)} disabled={row?.saving}>
              {row?.saving ? <Loader2 className="h-4 w-4 animate-spin" /> : row?.saved ? <Check className="h-4 w-4" /> : 'Kaydet'}
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Ürün Ayarları" />

      <p className="text-sm text-text-secondary">
        Her ürün için <strong>maliyet</strong> ve <strong>desi</strong> girin. Aynı ürünün farklı bedenleri tek satırda
        toplanır — kaydettiğinizde girdiğiniz değer o ürünün <strong>tüm bedenlerine</strong> uygulanır. Komisyon oranı
        Trendyol'dan otomatik gelir, burada girmenize gerek yoktur. Maliyeti girilen ürünler kâr analizlerine
        (Dashboard, Kâr Marjı Listesi) dahil edilir.
      </p>

      {!loading && !error && products.length > 0 && (
        <p className="text-sm text-text-secondary">
          <strong className="text-text-primary">{products.length}</strong> ürünün{' '}
          <strong className="text-text-primary">{costFilledCount}</strong>'inde maliyet girili,{' '}
          <strong className={costMissingCount > 0 ? 'text-warning' : 'text-text-primary'}>{costMissingCount}</strong>
          'inde eksik.
        </p>
      )}

      <div
        className={cn(
          'flex flex-col gap-3 rounded-lg border p-4 shadow-card sm:flex-row sm:items-center sm:justify-between',
          costMissingCount > 10 ? 'border-brand/40 bg-brand-soft/40' : 'border-app-border bg-app-surface',
        )}
      >
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-text-primary">CSV ile toplu giriş</p>
            {costMissingCount > 10 && (
              <Badge tone="brand" icon={<Zap className="h-3 w-3" />}>
                Önerilen yöntem — daha hızlı
              </Badge>
            )}
          </div>
          <p className="text-xs text-text-secondary">
            Şablonu indirin, Excel'de maliyet/desi kolonlarını doldurun, sonra geri yükleyin — kaydetmeden önce
            önizleme ekranında ne değişeceğini görürsünüz.
          </p>
          {costMissingCount > 10 && (
            <p className="mt-1 text-xs font-medium text-brand">
              {costMissingCount} ürünü tek tek girmek onlarca tıklama gerektirir — CSV ile şablonu indirip Excel'de
              doldurduktan sonra 3 tıkla toplu tamamlayabilirsiniz.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={handleTemplateDownload}>
            <Download className="mr-1.5 h-4 w-4" /> Şablon indir
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleFileSelected}
          />
          <Button variant="primary" size="sm" onClick={() => fileInputRef.current?.click()} disabled={bulkBusy}>
            {bulkBusy ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Upload className="mr-1.5 h-4 w-4" />}
            CSV yükle
          </Button>
        </div>
      </div>

      {bulkResult && (
        <div
          className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${
            bulkResult.error_count > 0
              ? 'border-amber-300 bg-amber-50 text-amber-800'
              : 'border-success/30 bg-success-soft text-success'
          }`}
        >
          <div>
            <p className="font-medium">
              {bulkResult.error_count > 0
                ? `${bulkResult.updated_variants ?? bulkResult.will_update} satır uygulandı, ${bulkResult.error_count} satır hata nedeniyle atlandı.`
                : `${bulkResult.updated_variants ?? bulkResult.will_update} satır uygulandı.`}
            </p>
            {bulkResult.error_count > 0 && (
              <details className="mt-1">
                <summary className="cursor-pointer text-xs underline">Atlanan satırları gör</summary>
                <ul className="mt-1 space-y-1 text-xs">
                  {bulkResult.errors.map((e, i) => (
                    <li key={i}>
                      Satır {e.row}: {translateBulkErrorCode(e.error_code)} — {e.detail}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
          <button
            type="button"
            onClick={() => setBulkResult(null)}
            className="text-text-muted hover:text-text-primary"
            aria-label="Kapat"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Ürün adı, kategori veya SKU ara"
          className="max-w-sm"
        />
        <Toggle
          label="Sadece maliyeti eksik olanlar"
          checked={onlyMissingCost}
          onChange={setOnlyMissingCost}
        />
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          Ürünler yüklenemedi. Sayfayı yenileyip tekrar deneyin.
        </div>
      ) : loading ? (
        <div className="h-64 animate-pulse rounded-lg border border-app-border bg-app-surface-muted" />
      ) : products.length === 0 ? (
        <div className="rounded-lg border border-app-border bg-app-surface p-10 text-center text-sm text-text-muted shadow-card">
          Henüz ürün bulunamadı. Mağazanızı bağladıktan (Ayarlar) ve satış verisi geldikten sonra ürünler burada listelenir.
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-app-border bg-app-surface p-10 text-center text-sm text-text-muted shadow-card">
          {onlyMissingCost ? 'Maliyeti eksik ürün kalmadı.' : 'Aramayla eşleşen ürün yok.'}
        </div>
      ) : (
        <>
          <p className="text-xs text-text-muted">{filtered.length} ürün gösteriliyor</p>
          <DataTable columns={columns} data={filtered} rowKey={(r) => rowKey(r)} pageSize={60} />
        </>
      )}

      {bulkPreview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={() => !bulkBusy && handleCancelBulkPreview()}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-lg bg-app-surface shadow-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-app-border px-6 py-4">
              <h2 className="text-lg font-semibold text-text-primary">Önizleme — {bulkFile?.name}</h2>
              <button
                type="button"
                onClick={handleCancelBulkPreview}
                disabled={bulkBusy}
                className="text-text-muted hover:text-text-primary"
                aria-label="Kapat"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              <p className="text-sm text-text-secondary">
                <strong className="text-text-primary">{bulkPreview.will_update}</strong> satır güncellenecek ·{' '}
                <strong className="text-text-primary">{bulkPreview.skipped}</strong> satır boş bırakıldığı için
                atlanacak
                {bulkPreview.error_count > 0 && (
                  <>
                    {' '}
                    · <strong className="text-danger">{bulkPreview.error_count}</strong> satır hatalı (bunlar
                    yazılmayacak)
                  </>
                )}
                .
              </p>

              {bulkPreview.error_count > 0 && (
                <div className="mt-4 rounded-lg border border-danger/30 bg-danger-soft p-3">
                  <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-danger">
                    <AlertTriangle className="h-4 w-4" /> Hatalı satırlar
                  </p>
                  <div className="max-h-48 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="text-text-muted">
                          <th className="py-1 pr-2">Satır</th>
                          <th className="py-1 pr-2">Hata</th>
                          <th className="py-1">Detay</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkPreview.errors.map((e: BulkCostError, i) => (
                          <tr key={i} className="border-t border-danger/20">
                            <td className="py-1 pr-2 font-mono">{e.row}</td>
                            <td className="py-1 pr-2">{translateBulkErrorCode(e.error_code)}</td>
                            <td className="py-1 text-text-secondary">{e.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {bulkPreview.preview.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-sm font-medium text-text-primary">Değişecek değerler</p>
                  <div className="max-h-64 overflow-y-auto rounded-lg border border-app-border">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-app-surface-muted">
                        <tr className="text-text-muted">
                          <th className="px-2 py-1.5">Ürün</th>
                          <th className="px-2 py-1.5">Beden</th>
                          <th className="px-2 py-1.5 text-right">Maliyet</th>
                          <th className="px-2 py-1.5 text-right">Desi</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkPreview.preview.map((p, i) => (
                          <tr key={i} className="border-t border-app-border">
                            <td className="px-2 py-1.5">{p.product_name}</td>
                            <td className="px-2 py-1.5">{p.variant_count > 1 ? `${p.variant_count} beden` : p.product_id}</td>
                            <td className="px-2 py-1.5 text-right">
                              {p.old_cost !== p.new_cost ? (
                                <>
                                  <span className="text-text-muted line-through">{formatCurrency(p.old_cost)}</span>{' '}
                                  <span className="font-medium text-text-primary">{formatCurrency(p.new_cost)}</span>
                                </>
                              ) : (
                                formatCurrency(p.old_cost)
                              )}
                            </td>
                            <td className="px-2 py-1.5 text-right">
                              {p.old_desi !== p.new_desi ? (
                                <>
                                  <span className="text-text-muted line-through">{p.old_desi}</span>{' '}
                                  <span className="font-medium text-text-primary">{p.new_desi}</span>
                                </>
                              ) : (
                                p.old_desi
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 border-t border-app-border px-6 py-4">
              <Button variant="outline" onClick={handleCancelBulkPreview} disabled={bulkBusy}>
                Vazgeç
              </Button>
              <Button variant="primary" onClick={handleApplyBulk} disabled={bulkBusy || bulkPreview.will_update === 0}>
                {bulkBusy ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
                Uygula
              </Button>
            </div>
          </div>
        </div>
      )}

      {historyProduct && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={() => setHistoryProduct(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg bg-app-surface shadow-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-app-border px-6 py-4">
              <h2 className="text-lg font-semibold text-text-primary">
                Değişiklik Geçmişi — {historyProduct.product_name}
              </h2>
              <button
                type="button"
                onClick={() => setHistoryProduct(null)}
                className="text-text-muted hover:text-text-primary"
                aria-label="Kapat"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              {historyLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
                </div>
              ) : historyError ? (
                <p className="text-sm text-danger">Geçmiş yüklenemedi. Tekrar deneyin.</p>
              ) : productHistory.length === 0 ? (
                <p className="text-sm text-text-muted">Bu ürün için henüz bir değişiklik kaydı yok (son 30 gün).</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-text-muted">
                      <th className="py-1.5 pr-2">Alan</th>
                      <th className="py-1.5 pr-2">Eski Değer</th>
                      <th className="py-1.5 pr-2">Yeni Değer</th>
                      <th className="py-1.5 pr-2">Kaynak</th>
                      <th className="py-1.5">Zaman</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productHistory.map((e, i) => (
                      <tr key={i} className="border-t border-app-border">
                        <td className="py-1.5 pr-2">{HISTORY_FIELD_LABELS[e.field] ?? e.field}</td>
                        <td className="py-1.5 pr-2 text-text-muted line-through">{formatHistoryValue(e.field, e.old_value)}</td>
                        <td className="py-1.5 pr-2 font-medium text-text-primary">{formatHistoryValue(e.field, e.new_value)}</td>
                        <td className="py-1.5 pr-2 text-text-secondary">
                          {HISTORY_SOURCE_LABELS[e.source] ?? e.source}
                          {e.variantCount > 1 && ` · ${e.variantCount} beden`}
                        </td>
                        <td className="py-1.5 text-text-secondary">{formatChangedAt(e.changed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
