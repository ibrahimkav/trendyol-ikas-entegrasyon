// API Configuration
import axios from 'axios'

function resolveApiBaseUrl(): string {
  const env = (import.meta as any).env
  const fromEnv = env?.VITE_API_BASE_URL as string | undefined
  if (fromEnv) return fromEnv.replace(/\/$/, '')

  if (env?.DEV) {
    // Aynı origin (Vite proxy → backend). Telefondan https://IP:3000 ile de çalışır.
    return '/api'
  }

  // Production: API genelde aynı host üzerinden reverse proxy ile veya VITE_API_BASE_URL ile
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api`
  }
  return '/api'
}

const API_BASE_URL = resolveApiBaseUrl()

// Axios instance oluştur
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 saniye timeout
})

// Request interceptor — auth token + aktif mağaza varsa header'lara ekle.
// X-Store-Id: backend/security.py get_current_store JWT'nin store_id claim'inden ÖNCE bunu okur —
// login sonrası mağaza oluşturulmuş/değiştirilmiş olsa bile token'ı yenilemeden doğru mağazayı hedefler.
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
    }
    const storeId = localStorage.getItem('active_store_id')
    if (storeId) {
      config.headers = config.headers ?? {}
      config.headers['X-Store-Id'] = storeId
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - hata yönetimi
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401: token geçersiz/süresi dolmuş — temizle, AuthGuard bir sonraki render'da /login'e yönlendirir
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.dispatchEvent(new Event('auth:unauthorized'))
    }

    // 409: mağaza Trendyol anahtarını bağlamamış (Pam Wave3 kontratı) — 401'DEN AYRI ele alınır.
    // Logout DEĞİL; kullanıcıyı Ayarlar → Trendyol API bağlama akışına nazikçe yönlendir (global banner).
    if (error.response?.status === 409) {
      window.dispatchEvent(new Event('store:not-connected'))
    }

    // Bağlantı hatalarını daha iyi handle et
    if (error.code === 'ECONNREFUSED' || error.code === 'ECONNRESET') {
      console.error('Backend server çalışmıyor! http://localhost:8000 adresini kontrol edin.')
      // Kullanıcıya daha anlaşılır hata mesajı göster
      error.userMessage = 'Backend sunucusu çalışmıyor. Lütfen backend\'i başlatın.'
    } else if (error.code === 'ETIMEDOUT' || error.message?.includes('timeout')) {
      console.error('Backend yanıt vermiyor (timeout)')
      error.userMessage = 'Backend sunucusu yanıt vermiyor. Lütfen tekrar deneyin.'
    } else if (error.response) {
      // HTTP hata yanıtı
      console.error('API Error:', error.response.status, error.response.data)
      error.userMessage = error.response.data?.detail || error.response.data?.message || 'Bir hata oluştu'
    } else if (error.request) {
      // İstek gönderildi ama yanıt alınamadı
      console.error('API Request Error:', error.request)
      error.userMessage = 'Sunucuya bağlanılamıyor. Lütfen internet bağlantınızı kontrol edin.'
    } else {
      // İstek hazırlanırken hata oluştu
      console.error('API Error:', error.message)
      error.userMessage = error.message || 'Bilinmeyen bir hata oluştu'
    }
    
    return Promise.reject(error)
  }
)

type RetryConfig = { __retryCount?: number }

/** GET istekleri: kısa ağ kesintilerinde en fazla 2 kez yeniden dener (yanıt interceptor zincirinde önce çalışır). */
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as typeof error.config & RetryConfig
    if (!config?.url) return Promise.reject(error)
    const method = (config.method || 'get').toLowerCase()
    if (method !== 'get') return Promise.reject(error)

    const count = config.__retryCount ?? 0
    if (count >= 2) return Promise.reject(error)

    const msg = typeof error.message === 'string' ? error.message : ''
    const retryable =
      error.code === 'ECONNRESET' ||
      error.code === 'ECONNREFUSED' ||
      error.code === 'ETIMEDOUT' ||
      error.code === 'ERR_NETWORK' ||
      msg.includes('timeout')

    if (!retryable) return Promise.reject(error)

    config.__retryCount = count + 1
    await new Promise((r) => setTimeout(r, 350 * config.__retryCount!))
    return apiClient.request(config)
  }
)

export default apiClient

