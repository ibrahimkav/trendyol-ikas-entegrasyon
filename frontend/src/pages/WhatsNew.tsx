import { Sparkles } from 'lucide-react'
import { PageHeader } from '../components/ui'

/**
 * Yenilikler `/whats-new/hepsiburada-catalog` — melontik'in en düşük öncelikli sayfası:
 * basit statik changelog (ground-truth: sidebar "Yenilikler" flyout → değişiklik günlüğü).
 * Backend gerektirmez; yeni sürüm notları buraya elle eklenir.
 */

type ChangelogEntry = {
  date: string
  version: string
  title: string
  items: string[]
  tag?: 'yeni' | 'iyileştirme' | 'düzeltme'
}

const CHANGELOG: ChangelogEntry[] = [
  {
    date: '17 Eyl 2026',
    version: 'v0.4',
    title: 'Çok mağazalı yapı ve gerçek Trendyol verisi',
    tag: 'yeni',
    items: [
      'Çok kiracılı (multi-tenant) yapı: her hesap kendi mağazalarını ve verisini görür.',
      'Mağaza başına Trendyol bağlantısı: Ayarlar’dan anahtarınızı girince ürün/sipariş/analiz verileri gerçek Trendyol hesabınızdan gelir.',
      'Hakediş & Desi Kontrolü artık gerçek komisyonu Trendyol hakediş (settlement) kayıtlarından çekip beklenenle karşılaştırıyor, hatalı kesintileri işaretliyor.',
      'Trendyol bağlı değilken ilgili sayfalar sizi nazikçe Ayarlar’a yönlendiriyor.',
    ],
  },
  {
    date: '14 Eyl 2026',
    version: 'v0.3',
    title: 'Ayarlar, Ürün Ayarları ve Raporlar',
    tag: 'yeni',
    items: [
      'Ayarlar → Trendyol/Hepsiburada API bağlama (store-connect) eklendi — gerçek satış verisi artık buradan akıyor.',
      'Ürün Ayarları: ürün başına maliyet + desi girişi (komisyon Trendyol’dan otomatik gelir).',
      'Raporlar: Sipariş / Ürün / Kategori Kârlılık + İade Zarar Analizi sayfaları.',
      'Uyarı Sayfası: düşük kâr marjı ve zararına satış uyarıları.',
    ],
  },
  {
    date: '13 Eyl 2026',
    version: 'v0.2',
    title: 'Dashboard ve Kârlılık',
    tag: 'yeni',
    items: [
      'Dashboard: 6 KPI kartı, masraf kalemleri dağılımı ve kâr performansı grafiği.',
      'Canlı Performans: bugünkü net kâr, saatlik kâr grafiği ve sipariş alan ürünler.',
      'Kâr Marjı Listesi ve Ürün Fiyatlandırma hesaplayıcısı.',
      'E-posta ile şifresiz giriş (OTP).',
    ],
  },
  {
    date: '9 Eyl 2026',
    version: 'v0.1',
    title: 'Yeni arayüz',
    tag: 'iyileştirme',
    items: [
      'Melontik tarzı yeni kenar çubuğu ve tasarım sistemi (coral tema, Poppins).',
      'Kârlılık odaklı sayfa düzenine geçiş.',
    ],
  },
]

const tagStyles: Record<NonNullable<ChangelogEntry['tag']>, string> = {
  yeni: 'bg-success-soft text-success',
  iyileştirme: 'bg-info-soft text-info',
  düzeltme: 'bg-warning-soft text-warning',
}

export default function WhatsNew() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Yenilikler" />

      <p className="text-sm text-text-secondary">
        Uygulamaya eklenen yeni özellikleri ve iyileştirmeleri buradan takip edebilirsiniz.
      </p>

      <ol className="flex flex-col gap-4">
        {CHANGELOG.map((entry) => (
          <li key={entry.version} className="rounded-lg border border-app-border bg-app-surface p-5 shadow-card">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-soft text-brand">
                <Sparkles className="h-4 w-4" />
              </span>
              <h2 className="text-base font-semibold text-text-primary">{entry.title}</h2>
              {entry.tag && (
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tagStyles[entry.tag]}`}>{entry.tag}</span>
              )}
              <span className="ml-auto text-xs text-text-muted">
                {entry.version} · {entry.date}
              </span>
            </div>
            <ul className="flex flex-col gap-1.5 pl-1">
              {entry.items.map((item, i) => (
                <li key={i} className="flex gap-2 text-sm text-text-secondary">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                  {item}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
