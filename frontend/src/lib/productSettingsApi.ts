import apiClient from '../config/api'

export type ProductSetting = {
  product_id: string
  product_name: string
  barcode: string | null
  category: string | null
  default_cost: number
  desi: number
}

export type GroupedProductSetting = {
  content_id: string | null
  product_name: string
  category: string | null
  thumbnail_url: string | null
  variant_count: number
  variant_product_ids: string[]
  price_min: number | null
  price_max: number | null
  default_cost: number
  desi: number
  cost_mixed: boolean
  desi_mixed: boolean
}

/**
 * Ürün Ayarları veri katmanı — Jim'in spec'i: kullanıcı ürün başına MALİYET + DESİ girer,
 * komisyon API'den otomatik gelir (bu sayfa komisyon girişi içermez).
 *
 * BACKEND SÖZLEŞMESİ (Pam, canlı):
 *   GET  /api/products/settings              → { products: ProductSetting[] } (beden-bazlı, ESKİ — artık sayfada kullanılmıyor, geriye dönük duruyor)
 *   PUT  /api/products/settings/{product_id} → body { default_cost, desi } (tek beden/varyant)
 *
 * w3-grouped-settings-ui (god'un tanımladığı sözleşme, Pam paralel uyguladı):
 *   GET  /api/products/settings/grouped       → { products: GroupedProductSetting[], count } — content_id (Trendyol ürün kimliği)
 *     başına TEK kayıt; aynı ürünün beden varyantları (aynı content_id, farklı barcode/product_id) tek satırda
 *     toplanır. content_id NULL olan ürünler kendi tek-varyantlı grubu olarak gelir (variant_count=1).
 *   PUT  /api/products/settings/group/{content_id} → body { default_cost, desi } → o content_id'ye sahip TÜM
 *     beden varyantlarına yazar, { updated_count } döner. content_id=null grupları için KULLANILMAZ — onlar için
 *     mevcut saveProductSetting(variant_product_ids[0], ...) kullanılır (tek varyant olduğu için).
 */

export async function fetchProductSettings(): Promise<{ products: ProductSetting[] }> {
  const res = await apiClient.get<{ products: ProductSetting[] }>('/products/settings')
  return { products: res.data.products ?? [] }
}

/** Tek ürünün maliyet+desi'sini kaydeder. */
export async function saveProductSetting(productId: string, data: { default_cost: number; desi: number }): Promise<void> {
  await apiClient.put(`/products/settings/${encodeURIComponent(productId)}`, data)
}

/** Ürün Ayarları listesini content_id (ürün) bazında gruplanmış döner — beden varyantları tek satırda. */
export async function fetchGroupedProductSettings(): Promise<{ products: GroupedProductSetting[]; count: number }> {
  const res = await apiClient.get<{ products: GroupedProductSetting[]; count: number }>('/products/settings/grouped')
  return { products: res.data.products ?? [], count: res.data.count ?? 0 }
}

/** Bir content_id'ye sahip TÜM beden varyantlarına tek seferde maliyet+desi yazar. */
export async function saveGroupedProductSetting(
  contentId: string,
  data: { default_cost: number; desi: number },
): Promise<{ updated_count: number }> {
  const res = await apiClient.put<{ updated_count: number; content_id: string }>(
    `/products/settings/group/${encodeURIComponent(contentId)}`,
    data,
  )
  return { updated_count: res.data.updated_count ?? 0 }
}

// w3-bulk-cost-ui — bkz. hive/docs/bulk-cost-csv.md (kolon/encoding/hata kodu sözleşmesi kaynağı).

export type BulkCostError = {
  row: number
  content_id: string | null
  product_id: string | null
  error_code: 'MISSING_KEY' | 'UNKNOWN_KEY' | 'INVALID_NUMBER' | 'NEGATIVE_VALUE' | string
  detail: string
}

export type BulkCostPreviewItem = {
  content_id: string | null
  product_id: string
  product_name: string
  old_cost: number
  new_cost: number
  old_desi: number
  new_desi: number
  variant_count: number
}

export type BulkCostResponse = {
  will_update: number
  skipped: number
  errors: BulkCostError[]
  error_count: number
  preview: BulkCostPreviewItem[]
  updated_groups?: number
  updated_variants?: number
}

// w3-cost-entry-followups #5 — hive/docs/cost-entry-ux-review.md: backend'in change-history ucu
// VARDI ama hiçbir sayfa tüketmiyordu. Uç sadece {product_id, field, old_value, new_value, source,
// changed_at} döndürüyor (backend/routers/products.py:441-480'den doğrudan okundu) — "kim" alanı
// YOK, uydurma bir kolon EKLENMEDİ.
export type ChangeHistoryEntry = {
  product_id: string
  field: string
  old_value: number | null
  new_value: number | null
  source: string
  changed_at: string | null
}

/** Son 30 günün maliyet/desi/fiyat değişim geçmişi (mağaza geneli) — çağıran client-side product_id'ye göre filtreler. */
export async function fetchChangeHistory(): Promise<ChangeHistoryEntry[]> {
  const res = await apiClient.get<{ changes: ChangeHistoryEntry[] }>('/products/change-history', {
    params: { limit: 500 },
  })
  return res.data.changes ?? []
}

/** Şablon CSV'yi indirir ve tarayıcıda dosya olarak kaydettirir (utf-8-sig, ; ayraçlı — backend üretir). */
export async function downloadProductSettingsTemplate(): Promise<void> {
  const res = await apiClient.get('/products/settings/template.csv', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', 'urun-ayarlari-sablon.csv')
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Kullanıcının doldurduğu CSV'yi yükler. dryRun=true iken hiçbir yazma olmaz, sadece önizleme döner
 * (bkz. spec: dry_run cevap şeması). dryRun=false iken satır-bazlı kısmi başarı ile gerçekten yazar.
 */
export async function bulkUploadProductSettingsCsv(file: File, dryRun: boolean): Promise<BulkCostResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await apiClient.post<BulkCostResponse>('/products/settings/bulk', formData, {
    params: { dry_run: dryRun },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}
