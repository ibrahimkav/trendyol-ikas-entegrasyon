import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Link2, X } from 'lucide-react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

/**
 * melontik app kabuğu: sol icon-rail sidebar + üst topbar + kaydırılabilir içerik alanı.
 * Eski header-nav (AppNavigation/navConfig) bunun yerine geçti — melontik'te sidebar tabanlı
 * bir SaaS shell var, üstte yatay nav yok.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  // Global "Trendyol bağlı değil" nezaket katmanı (Pam Wave3 409 kontratı, god onayı w2c sonrası).
  // config/api.ts herhangi bir istekte 409 alınca 'store:not-connected' event fırlatıyor; burada
  // hafif, kapatılabilir bir banner gösterip kullanıcıyı Ayarlar → Trendyol API'ye yönlendiriyoruz.
  const [storeNotConnected, setStoreNotConnected] = useState(false)
  useEffect(() => {
    const handler = () => setStoreNotConnected(true)
    window.addEventListener('store:not-connected', handler)
    return () => window.removeEventListener('store:not-connected', handler)
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-app-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        {storeNotConnected && (
          <div className="flex items-center gap-3 border-b border-warning/30 bg-warning-soft px-6 py-2.5 text-sm text-warning">
            <Link2 className="h-4 w-4 shrink-0" />
            <span className="flex-1">
              Bazı veriler için Trendyol hesabınız bağlı değil.{' '}
              <Link to="/settings" className="font-semibold underline underline-offset-2" onClick={() => setStoreNotConnected(false)}>
                Ayarlar → Trendyol API'den bağlayın
              </Link>
              .
            </span>
            <button
              type="button"
              onClick={() => setStoreNotConnected(false)}
              className="shrink-0 rounded p-1 hover:bg-warning/10"
              aria-label="Kapat"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">{children}</main>
      </div>
    </div>
  )
}
