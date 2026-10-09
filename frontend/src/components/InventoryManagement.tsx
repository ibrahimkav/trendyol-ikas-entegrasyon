import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import {
  Package,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Search,
  Filter,
  Lightbulb,
  ShoppingCart,
  Zap,
  HelpCircle,
  Info
} from 'lucide-react'

interface ProductStock {
  product_id: string
  product_name: string
  current_stock: number
  min_stock_level: number
  status: 'in_stock' | 'low_stock' | 'out_of_stock'
  last_updated: string
  category?: string
  barcode?: string
  total_sales_90days?: number
  days_since_last_sale?: number
  is_real_stock?: boolean
}

type EffectiveStatus = 'in_stock' | 'low_stock' | 'out_of_stock' | 'unknown'

// is_real_stock=false demek: stok Trendyol API'sinden değil, sipariş geçmişinden
// tahmin edildi. Bu tahmin 0'a düşebilir (ör. tüm siparişler "bugün" tarihli) — bu,
// stoğun gerçekten tükendiği anlamına gelmez, sadece bilinmediği anlamına gelir.
const getEffectiveStatus = (product: ProductStock): EffectiveStatus => {
  if (product.is_real_stock === false) return 'unknown'
  return product.status
}

interface StockSummary {
  total_products: number
  in_stock_count: number
  low_stock_count: number
  out_of_stock_count: number
  alert_percentage: number
}

interface StockRecommendation {
  id: number
  product_id: string
  product_name: string
  current_stock: number
  recommended_quantity: number
  recommendation_reason: string | null
  urgency_level: 'low' | 'medium' | 'high' | 'critical'
  estimated_cost: number
  estimated_arrival_days: number
  is_ordered: boolean
  created_at: string
}

type TabType = 'stock' | 'recommendations'

export default function InventoryManagement() {
  const [products, setProducts] = useState<ProductStock[]>([])
  const [summary, setSummary] = useState<StockSummary | null>(null)
  const [recommendations, setRecommendations] = useState<StockRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'in_stock' | 'low_stock' | 'out_of_stock' | 'unknown'>('all')
  const [activeTab, setActiveTab] = useState<TabType>('stock')
  const [generatingRecommendations, setGeneratingRecommendations] = useState(false)

  useEffect(() => {
    fetchInventoryData()
    if (activeTab === 'recommendations') {
      fetchRecommendations()
    }
  }, [activeTab])

  const fetchInventoryData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [productsRes, summaryRes] = await Promise.allSettled([
        apiClient.get('/inventory/products?include_out_of_stock=true'),
        apiClient.get('/inventory/summary')
      ])

      if (productsRes.status === 'fulfilled') {
        const data = productsRes.value.data
        setProducts(data.products || [])
        
        // Debug bilgisi varsa göster
        if (data.debug_info) {
          console.log('[Inventory] Debug:', data.debug_info)
        }
        
        // Eğer ürün yoksa ama sipariş varsa, bilgilendir
        if ((data.products || []).length === 0 && data.debug_info?.orders_processed > 0) {
          setError('Siparişler bulundu ancak ürün bilgileri çıkarılamadı. Sipariş yapısı kontrol ediliyor.')
        } else if ((data.products || []).length === 0) {
          setError('Henüz stok verisi yok. Siparişler geldikçe ürünler görünecek.')
        }
      } else {
        setError('Stok verileri yüklenemedi: ' + (productsRes.reason?.response?.data?.detail || productsRes.reason?.message || 'Bilinmeyen hata'))
      }

      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value.data)
      }
    } catch (err: any) {
      setError('Stok verileri yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchRecommendations = async () => {
    try {
      const response = await apiClient.get('/inventory/recommendations')
      setRecommendations(response.data || [])
    } catch (err: any) {
      console.error('Öneriler yüklenemedi:', err)
    }
  }

  const generateRecommendations = async () => {
    try {
      setGeneratingRecommendations(true)
      await apiClient.post('/inventory/recommendations/generate')
      await fetchRecommendations()
      setError(null)
    } catch (err: any) {
      setError('Öneriler oluşturulamadı: ' + (err.response?.data?.detail || err.message))
    } finally {
      setGeneratingRecommendations(false)
    }
  }

  const markRecommendationOrdered = async (recommendationId: number) => {
    try {
      await apiClient.post(`/inventory/recommendations/${recommendationId}/order`)
      await fetchRecommendations()
    } catch (err: any) {
      setError('Öneri güncellenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getUrgencyLabel = (urgency: string) => {
    switch (urgency) {
      case 'critical':
        return 'Kritik'
      case 'high':
        return 'Yüksek'
      case 'medium':
        return 'Orta'
      case 'low':
        return 'Düşük'
      default:
        return urgency
    }
  }

  const getStatusIcon = (status: EffectiveStatus) => {
    switch (status) {
      case 'in_stock':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case 'low_stock':
        return <AlertTriangle className="w-5 h-5 text-yellow-600" />
      case 'out_of_stock':
        return <XCircle className="w-5 h-5 text-red-600" />
      case 'unknown':
        return <HelpCircle className="w-5 h-5 text-gray-400" />
      default:
        return <Package className="w-5 h-5 text-gray-400" />
    }
  }

  const getStatusText = (status: EffectiveStatus) => {
    switch (status) {
      case 'in_stock':
        return 'Stokta Var'
      case 'low_stock':
        return 'Düşük Stok'
      case 'out_of_stock':
        return 'Stokta Yok'
      case 'unknown':
        return 'Stok Bilinmiyor'
      default:
        return 'Bilinmeyen'
    }
  }

  const getStatusColor = (status: EffectiveStatus) => {
    switch (status) {
      case 'in_stock':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'low_stock':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'out_of_stock':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'unknown':
        return 'bg-gray-100 text-gray-600 border-gray-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.product_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (product.barcode && product.barcode.toLowerCase().includes(searchTerm.toLowerCase()))

    const matchesStatus = statusFilter === 'all' || getEffectiveStatus(product) === statusFilter

    return matchesSearch && matchesStatus
  })

  const unknownStockCount = products.filter(p => getEffectiveStatus(p) === 'unknown').length
  const realStockSummary = {
    in_stock: products.filter(p => getEffectiveStatus(p) === 'in_stock').length,
    low_stock: products.filter(p => getEffectiveStatus(p) === 'low_stock').length,
    out_of_stock: products.filter(p => getEffectiveStatus(p) === 'out_of_stock').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-trendyol-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Stok yönetimi</h1>
          <p className="page-subtitle">Stok seviyeleri ve düşük stok uyarıları</p>
        </div>
        <button
          onClick={fetchInventoryData}
          className="px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition flex items-center space-x-2"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Yenile</span>
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Özet Kartlar (gerçek Trendyol stok verisiyle onaylanmış ürünlerden hesaplanır) */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="card bg-gradient-to-br from-blue-50 to-blue-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam Ürün</p>
                <p className="text-3xl font-bold text-blue-600 mt-1">{products.length}</p>
              </div>
              <Package className="w-10 h-10 text-blue-600 opacity-50" />
            </div>
          </div>

          <div className="card bg-gradient-to-br from-green-50 to-green-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Stokta Var</p>
                <p className="text-3xl font-bold text-green-600 mt-1">{realStockSummary.in_stock}</p>
              </div>
              <CheckCircle className="w-10 h-10 text-green-600 opacity-50" />
            </div>
          </div>

          <div className="card bg-gradient-to-br from-yellow-50 to-yellow-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Düşük Stok</p>
                <p className="text-3xl font-bold text-yellow-600 mt-1">{realStockSummary.low_stock}</p>
              </div>
              <AlertTriangle className="w-10 h-10 text-yellow-600 opacity-50" />
            </div>
          </div>

          <div className="card bg-gradient-to-br from-red-50 to-red-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Stokta Yok</p>
                <p className="text-3xl font-bold text-red-600 mt-1">{realStockSummary.out_of_stock}</p>
              </div>
              <XCircle className="w-10 h-10 text-red-600 opacity-50" />
            </div>
          </div>

          <div className="card bg-gradient-to-br from-gray-50 to-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Stok Bilinmiyor</p>
                <p className="text-3xl font-bold text-gray-500 mt-1">{unknownStockCount}</p>
              </div>
              <HelpCircle className="w-10 h-10 text-gray-400 opacity-50" />
            </div>
          </div>
        </div>
      )}

      {unknownStockCount > 0 && (
        <div className="flex items-start gap-2 bg-gray-50 border border-gray-200 text-gray-600 px-4 py-3 rounded-lg text-sm">
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            {unknownStockCount} ürün için stok bilgisi bilinmiyor — Trendyol Ürün API'si bu hesap için stok verisi döndürmedi, bu yüzden "Stokta Yok" yerine "Stok Bilinmiyor" gösteriliyor.
          </span>
        </div>
      )}

      {/* Filtreler */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Ürün adı, ID veya barkod ile ara..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
            />
          </div>
          
          <div className="flex items-center space-x-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
            >
              <option value="all">Tüm Durumlar</option>
              <option value="in_stock">Stokta Var</option>
              <option value="low_stock">Düşük Stok</option>
              <option value="out_of_stock">Stokta Yok</option>
              <option value="unknown">Stok Bilinmiyor</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="card">
        <div className="flex space-x-1 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('stock')}
            className={`px-6 py-3 font-medium text-sm transition ${
              activeTab === 'stock'
                ? 'border-b-2 border-orange-500 text-orange-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Package className="w-4 h-4 inline mr-2" />
            Stok Durumu
          </button>
          <button
            onClick={() => setActiveTab('recommendations')}
            className={`px-6 py-3 font-medium text-sm transition ${
              activeTab === 'recommendations'
                ? 'border-b-2 border-orange-500 text-orange-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Lightbulb className="w-4 h-4 inline mr-2" />
            Sipariş Önerileri
            {recommendations.length > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-orange-100 text-orange-600 rounded-full text-xs">
                {recommendations.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Recommendations Tab */}
      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Stok Sipariş Önerileri</h2>
              <p className="text-sm text-gray-600 mt-1">AI destekli otomatik sipariş önerileri</p>
            </div>
            <button
              onClick={generateRecommendations}
              disabled={generatingRecommendations}
              className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition flex items-center space-x-2 disabled:opacity-50"
            >
              {generatingRecommendations ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              <span>{generatingRecommendations ? 'Oluşturuluyor...' : 'Önerileri Oluştur'}</span>
            </button>
          </div>

          {recommendations.length === 0 ? (
            <div className="card text-center py-12">
              <Lightbulb className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p className="text-gray-600 mb-4">Henüz sipariş önerisi yok</p>
              <button
                onClick={generateRecommendations}
                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
              >
                Önerileri Oluştur
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {recommendations.map((rec) => (
                <div key={rec.id} className="card hover:shadow-lg transition">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="font-semibold text-gray-900 flex-1">{rec.product_name}</h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getUrgencyColor(rec.urgency_level)}`}>
                      {getUrgencyLabel(rec.urgency_level)}
                    </span>
                  </div>

                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Mevcut Stok:</span>
                      <span className="font-semibold text-red-600">{rec.current_stock}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Önerilen Miktar:</span>
                      <span className="font-semibold text-green-600">{rec.recommended_quantity}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Tahmini Teslimat:</span>
                      <span className="text-gray-900">{rec.estimated_arrival_days} gün</span>
                    </div>
                    {rec.recommendation_reason && (
                      <div className="mt-3 p-2 bg-gray-50 rounded text-xs text-gray-600">
                        {rec.recommendation_reason}
                      </div>
                    )}
                  </div>

                  {!rec.is_ordered && (
                    <button
                      onClick={() => markRecommendationOrdered(rec.id)}
                      className="w-full px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition flex items-center justify-center space-x-2"
                    >
                      <ShoppingCart className="w-4 h-4" />
                      <span>Sipariş Verildi</span>
                    </button>
                  )}
                  {rec.is_ordered && (
                    <div className="w-full px-4 py-2 bg-gray-100 text-gray-600 rounded-lg flex items-center justify-center space-x-2">
                      <CheckCircle className="w-4 h-4" />
                      <span>Sipariş Verildi</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stock Tab - Ürün Listesi */}
      {activeTab === 'stock' && (
        <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Ürün Stok Durumu ({filteredProducts.length})
        </h2>
        
        {filteredProducts.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Package className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            <p>Ürün bulunamadı</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Durum</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Ürün Adı</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Ürün ID</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Mevcut Stok</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Min. Stok</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Son 90 Gün Satış</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Son Güncelleme</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((product) => {
                  const effectiveStatus = getEffectiveStatus(product)
                  return (
                  <tr key={product.product_id} className="border-b border-gray-100 hover:bg-gray-50 transition">
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(effectiveStatus)}`}>
                        {getStatusIcon(effectiveStatus)}
                        <span>{getStatusText(effectiveStatus)}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-medium text-gray-900">{product.product_name}</p>
                      {product.category && (
                        <p className="text-xs text-gray-500 mt-1">{product.category}</p>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-sm text-gray-600 font-mono">{product.product_id.slice(0, 12)}...</p>
                    </td>
                    <td className="py-3 px-4">
                      {effectiveStatus === 'unknown' ? (
                        <p className="text-sm text-gray-400 italic">Bilinmiyor</p>
                      ) : (
                        <p className={`font-bold ${effectiveStatus === 'out_of_stock' ? 'text-red-600' : effectiveStatus === 'low_stock' ? 'text-yellow-600' : 'text-green-600'}`}>
                          {product.current_stock}
                        </p>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-sm text-gray-600">{product.min_stock_level}</p>
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-sm text-gray-600">
                        {product.total_sales_90days || 0} adet
                        {product.days_since_last_sale !== undefined && product.days_since_last_sale !== null && (
                          <span className="text-xs text-gray-400 block mt-1">
                            Son satış: {product.days_since_last_sale} gün önce
                          </span>
                        )}
                      </p>
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-sm text-gray-600">
                        {new Date(product.last_updated).toLocaleDateString('tr-TR')}
                      </p>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        </div>
      )}
    </div>
  )
}

