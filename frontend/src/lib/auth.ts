import apiClient from '../config/api'

export type AuthUser = { id: string; email: string }
export type AuthStore = { id: string; store_name: string; is_active: boolean }

const TOKEN_KEY = 'auth_token'
const STORE_ID_KEY = 'active_store_id'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(STORE_ID_KEY)
}

/**
 * JWT'nin store_id claim'i sadece login anındaki mağaza durumunu yansıtır (backend/security.py
 * get_current_store) — sonradan mağaza eklenirse (ör. verifyPin'in otomatik oluşturduğu demo
 * mağaza) token GÜNCELLENMEZ. Backend bu yüzden X-Store-Id header'ını öncelikli okuyor; burada
 * onu client-side saklayıp api.ts'in her isteğe eklemesini sağlıyoruz.
 */
export function getActiveStoreId(): string | null {
  return localStorage.getItem(STORE_ID_KEY)
}

export function setActiveStoreId(storeId: string) {
  localStorage.setItem(STORE_ID_KEY, storeId)
}

export function isAuthenticated(): boolean {
  return Boolean(getToken())
}

export async function requestPin(email: string): Promise<{ debug_code?: string }> {
  const res = await apiClient.post('/auth/request-pin', { email })
  return res.data
}

export async function verifyPin(email: string, code: string) {
  const res = await apiClient.post<{
    access_token: string
    token_type: string
    user: AuthUser
    stores: AuthStore[]
  }>('/auth/verify-pin', { email, code })
  setToken(res.data.access_token)

  // İlk girişte hiç mağaza yoksa (yeni kullanıcı) gerçek store-connect endpoint'iyle bir
  // varsayılan mağaza oluşturuyoruz — böylece login sonrası sidebar'ın tamamı hemen görülebilir
  // (god'ın w2a-oscar runtime-doğrulama talebi), ayrı bir sahte "demo bypass" eklemeden — bu
  // POST /settings/stores gerçek endpoint'i, gerçek bir satır oluşturuyor. Gerçek Trendyol/HB
  // bağlantısı hâlâ Ayarlar'dan elle yapılmalı, bu sadece boş-mağaza duvarını kaldırıyor.
  if (res.data.stores.length === 0) {
    try {
      const store = await apiClient.post<AuthStore>('/settings/stores', { store_name: 'Demo Mağaza' })
      res.data.stores = [store.data]
    } catch {
      // Olmazsa olsun — kullanıcı normal akışta Ayarlar'dan mağaza ekleyebilir.
    }
  }

  // JWT'nin store_id claim'i login anında (yukarıdaki auto-create'ten ÖNCE) belirlendiği için
  // güncel olmayabilir — X-Store-Id header'ı ile açıkça override ediyoruz (bkz. yukarıdaki not).
  if (res.data.stores.length > 0) {
    setActiveStoreId(res.data.stores[0].id)
  }

  return res.data
}

export async function fetchMe() {
  const res = await apiClient.get<{ id: string; email: string; is_active: boolean; stores: AuthStore[] }>('/auth/me')
  if (res.data.stores.length > 0 && !getActiveStoreId()) {
    setActiveStoreId(res.data.stores[0].id)
  }
  return res.data
}

export function logout() {
  clearToken()
}
