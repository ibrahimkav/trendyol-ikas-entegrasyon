// w3-competitor-frontend-cleanup — bu sayfa artık ERİŞİLEMEZ (route+nav linki+lazy import kaldırıldı,
// App.tsx/melontikNav.ts). Backend rotası da kapalı (main.py:138-144, "w3-competitor-route-close"):
// competitor_analysis.py'deki get_your_products() store_id filtresi OLMADAN TÜM mağazaların ürünlerini
// dönüyordu — router'ın 4 ucu da (products/analysis/market-trends/categories) bunu kullandığı için
// sızıntı özelliğin TAMAMINDAydı. Ayrıca özellik zaten sahteydi: Trendyol'da rakip-arama API'si yok,
// "rakip" olarak kendi katalog verimiz gösteriliyor, puan/yorum sayısı RANDOM üretiliyordu (bkz. Ryan'in
// araştırması, hive/docs/seller-workflow-gaps.md). Düzeltilmedi, KAPATILDI — geri getirilmeyecek. Kod
// silinmedi, sadece mount/erişim kaldırıldı.
import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { TrendingUp, TrendingDown, Minus, Search, BarChart3, AlertCircle, XCircle, Loader, Target, Users, Star } from 'lucide-react'

interface Product {
  product_id: string
  product_name: string
  category: string
  price: number
}

interface CompetitorProduct {
  product_id: string
  product_name: string
  competitor_name: string
  price: number
  rating?: number
  review_count?: number
  stock_status?: string
  last_updated: string
}

interface MarketAnalysis {
  product_id: string
  product_name: string
  your_price: number
  average_market_price: number
  min_price: number
  max_price: number
  competitor_count: number
  price_position: string
  recommendation: string
}

interface CompetitorAnalysis {
  product_id: string
  product_name: string
  your_price: number
  competitors: CompetitorProduct[]
  market_analysis: MarketAnalysis
}

interface MarketTrend {
  product_id: string
  product_name: string
  current_price: number
  trend_direction: string
  change_percent: number
  average_market_price: number
  competitor_count: number
}

export default function CompetitorAnalysis() {
  const [activeTab, setActiveTab] = useState<'analysis' | 'trends'>('analysis')
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<CompetitorAnalysis | null>(null)
  const [trends, setTrends] = useState<MarketTrend[]>([])
  const [loading, setLoading] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')

  useEffect(() => {
    fetchCategories()
    fetchProducts()
    if (activeTab === 'trends') {
      fetchMarketTrends()
    }
  }, [activeTab, selectedCategory])

  const fetchProducts = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (selectedCategory) params.append('category', selectedCategory)
      if (searchTerm) params.append('search', searchTerm)
      
      const response = await apiClient.get(`/competitor/products?${params.toString()}`)
      setProducts(response.data.products || [])
    } catch (err: any) {
      console.error('[CompetitorAnalysis] Error fetching products:', err)
      setError('Ürünler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchCategories = async () => {
    try {
      const response = await apiClient.get('/competitor/categories')
      setCategories(response.data.categories || [])
    } catch (err: any) {
      console.error('[CompetitorAnalysis] Error fetching categories:', err)
    }
  }

  const fetchAnalysis = async (productId: string) => {
    try {
      setAnalysisLoading(true)
      setError(null)
      const response = await apiClient.get(`/competitor/analysis/${productId}`)
      setAnalysis(response.data)
      setSelectedProduct(productId)
    } catch (err: any) {
      console.error('[CompetitorAnalysis] Error fetching analysis:', err)
      setError('Analiz yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAnalysisLoading(false)
    }
  }

  const fetchMarketTrends = async () => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams()
      if (selectedCategory) params.append('category', selectedCategory)
      
      const response = await apiClient.get(`/competitor/market-trends?${params.toString()}`)
      setTrends(response.data.trends || [])
    } catch (err: any) {
      console.error('[CompetitorAnalysis] Error fetching trends:', err)
      setError('Trend verileri yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY'
    }).format(amount)
  }

  const getRecommendationColor = (recommendation: string) => {
    switch (recommendation) {
      case 'increase':
        return 'text-green-600 bg-green-50'
      case 'decrease':
        return 'text-red-600 bg-red-50'
      case 'maintain':
        return 'text-blue-600 bg-blue-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getRecommendationText = (recommendation: string) => {
    switch (recommendation) {
      case 'increase':
        return 'Fiyatı Artır'
      case 'decrease':
        return 'Fiyatı Düşür'
      case 'maintain':
        return 'Fiyatı Koru'
      default:
        return 'Bilinmiyor'
    }
  }

  const getPricePositionText = (position: string) => {
    switch (position) {
      case 'lowest':
        return 'En Düşük'
      case 'highest':
        return 'En Yüksek'
      case 'average':
        return 'Ortalama'
      default:
        return 'Bilinmiyor'
    }
  }

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case 'up':
        return <TrendingUp className="w-5 h-5 text-green-600" />
      case 'down':
        return <TrendingDown className="w-5 h-5 text-red-600" />
      default:
        return <Minus className="w-5 h-5 text-gray-600" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-title">Rekabet analizi</h1>
        <p className="page-subtitle">Rakip fiyat takibi ve piyasa analizi</p>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => {
              setActiveTab('analysis')
              setAnalysis(null)
              setSelectedProduct(null)
            }}
            className={`flex-1 px-6 py-4 text-center font-medium transition ${
              activeTab === 'analysis'
                ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <Target className="w-5 h-5 inline-block mr-2" />
            Ürün Analizi
          </button>
          <button
            onClick={() => {
              setActiveTab('trends')
              fetchMarketTrends()
            }}
            className={`flex-1 px-6 py-4 text-center font-medium transition ${
              activeTab === 'trends'
                ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <BarChart3 className="w-5 h-5 inline-block mr-2" />
            Piyasa Trendleri
          </button>
        </div>

        <div className="p-6">
          {/* Ürün Analizi Sekmesi */}
          {activeTab === 'analysis' && (
            <div className="space-y-6">
              {/* Filtreler */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Kategori
                  </label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => {
                      setSelectedCategory(e.target.value)
                      fetchProducts()
                    }}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  >
                    <option value="">Tüm Kategoriler</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Ürün Ara
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={searchTerm}
                      onChange={(e) => {
                        setSearchTerm(e.target.value)
                        fetchProducts()
                      }}
                      placeholder="Ürün adı ile ara..."
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    />
                  </div>
                </div>
              </div>

              {/* Ürün Listesi */}
              {loading ? (
                <div className="text-center py-12">
                  <Loader className="w-8 h-8 animate-spin text-orange-600 mx-auto mb-4" />
                  <p className="text-gray-600">Yükleniyor...</p>
                </div>
              ) : products.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">Ürün bulunamadı</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {products.map((product) => (
                    <button
                      key={product.product_id}
                      onClick={() => fetchAnalysis(product.product_id)}
                      className={`p-4 rounded-lg border-2 transition text-left ${
                        selectedProduct === product.product_id
                          ? 'border-orange-500 bg-orange-50'
                          : 'border-gray-200 hover:border-orange-300 hover:bg-gray-50'
                      }`}
                    >
                      <h3 className="font-semibold text-gray-900 mb-2">{product.product_name}</h3>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">{product.category}</span>
                        <span className="text-lg font-bold text-orange-600">{formatCurrency(product.price)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Analiz Sonuçları */}
              {analysisLoading && (
                <div className="text-center py-12">
                  <Loader className="w-8 h-8 animate-spin text-orange-600 mx-auto mb-4" />
                  <p className="text-gray-600">Analiz yapılıyor...</p>
                </div>
              )}

              {analysis && !analysisLoading && (
                <div className="space-y-6 mt-6">
                  {/* Piyasa Analizi Özeti */}
                  <div className="bg-gradient-to-r from-orange-50 to-orange-100 rounded-lg p-6 border border-orange-200">
                    <h2 className="text-xl font-bold text-gray-900 mb-4">{analysis.product_name}</h2>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Sizin Fiyatınız</p>
                        <p className="text-2xl font-bold text-gray-900">{formatCurrency(analysis.your_price)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Ortalama Piyasa Fiyatı</p>
                        <p className="text-2xl font-bold text-gray-900">{formatCurrency(analysis.market_analysis.average_market_price)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Fiyat Pozisyonu</p>
                        <p className="text-2xl font-bold text-gray-900">{getPricePositionText(analysis.market_analysis.price_position)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Öneri</p>
                        <span className={`inline-block px-4 py-2 rounded-lg font-semibold ${getRecommendationColor(analysis.market_analysis.recommendation)}`}>
                          {getRecommendationText(analysis.market_analysis.recommendation)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Fiyat Aralığı */}
                  <div className="bg-white rounded-lg border border-gray-200 p-6">
                    <h3 className="font-semibold text-gray-900 mb-4">Fiyat Aralığı</h3>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">En Düşük</span>
                      <span className="text-lg font-bold text-green-600">{formatCurrency(analysis.market_analysis.min_price)}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                      <div
                        className="bg-gradient-to-r from-green-500 via-orange-500 to-red-500 h-3 rounded-full"
                        style={{ width: '100%' }}
                      />
                      <div className="flex justify-between mt-1">
                        <div className="text-center">
                          <div className="w-3 h-3 bg-green-500 rounded-full mx-auto mb-1" />
                          <span className="text-xs text-gray-600">{formatCurrency(analysis.market_analysis.min_price)}</span>
                        </div>
                        <div className="text-center">
                          <div className="w-3 h-3 bg-orange-500 rounded-full mx-auto mb-1" />
                          <span className="text-xs text-gray-600">{formatCurrency(analysis.market_analysis.average_market_price)}</span>
                        </div>
                        <div className="text-center">
                          <div className="w-3 h-3 bg-red-500 rounded-full mx-auto mb-1" />
                          <span className="text-xs text-gray-600">{formatCurrency(analysis.market_analysis.max_price)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 text-center">
                      <div className="inline-block px-4 py-2 bg-orange-100 rounded-lg">
                        <span className="text-sm text-gray-600">Sizin Fiyatınız: </span>
                        <span className="font-bold text-orange-600">{formatCurrency(analysis.your_price)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Rakip Listesi */}
                  <div className="bg-white rounded-lg border border-gray-200 p-6">
                    <h3 className="font-semibold text-gray-900 mb-4">
                      Rakip Ürünler ({analysis.competitors.length})
                    </h3>
                    <div className="space-y-3">
                      {analysis.competitors.map((competitor, index) => (
                        <div
                          key={index}
                          className={`p-4 rounded-lg border-2 ${
                            competitor.price < analysis.your_price
                              ? 'border-red-200 bg-red-50'
                              : competitor.price > analysis.your_price
                              ? 'border-green-200 bg-green-50'
                              : 'border-gray-200 bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <h4 className="font-semibold text-gray-900">{competitor.competitor_name}</h4>
                              <div className="flex items-center space-x-4 mt-2 text-sm text-gray-600">
                                {competitor.rating && (
                                  <div className="flex items-center">
                                    <Star className="w-4 h-4 text-yellow-500 mr-1 fill-current" />
                                    <span>{competitor.rating}</span>
                                  </div>
                                )}
                                {competitor.review_count && (
                                  <div className="flex items-center">
                                    <Users className="w-4 h-4 mr-1" />
                                    <span>{competitor.review_count} değerlendirme</span>
                                  </div>
                                )}
                                {competitor.stock_status && (
                                  <span className={`px-2 py-1 rounded text-xs ${
                                    competitor.stock_status === 'Stokta'
                                      ? 'bg-green-100 text-green-700'
                                      : 'bg-red-100 text-red-700'
                                  }`}>
                                    {competitor.stock_status}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-bold text-gray-900">{formatCurrency(competitor.price)}</p>
                              {competitor.price !== analysis.your_price && (
                                <p className={`text-sm font-medium ${
                                  competitor.price < analysis.your_price
                                    ? 'text-red-600'
                                    : 'text-green-600'
                                }`}>
                                  {competitor.price < analysis.your_price ? '-' : '+'}
                                  {formatCurrency(Math.abs(competitor.price - analysis.your_price))}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Piyasa Trendleri Sekmesi */}
          {activeTab === 'trends' && (
            <div className="space-y-6">
              {/* Filtreler */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Kategori
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => {
                    setSelectedCategory(e.target.value)
                    fetchMarketTrends()
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                >
                  <option value="">Tüm Kategoriler</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              {/* Trend Listesi */}
              {loading ? (
                <div className="text-center py-12">
                  <Loader className="w-8 h-8 animate-spin text-orange-600 mx-auto mb-4" />
                  <p className="text-gray-600">Yükleniyor...</p>
                </div>
              ) : trends.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">Trend verisi bulunamadı</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {trends.map((trend) => (
                    <div key={trend.product_id} className="bg-white rounded-lg border border-gray-200 p-6">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900 mb-2">{trend.product_name}</h3>
                          <div className="flex items-center space-x-6 text-sm text-gray-600">
                            <div>
                              <span className="font-medium">Fiyat: </span>
                              <span className="font-bold text-gray-900">{formatCurrency(trend.current_price)}</span>
                            </div>
                            <div>
                              <span className="font-medium">Ortalama Piyasa: </span>
                              <span className="font-bold text-gray-900">{formatCurrency(trend.average_market_price)}</span>
                            </div>
                            <div>
                              <span className="font-medium">Rakip Sayısı: </span>
                              <span className="font-bold text-gray-900">{trend.competitor_count}</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="flex items-center space-x-2 mb-2">
                            {getTrendIcon(trend.trend_direction)}
                            <span className={`text-lg font-bold ${
                              trend.trend_direction === 'up'
                                ? 'text-green-600'
                                : trend.trend_direction === 'down'
                                ? 'text-red-600'
                                : 'text-gray-600'
                            }`}>
                              {trend.change_percent >= 0 ? '+' : ''}{trend.change_percent.toFixed(2)}%
                            </span>
                          </div>
                          <p className="text-xs text-gray-500">Son 30 gün</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Hata */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <XCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* Bilgi Notu */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 mr-3" />
          <div className="text-sm text-blue-800">
            <p className="font-semibold mb-1">Bilgi:</p>
            <p>Rakip analizi, Trendyol'dan çekilen gerçek ürün verileri kullanılarak yapılmaktadır. Aynı kategorideki benzer ürünler rakip olarak gösterilmektedir.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

