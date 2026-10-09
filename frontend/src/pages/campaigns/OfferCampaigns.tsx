import CampaignListPage, { type CampaignRow } from './CampaignListPage'

// Avantajlı Teklifler — Trendyol'un davet ettiği, genelde komisyon desteği içeren kampanyalar.
// Kâr-etkisinde iki kaldıraç (indirimli fiyat + Trendyol komisyon karşılaması) var (Jim §2.2, orta güven).
const MOCK_OFFERS: CampaignRow[] = [
  { id: 'offer-1', name: 'Trendyol Yaz Fırsatları', discountLabel: '%15 (komisyon desteği %5)', dateRange: '1–30 Eyl 2026', currentProfit: 4820, campaignProfit: 3960, campaignMarginPct: 21.4 },
  { id: 'offer-2', name: 'Hızlı Teslimat Rozeti Kampanyası', discountLabel: '%10', dateRange: '5–20 Eyl 2026', currentProfit: 2140, campaignProfit: 1610, campaignMarginPct: 14.8 },
  { id: 'offer-3', name: 'Flash İndirim (Elektronik)', discountLabel: '₺50/ürün', dateRange: '12–14 Eyl 2026', currentProfit: 980, campaignProfit: -120, campaignMarginPct: -3.1 },
]

export default function OfferCampaigns() {
  return (
    <CampaignListPage
      title="Avantajlı Teklifler"
      breadcrumbLabel="Avantajlı Teklifler"
      emptyMessage="Şu an uygun avantajlı teklif yok."
      mockRows={MOCK_OFFERS}
    />
  )
}
