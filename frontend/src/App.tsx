import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import AppShell from './layout/AppShell'
import PageLoader from './components/PageLoader'
import ComingSoon from './components/ComingSoon'
import Login from './pages/auth/Login'
import { AuthProvider, useAuth } from './context/AuthContext'

// --- melontik core (sidebar nav'da yer alan sayfalar) ---
const Dashboard = lazy(() => import('./components/Dashboard'))
const StorePerformance = lazy(() => import('./components/StorePerformance')) // Canlı Performans
const ProfitMarginList = lazy(() => import('./pages/ProfitMarginList')) // Kâr Marjı Listesi (Ryan, w2a-ryan)
const ProductPricing = lazy(() => import('./pages/ProductPricing')) // Ürün Fiyatlandırma (Ryan, w2a-ryan) — PriceHistory'yi "Geçmiş" sekmesi olarak kendi içinde gömüyor
const ProductSettings = lazy(() => import('./pages/ProductSettings')) // Ürün Ayarları — maliyet+desi giriş (Oscar, w2b)
const Settings = lazy(() => import('./pages/Settings')) // Ayarlar — store-connect (Oscar, w2b)
// Raporlar×4 + Uyarı Sayfası (Ryan, w2b-ryan) — ReportShell 'Rapor Seçin' dropdown'ı 4 route arası navigate eder
const OrderProfitabilityReport = lazy(() => import('./pages/reports/OrderProfitabilityReport'))
const ProductProfitabilityReport = lazy(() => import('./pages/reports/ProductProfitabilityReport'))
const CategoryProfitabilityReport = lazy(() => import('./pages/reports/CategoryProfitabilityReport'))
const ReturnLossReport = lazy(() => import('./pages/reports/ReturnLossReport'))
const WarningPage = lazy(() => import('./pages/WarningPage'))
const WhatsNew = lazy(() => import('./pages/WhatsNew')) // Yenilikler — statik changelog (Oscar, w2c)
const IkasInvoices = lazy(() => import('./pages/IkasInvoices')) // ikas siparişleri → Trendyol E-Faturam faturası
// Hakediş & Desi + Kampanya×3 (Ryan, w2c-ryan) — CampaignTabs 3 kampanya route'u arası gezinir
const EntitlementReconciliation = lazy(() => import('./pages/EntitlementReconciliation'))
const BuildYourCampaign = lazy(() => import('./pages/campaigns/BuildYourCampaign'))
const OfferCampaigns = lazy(() => import('./pages/campaigns/OfferCampaigns'))
const BasketCampaigns = lazy(() => import('./pages/campaigns/BasketCampaigns'))

// Eski trendyol Finansal Yönetim — /entitlement artık gerçek Hakediş&Desi sayfası (Ryan) olduğu için
// bu superseded bileşen Diğer Araçlar'dan /financial ile erişilebilir kalıyor (silmeden, keep-hidden).
const FinancialManagement = lazy(() => import('./components/FinancialManagement'))

// --- trendyol "Diğer Araçlar" (Phyllis w1-ux-disposition.md: 17 KEEP-HIDDEN sayfa — silinmez,
// yeni dar sidebar'da görünmez, alttaki "Diğer Araçlar" flyout'undan erişilir) ---
const AutoBarcodeGenerator = lazy(() => import('./components/AutoBarcodeGenerator'))
const Notifications = lazy(() => import('./components/Notifications'))
const CargoTracking = lazy(() => import('./components/CargoTracking'))
const Customers = lazy(() => import('./components/Customers'))
const CustomerQA = lazy(() => import('./components/CustomerQA'))
const InventoryManagement = lazy(() => import('./components/InventoryManagement'))
const AutomationRules = lazy(() => import('./components/AutomationRules'))
const BulkOperations = lazy(() => import('./components/BulkOperations'))
const Returns = lazy(() => import('./components/Returns'))
const ExportImport = lazy(() => import('./components/ExportImport'))
const ImageManagement = lazy(() => import('./components/ImageManagement'))
const SEOOptimization = lazy(() => import('./components/SEOOptimization'))
const CustomerSegmentation = lazy(() => import('./components/CustomerSegmentation'))
const OrderScanner = lazy(() => import('./components/OrderScanner'))
const ProductImageMapping = lazy(() => import('./components/ProductImageMapping'))
const OrdersList = lazy(() => import('./components/OrdersList'))
const OrderDetailPage = lazy(() => import('./components/OrderDetailPage'))
// Orphan karar (god w2c #4): eski ProductManagement silinmiyor, Diğer Araçlar'a trendyol-native
// ürün yönetimi olarak /product-management path'iyle eklendi (Ürün Ayarları /product-settings'ten ayrı).
const ProductManagement = lazy(() => import('./components/ProductManagement'))

// --- Wave2 bekliyor: Reports/Campaigns MAPS-TO'ları (disposition #5, #7) tek monolitik bileşen
// olduğu için 4/3 alt-route'a gerçek içerik bölünmesi gerekiyor (page-body işi, Wave1 kapsamı dışı).
// Aşağıdaki ComingSoon placeholder'lar o alt-route'ları tutuyor; eski bileşenler bu ayrım
// yapılana kadar orijinal URL'lerinde erişilebilir kalıyor (regresyon yok).
const Reports = lazy(() => import('./components/Reports'))
const Campaigns = lazy(() => import('./components/Campaigns'))

/** Token yoksa /login'e yönlendirir (dönüş yolunu state'te taşır). hive/agents/pam-mttzdxq5/w1-backend-auth-notes.md */
function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) return <PageLoader />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppShell>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  {/* melontik sidebar sırasıyla (kaynak: hive/research/melontik-screens.md) */}
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/old-dashboard" element={<ComingSoon title="Basit Dashboard" />} />
            <Route path="/live-performance" element={<StorePerformance />} />

            {/* Kampanya×3 (Ryan, w2c-ryan) — CampaignTabs bu 3 route arası gezinir */}
            <Route path="/campaign/build-your-campaign" element={<BuildYourCampaign />} />
            <Route path="/campaign/offers" element={<OfferCampaigns />} />
            <Route path="/campaign/basket-campaigns" element={<BasketCampaigns />} />

            {/* Raporlar×4 (Ryan, w2b-ryan) — ReportShell dropdown'ı bu 4 route arası navigate eder */}
            <Route path="/reports/order-profitability-analysis" element={<OrderProfitabilityReport />} />
            <Route path="/reports/product-profitability-analysis" element={<ProductProfitabilityReport />} />
            <Route path="/reports/category-profitability-analysis" element={<CategoryProfitabilityReport />} />
            <Route path="/reports/return-loss-analysis" element={<ReturnLossReport />} />

            <Route path="/profit-margin-list" element={<ProfitMarginList />} />
            {/* İsim çakışması çözüldü: eski /pricing -> /product-pricing. Bileşen artık pages/ProductPricing.tsx
                (Ryan, w2a-ryan) — eski components/PricingAssistant.tsx silindi, bkz. commit notu. */}
            <Route path="/product-pricing" element={<ProductPricing />} />
            {/* Ürün Ayarları — Jim spec: maliyet+desi giriş (Oscar w2b). Eski ProductManagement
                artık burada değil; melontik'in Ürün Ayarları'ı bu yeni sayfa. */}
            <Route path="/product-settings" element={<ProductSettings />} />
            <Route path="/warning-page" element={<WarningPage />} />
            {/* Hakediş & Desi Kontrolü — gerçek reconciliation sayfası (Ryan, w2c-ryan). Eski
                FinancialManagement /financial'a taşındı (Diğer Araçlar). */}
            <Route path="/entitlement" element={<EntitlementReconciliation />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/whats-new/hepsiburada-catalog" element={<WhatsNew />} />

            {/* "Diğer Araçlar" flyout — 16 KEEP-HIDDEN sayfa (+ Notifications topbar zili = 17) */}
            <Route path="/auto-barcode" element={<AutoBarcodeGenerator />} />
            <Route path="/order-scanner" element={<OrderScanner />} />
            <Route path="/ikas-invoices" element={<IkasInvoices />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/cargo" element={<CargoTracking />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/customer-qa" element={<CustomerQA />} />
            <Route path="/inventory" element={<InventoryManagement />} />
            <Route path="/product-management" element={<ProductManagement />} />
            <Route path="/financial" element={<FinancialManagement />} />
            <Route path="/automation" element={<AutomationRules />} />
            <Route path="/bulk-operations" element={<BulkOperations />} />
            <Route path="/returns" element={<Returns />} />
            <Route path="/export-import" element={<ExportImport />} />
            <Route path="/images" element={<ImageManagement />} />
            <Route path="/product-image-mapping" element={<ProductImageMapping />} />
            <Route path="/seo-optimization" element={<SEOOptimization />} />
            <Route path="/customer-segmentation" element={<CustomerSegmentation />} />
            <Route path="/orders/:orderId" element={<OrderDetailPage />} />
            <Route path="/orders" element={<OrdersList />} />

            {/* Wave2 bekliyor (MAPS-TO, henüz bölünmedi) — nav'da yok, doğrudan URL ile erişilebilir */}
            <Route path="/reports" element={<Reports />} />
            <Route path="/campaigns" element={<Campaigns />} />

                  {/* DROP (Phyllis w1-ux-disposition.md #8): /price-history standalone route kaldırıldı,
                      işlevi Wave2'de /product-pricing içine "Geçmiş" sekmesi olarak gömülecek. Bileşen
                      dosyası (components/PriceHistory.tsx) korunuyor, sadece route'u yok. */}
                </Routes>
              </Suspense>
            </AppShell>
          </AuthGuard>
        }
      />
    </Routes>
  )
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  )
}

export default App
