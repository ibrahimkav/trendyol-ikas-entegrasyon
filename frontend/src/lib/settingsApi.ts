import apiClient from '../config/api'
import { getActiveStoreId } from './auth'

export type Platform = 'trendyol' | 'hepsiburada'

export type StoreCredential = {
  platform: Platform
  supplier_id: string | null
  api_key_preview: string
  is_connected: boolean
  connected_at: string | null
}

/**
 * Store-connect API — backend sözleşmesi: hive/agents/pam-mttzdxq5/w1-backend-auth-notes.md.
 * Ham api_key/secret ASLA geri dönmez (sadece maskelenmiş api_key_preview). Aktif mağaza id'si
 * lib/auth.ts'ten alınır; endpoint'ler yine de auth + sahiplik doğrulaması yapar.
 */
function requireStoreId(): string {
  const id = getActiveStoreId()
  if (!id) throw new Error('no-active-store')
  return id
}

export async function fetchCredentials(): Promise<StoreCredential[]> {
  const storeId = requireStoreId()
  const res = await apiClient.get<StoreCredential[]>(`/settings/stores/${storeId}/credentials`)
  return res.data
}

export async function connectCredential(body: {
  platform: Platform
  supplier_id?: string
  api_key: string
  api_secret: string
}): Promise<StoreCredential> {
  const storeId = requireStoreId()
  const res = await apiClient.post<StoreCredential>(`/settings/stores/${storeId}/credentials`, body)
  return res.data
}

export async function disconnectCredential(platform: Platform): Promise<void> {
  const storeId = requireStoreId()
  await apiClient.delete(`/settings/stores/${storeId}/credentials/${platform}`)
}

// w3-thresholds-ui — bkz. hive/docs/thresholds-spec.md (alan/sınır/response şeması kaynağı).

export type ThresholdField = 'margin_warning_threshold' | 'low_stock_floor' | 'low_stock_sales_ratio'

export type Thresholds = {
  margin_warning_threshold: number
  low_stock_floor: number
  low_stock_sales_ratio: number
  is_customized: Record<ThresholdField, boolean>
}

export async function fetchThresholds(): Promise<Thresholds> {
  const res = await apiClient.get<Thresholds>('/settings/thresholds')
  return res.data
}

/** Kısmi güncelleme — sadece bu alan değişir, diğer ikisi dokunulmadan kalır (spec'teki sözleşme). */
export async function saveThreshold(field: ThresholdField, value: number): Promise<Thresholds> {
  const res = await apiClient.put<Thresholds>('/settings/thresholds', { [field]: value })
  return res.data
}

/** Alanı özelleştirmeden çıkarır (NULL'a çeker, varsayılana döner) — 2026-09-27'de eklenen gerçek reset yolu. */
export async function resetThreshold(field: ThresholdField): Promise<Thresholds> {
  const res = await apiClient.delete<Thresholds>(`/settings/thresholds/${field}`)
  return res.data
}
