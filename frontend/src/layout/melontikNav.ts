import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Calculator,
  FileText,
  LayoutDashboard,
  Megaphone,
  Percent,
  QrCode,
  Scale,
  Settings,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react'

/**
 * Gerçek melontik sidebar nav sırası — kaynak: hive/research/melontik-screens.md
 * (god'ın canlı browser turu, Hepsiburada demo mağazası). /buybox ve
 * /market-intelligence/* bu demoda görünmüyor, Phyllis'in ux-ia kararına kadar
 * sidebar'a eklenmedi.
 */

export type NavChild = { label: string; path: string }
export type NavLeaf = { kind: 'leaf'; id: string; label: string; path: string; icon: LucideIcon }
export type NavGroup = { kind: 'group'; id: string; label: string; icon: LucideIcon; children: NavChild[] }
export type NavEntry = NavLeaf | NavGroup

export const sidebarNav: NavEntry[] = [
  { kind: 'leaf', id: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { kind: 'leaf', id: 'live-performance', label: 'Canlı Performans', path: '/live-performance', icon: Activity },
  {
    kind: 'group',
    id: 'campaign',
    label: 'Kampanya',
    icon: Megaphone,
    children: [
      { label: 'Kendi Kampanyanı Oluştur', path: '/campaign/build-your-campaign' },
      { label: 'Avantajlı Teklifler', path: '/campaign/offers' },
      { label: 'Sepet Kampanyaları', path: '/campaign/basket-campaigns' },
    ],
  },
  {
    kind: 'group',
    id: 'reports',
    label: 'Raporlar',
    icon: BarChart3,
    children: [
      { label: 'Sipariş Kârlılık Analizi', path: '/reports/order-profitability-analysis' },
      { label: 'Ürün Kârlılık Analizi', path: '/reports/product-profitability-analysis' },
      { label: 'Kategori Kârlılık Analizi', path: '/reports/category-profitability-analysis' },
      { label: 'İade Zarar Analizi', path: '/reports/return-loss-analysis' },
    ],
  },
  { kind: 'leaf', id: 'profit-margin-list', label: 'Kâr Marjı Listesi', path: '/profit-margin-list', icon: Percent },
  { kind: 'leaf', id: 'product-pricing', label: 'Ürün Fiyatlandırma', path: '/product-pricing', icon: Calculator },
  { kind: 'leaf', id: 'product-settings', label: 'Ürün Ayarları', path: '/product-settings', icon: Sliders },
  { kind: 'leaf', id: 'warning-page', label: 'Uyarı Sayfası', path: '/warning-page', icon: AlertTriangle },
  { kind: 'leaf', id: 'entitlement', label: 'Hakediş & Desi Kontrolü', path: '/entitlement', icon: Scale },
  { kind: 'leaf', id: 'settings', label: 'Ayarlar', path: '/settings', icon: Settings },
  {
    kind: 'group',
    id: 'whats-new',
    label: 'Yenilikler',
    icon: Sparkles,
    children: [{ label: 'Hepsiburada Katalog Geliştirmesi', path: '/whats-new/hepsiburada-catalog' }],
  },
]

/**
 * İnsan kararı (god'ın 2026-09-12T21-31-17 mesajı): Barkod + Sipariş Okut günlük operasyon için
 * kritik, Phyllis'in KEEP-HIDDEN kararı bu ikisi için override edildi — ana icon-rail'e, melontik
 * sırasını bozmadan, kendi küçük ayracıyla eklendi (bkz. Sidebar.tsx — sidebarNav'dan sonra,
 * "Diğer Araçlar"dan önce ayrı render ediliyor).
 */
export const operationalNav: NavLeaf[] = [
  { kind: 'leaf', id: 'auto-barcode', label: 'Barkod', path: '/auto-barcode', icon: Zap },
  { kind: 'leaf', id: 'order-scanner', label: 'Sipariş Okut', path: '/order-scanner', icon: QrCode },
  { kind: 'leaf', id: 'ikas-invoices', label: 'ikas Faturaları', path: '/ikas-invoices', icon: FileText },
]

/**
 * "Diğer Araçlar" — Phyllis w1-ux-disposition.md §3: 15 KEEP-HIDDEN trendyol sayfası (Notifications
 * topbar zili + Barkod/Sipariş Okut artık ana sidebar'da olduğu için 17'den 15'e düştü) gerçek
 * melontik nav'ında yer almıyor ama silinmiyor; sidebar'ın en altında, coral aileden görsel olarak
 * AYRIK (nötr gri), tek bir "Diğer Araçlar" ikonu altında gruplanmış flyout ile erişilebilir kalıyor.
 */
export type OtherToolsGroup = { label: string; items: NavChild[] }

export const otherToolsGroups: OtherToolsGroup[] = [
  {
    label: 'Sipariş & Lojistik',
    items: [
      { label: 'Siparişler', path: '/orders' },
      { label: 'Kargo', path: '/cargo' },
      { label: 'İade', path: '/returns' },
    ],
  },
  {
    label: 'Ürün & Stok',
    items: [
      { label: 'Ürün Yönetimi', path: '/product-management' },
      { label: 'Stok', path: '/inventory' },
      { label: 'Görseller', path: '/images' },
      { label: 'Görsel Eşleştirme', path: '/product-image-mapping' },
      { label: 'SEO', path: '/seo-optimization' },
      { label: 'Toplu İşlem', path: '/bulk-operations' },
      { label: 'Export/Import', path: '/export-import' },
    ],
  },
  {
    label: 'Müşteri & Pazarlama',
    items: [
      { label: 'Müşteriler', path: '/customers' },
      { label: 'Müşteri Soruları', path: '/customer-qa' },
      { label: 'Segmentasyon', path: '/customer-segmentation' },
    ],
  },
  {
    label: 'Diğer',
    items: [
      { label: 'Finansal Yönetim', path: '/financial' },
      { label: 'Otomasyon', path: '/automation' },
    ],
  },
]

/** path -> topbar sayfa başlığı */
export const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/old-dashboard': 'Basit Dashboard',
  '/live-performance': 'Canlı Performans',
  '/campaign/build-your-campaign': 'Kendi Kampanyanı Oluştur',
  '/campaign/offers': 'Avantajlı Teklifler',
  '/campaign/basket-campaigns': 'Sepet Kampanyaları',
  '/reports/order-profitability-analysis': 'Sipariş Kârlılık Analizi',
  '/reports/product-profitability-analysis': 'Ürün Kârlılık Analizi',
  '/reports/category-profitability-analysis': 'Kategori Kârlılık Analizi',
  '/reports/return-loss-analysis': 'İade Zarar Analizi',
  '/profit-margin-list': 'Kâr Marjı Listesi',
  '/product-pricing': 'Ürün Fiyatlandırma',
  '/product-settings': 'Ürün Ayarları',
  '/warning-page': 'Uyarı Sayfası',
  '/entitlement': 'Hakediş & Desi Kontrolü',
  '/settings': 'Ayarlar',
  '/whats-new/hepsiburada-catalog': 'Hepsiburada Katalog Geliştirmesi',
  // Diğer Araçlar (keep-hidden) + Wave2 bekleyen eski route'lar
  '/orders': 'Siparişler',
  '/order-scanner': 'Sipariş Tarama',
  '/cargo': 'Kargo',
  '/returns': 'İade',
  '/inventory': 'Stok',
  '/product-management': 'Ürün Yönetimi',
  '/auto-barcode': 'Otomatik Barkod',
  '/images': 'Görseller',
  '/product-image-mapping': 'Görsel Eşleştirme',
  '/seo-optimization': 'SEO',
  '/bulk-operations': 'Toplu İşlem',
  '/export-import': 'Export/Import',
  '/customers': 'Müşteriler',
  '/customer-qa': 'Müşteri Soruları',
  '/customer-segmentation': 'Segmentasyon',
  '/automation': 'Otomasyon',
  '/financial': 'Finansal Yönetim',
  '/notifications': 'Bildirimler',
  '/reports': 'Raporlar',
  '/campaigns': 'Kampanya',
}
