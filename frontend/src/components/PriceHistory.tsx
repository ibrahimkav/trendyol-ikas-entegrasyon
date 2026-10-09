import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { 
  RefreshCw, 
  Search, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  DollarSign,
  BarChart3,
  Calendar,
  AlertCircle,
  Lightbulb,
  ArrowUp,
  ArrowDown
} from 'lucide-react'

interface PriceHistoryItem {
  id: number
  product_id: string
  product_name: string | null
  previous_price: number
  new_price: number
  price_change: number
  price_change_percent: number
  change_reason: string | null
  competitor_price: number | null
  created_at: string
}

interface PriceTrendItem {
  date: string
  average_price: number
  min_price: number | null
  max_price: number | null
  price_volatility: number
  sales_count: number
  revenue: number
  competitor_avg_price: number | null
  market_position: string | null
}

interface PriceAnalysis {
  product_id: string
  product_name: string
  current_price: number
  price_trend: 'increasing' | 'decreasing' | 'stable'
  average_price_30days: number
  average_price_90days: number
  price_change_30days: number
  price_change_90days: number
  best_price_period: {
    date: string
    price: number
    sales_after: number
  }
  worst_price_period: {
    date: string
    price: number
    sales_after: number
  }
  recommendations: string[]
}

export default function PriceHistory() {
  const [selectedProductId, setSelectedProductId] = useState<string>('')
  const [history, setHistory] = useState<PriceHistoryItem[]>([])
  const [, setTrends] = useState<PriceTrendItem[]>([])
  const [analysis, setAnalysis] = useState<PriceAnalysis | null>(null)
  const [allProducts, setAllProducts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [daysFilter, setDaysFilter] = useState(90)
  const [periodFilter, setPeriodFilter] = useState<'daily' | 'weekly' | 'monthly'>('daily')
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    fetchAllProducts()
  }, [])

  useEffect(() => {
    if (selectedProductId) {
      fetchPriceHistory()
      fetchPriceTrend()
      fetchPriceAnalysis()
    }
  }, [selectedProductId, daysFilter, periodFilter])

  const fetchAllProducts = async () => {
    try {
      setLoading(true)
      const response = await apiClient.get(`/price-history/products/all?days=30&limit=100`)
      const products = response.data.products || []
      setAllProducts(products)
      
      if (products.length === 0) {
        setError('Henüz ürün bulunamadı. Ürünler eklendikçe burada görünecek.')
      } else {
        setError(null)
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Ürünler yüklenemedi'
      setError(errorMsg)
      console.error('Ürünler yüklenemedi:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchPriceHistory = async () => {
    if (!selectedProductId) return
    
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get(`/price-history/${selectedProductId}?days=${daysFilter}`)
      setHistory(response.data || [])
    } catch (err: any) {
      setError('Fiyat geçmişi yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchPriceTrend = async () => {
    if (!selectedProductId) return
    
    try {
      const response = await apiClient.get(`/price-history/${selectedProductId}/trend?period=${periodFilter}&days=${daysFilter}`)
      setTrends(response.data || [])
    } catch (err: any) {
      console.error('Trend verileri yüklenemedi:', err)
    }
  }

  const fetchPriceAnalysis = async () => {
    if (!selectedProductId) return
    
    try {
      const response = await apiClient.get(`/price-history/${selectedProductId}/analysis`)
      setAnalysis(response.data)
    } catch (err: any) {
      console.error('Fiyat analizi yüklenemedi:', err)
    }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp className="w-5 h-5 text-red-600" />
      case 'decreasing':
        return <TrendingDown className="w-5 h-5 text-green-600" />
      default:
        return <Minus className="w-5 h-5 text-gray-600" />
    }
  }

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return 'bg-red-100 text-red-800'
      case 'decreasing':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getTrendLabel = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return 'Yükseliş'
      case 'decreasing':
        return 'Düşüş'
      default:
        return 'Stabil'
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
      minimumFractionDigits: 2
    }).format(price)
  }

  const filteredProducts = allProducts.filter(p =>
    p.product_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.product_id.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Fiyat geçmişi</h1>
          <p className="page-subtitle">Fiyat değişiklikleri ve trend analizi</p>
        </div>
        <button
          onClick={() => {
            if (selectedProductId) {
              fetchPriceHistory()
              fetchPriceTrend()
              fetchPriceAnalysis()
            }
            fetchAllProducts()
          }}
          className="flex items-center space-x-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Yenile</span>
        </button>
      </div>

      {/* Ürün Seçimi */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Ürün ara..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          />
        </div>

        {loading && allProducts.length === 0 ? (
          <div className="text-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-orange-500 mx-auto mb-2" />
            <p className="text-sm text-gray-600">Ürünler yükleniyor...</p>
          </div>
        ) : filteredProducts.length > 0 ? (
          <div className="max-h-60 overflow-y-auto">
            {filteredProducts.map((product) => (
              <button
                key={product.product_id}
                onClick={() => setSelectedProductId(product.product_id)}
                className={`w-full text-left px-4 py-3 rounded-lg mb-2 transition ${
                  selectedProductId === product.product_id
                    ? 'bg-orange-50 border-2 border-orange-500'
                    : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                }`}
              >
                <div className="flex justify-between items-center">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{product.product_name || product.product_id}</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <p className="text-xs text-gray-500">ID: {product.product_id}</p>
                      {!product.has_history && (
                        <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded-full">
                          Fiyat geçmişi yok
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <p className="font-semibold text-gray-900">{formatPrice(product.current_price)}</p>
                    {product.price_change_percent !== 0 && product.has_history && (
                      <p className={`text-xs mt-1 flex items-center justify-end ${
                        product.price_change_percent > 0 ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {product.price_change_percent > 0 ? (
                          <ArrowUp className="w-3 h-3 mr-1" />
                        ) : (
                          <ArrowDown className="w-3 h-3 mr-1" />
                        )}
                        {Math.abs(product.price_change_percent).toFixed(2)}%
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-600">
              {searchTerm ? 'Arama sonucu bulunamadı' : 'Henüz ürün bulunamadı'}
            </p>
            {!searchTerm && (
              <p className="text-xs text-gray-500 mt-1">
                Ürünler eklendikçe burada görünecek
              </p>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      {selectedProductId && (
        <>
          {/* Filtreler */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Zaman Aralığı</label>
                <select
                  value={daysFilter}
                  onChange={(e) => setDaysFilter(Number(e.target.value))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                >
                  <option value="7">Son 7 Gün</option>
                  <option value="30">Son 30 Gün</option>
                  <option value="90">Son 90 Gün</option>
                  <option value="180">Son 180 Gün</option>
                  <option value="365">Son 1 Yıl</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Periyot</label>
                <select
                  value={periodFilter}
                  onChange={(e) => setPeriodFilter(e.target.value as any)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                >
                  <option value="daily">Günlük</option>
                  <option value="weekly">Haftalık</option>
                  <option value="monthly">Aylık</option>
                </select>
              </div>
            </div>
          </div>

          {/* Fiyat Analizi */}
          {analysis && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Güncel Fiyat</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{formatPrice(analysis.current_price)}</p>
                  </div>
                  <div className="bg-orange-100 p-3 rounded-full">
                    <DollarSign className="w-6 h-6 text-orange-600" />
                  </div>
                </div>
                <div className="mt-4 flex items-center space-x-2">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTrendColor(analysis.price_trend)}`}>
                    {getTrendIcon(analysis.price_trend)}
                    <span className="ml-1">{getTrendLabel(analysis.price_trend)}</span>
                  </span>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">30 Günlük Ortalama</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{formatPrice(analysis.average_price_30days)}</p>
                  </div>
                  <div className="bg-blue-100 p-3 rounded-full">
                    <BarChart3 className="w-6 h-6 text-blue-600" />
                  </div>
                </div>
                <div className="mt-4">
                  <p className={`text-sm ${analysis.price_change_30days > 0 ? 'text-red-600' : analysis.price_change_30days < 0 ? 'text-green-600' : 'text-gray-600'}`}>
                    {analysis.price_change_30days > 0 ? '+' : ''}{analysis.price_change_30days.toFixed(2)}%
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">90 Günlük Ortalama</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{formatPrice(analysis.average_price_90days)}</p>
                  </div>
                  <div className="bg-purple-100 p-3 rounded-full">
                    <Calendar className="w-6 h-6 text-purple-600" />
                  </div>
                </div>
                <div className="mt-4">
                  <p className={`text-sm ${analysis.price_change_90days > 0 ? 'text-red-600' : analysis.price_change_90days < 0 ? 'text-green-600' : 'text-gray-600'}`}>
                    {analysis.price_change_90days > 0 ? '+' : ''}{analysis.price_change_90days.toFixed(2)}%
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <div>
                  <p className="text-sm text-gray-600">En İyi Dönem</p>
                  {analysis.best_price_period.date ? (
                    <>
                      <p className="text-lg font-bold text-gray-900 mt-1">{formatPrice(analysis.best_price_period.price)}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {analysis.best_price_period.sales_after} satış
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-gray-400 mt-1">Veri yok</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Öneriler */}
          {analysis && analysis.recommendations.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <Lightbulb className="w-5 h-5 mr-2 text-yellow-500" />
                Öneriler
              </h2>
              <ul className="space-y-2">
                {analysis.recommendations.map((rec, index) => (
                  <li key={index} className="flex items-start space-x-2 text-sm text-gray-700">
                    <span className="text-orange-500 mt-1">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Fiyat Geçmişi Tablosu */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">Fiyat Geçmişi</h2>
            </div>
            {loading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin text-orange-500 mx-auto" />
                <p className="text-gray-600 mt-2">Yükleniyor...</p>
              </div>
            ) : history.length === 0 ? (
              <div className="text-center py-12">
                <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">Fiyat geçmişi bulunamadı</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tarih</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Önceki Fiyat</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Yeni Fiyat</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Değişim</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Değişim %</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Neden</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rakip Fiyat</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {history.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {new Date(item.created_at).toLocaleString('tr-TR')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {formatPrice(item.previous_price)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                          {formatPrice(item.new_price)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${
                          item.price_change > 0 ? 'text-red-600' : item.price_change < 0 ? 'text-green-600' : 'text-gray-600'
                        }`}>
                          {item.price_change > 0 ? '+' : ''}{formatPrice(item.price_change)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${
                          item.price_change_percent > 0 ? 'text-red-600' : item.price_change_percent < 0 ? 'text-green-600' : 'text-gray-600'
                        }`}>
                          {item.price_change_percent > 0 ? '+' : ''}{item.price_change_percent.toFixed(2)}%
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {item.change_reason || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {item.competitor_price ? formatPrice(item.competitor_price) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {!selectedProductId && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 text-lg">Fiyat geçmişini görüntülemek için bir ürün seçin</p>
        </div>
      )}
    </div>
  )
}

