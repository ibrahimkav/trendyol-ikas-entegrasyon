import CampaignListPage, { type CampaignRow } from './CampaignListPage'

// Sepet Kampanyaları — sepet düzeyinde indirim (X Al Y Öde / sepet tutarına %). Kâr-etkisi ürün başına
// değil, tipik sepet kompozisyonu varsayımı gerektirir (Jim §2.2, düşük-orta güven). Örnek veri.
const MOCK_BASKET: CampaignRow[] = [
  { id: 'basket-1', name: '3 Al 2 Öde (Kozmetik)', discountLabel: '3 Al 2 Öde', dateRange: '1–15 Eyl 2026', currentProfit: 5400, campaignProfit: 3980, campaignMarginPct: 18.2 },
  { id: 'basket-2', name: 'Sepette %20 (₺500 üzeri)', discountLabel: '%20 (min ₺500)', dateRange: '8–22 Eyl 2026', currentProfit: 3120, campaignProfit: 2450, campaignMarginPct: 15.6 },
  { id: 'basket-3', name: '2. Ürüne %50', discountLabel: '2. ürün %50', dateRange: '10–17 Eyl 2026', currentProfit: 1890, campaignProfit: 1180, campaignMarginPct: 9.4 },
]

export default function BasketCampaigns() {
  return (
    <CampaignListPage
      title="Sepet Kampanyaları"
      breadcrumbLabel="Sepet Kampanyaları"
      emptyMessage="Şu an aktif sepet kampanyası yok."
      mockRows={MOCK_BASKET}
    />
  )
}
