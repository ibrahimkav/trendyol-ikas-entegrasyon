import { useState, useEffect } from 'react'
// import { Link } from 'react-router-dom'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { Package, TrendingUp, TrendingDown, Minus, Search, Filter, DollarSign, ShoppingCart } from 'lucide-react'

interface Product {
  product_id: string
  product_name: string
  total_sales: number
  total_revenue: number
  average_price: number
  orders_count: number
  first_sale_date: string | null
  last_sale_date: string | null
  sales_trend: 'increasing' | 'decreasing' | 'stable'
  category?: string
  barcode?: string
}

interface ProductDetail {
  product: {
    product_id: string
    product_name: string
    category?: string
    barcode?: string
  }
  statistics: {
    total_sales: number
    total_revenue: number
    average_price: number
    orders_count: number
    first_sale_date: string | null
    last_sale_date: string | null
    sales_trend: string
    trend_percent: number
  }
  order_history: Array<{
    order_id: string
    order_date: string
    quantity: number
    price: number
    revenue: number
  }>
  daily_sales: Array<{
    date: string
    sales: number
  }>
  monthly_sales: Array<{
    month: string
    sales: number
  }>
}

export default function ProductManagement() {
  const toast = useToast()
  const [products, setProducts] = useState<Product[]>([])
  const [selectedProduct, setSelectedProduct] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<'revenue' | 'sales' | 'recent'>('revenue')
  const [summary, setSummary] = useState<{total_products: number, total_revenue: number, total_sales: number} | null>(null)

  useEffect(() => {
    fetchProducts()
  }, [sortBy])

  const fetchProducts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get(`/products/?sort_by=${sortBy}`)
      setProducts(response.data.products || [])
      setSummary({
        total_products: response.data.total_products || 0,
        total_revenue: response.data.total_revenue || 0,
        total_sales: response.data.total_sales || 0
      })
      
      if ((response.data.products || []).length === 0) {
        setError('Henüz ürün verisi yok. Siparişler geldikçe ürünler görünecek.')
      }
    } catch (err: any) {
      console.error('[ProductManagement] Error:', err)
      setError('Ürünler yüklenemedi: ' + (err.response?.data?.detail || err.message || 'Bilinmeyen hata'))
    } finally {
      setLoading(false)
    }
  }

  const fetchProductDetail = async (productId: string) => {
    try {
      setDetailLoading(true)
      const response = await apiClient.get(`/products/${productId}`)
      setSelectedProduct(response.data)
    } catch (err: any) {
      toast({ type: 'error', message: 'Ürün detayı yüklenemedi: ' + (err.response?.data?.detail || err.message) })
    } finally {
      setDetailLoading(false)
    }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp className="w-4 h-4 text-green-600" />
      case 'decreasing':
        return <TrendingDown className="w-4 h-4 text-red-600" />
      default:
        return <Minus className="w-4 h-4 text-gray-400" />
    }
  }

  const getTrendText = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return 'Artış'
      case 'decreasing':
        return 'Azalış'
      default:
        return 'Stabil'
    }
  }

  const filteredProducts = products.filter(product =>
    product.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    product.product_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (product.barcode && product.barcode.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (product.category && product.category.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-title">Ürün yönetimi</h1>
        <p className="page-subtitle">
          Ürünlerinizi görüntüleyin, performans analizi ve detay incelemesi yapın
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Özet Kartlar */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card bg-gradient-to-br from-blue-50 to-blue-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam Ürün</p>
                <p className="text-3xl font-bold text-blue-600 mt-1">{summary.total_products}</p>
              </div>
              <Package className="w-10 h-10 text-blue-600 opacity-50" />
            </div>
          </div>
          
          <div className="card bg-gradient-to-br from-green-50 to-green-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam Gelir</p>
                <p className="text-3xl font-bold text-green-600 mt-1">{summary.total_revenue.toFixed(2)} TL</p>
              </div>
              <DollarSign className="w-10 h-10 text-green-600 opacity-50" />
            </div>
          </div>
          
          <div className="card bg-gradient-to-br from-purple-50 to-purple-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam Satış</p>
                <p className="text-3xl font-bold text-purple-600 mt-1">{summary.total_sales}</p>
              </div>
              <ShoppingCart className="w-10 h-10 text-purple-600 opacity-50" />
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ürün Listesi */}
        <div className="lg:col-span-2">
          <div className="card">
            <div className="flex flex-col sm:flex-row gap-4 mb-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Ürün adı, ID, barkod veya kategori ile ara..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <Filter className="w-5 h-5 text-gray-400" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                >
                  <option value="revenue">Gelire Göre</option>
                  <option value="sales">Satışa Göre</option>
                  <option value="recent">Yeniden Eskiye</option>
                </select>
              </div>
            </div>

            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Ürünler ({filteredProducts.length})
            </h2>
            
            {filteredProducts.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <Package className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p>Ürün bulunamadı</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredProducts.map((product) => (
                  <div
                    key={product.product_id}
                    onClick={() => fetchProductDetail(product.product_id)}
                    className="p-4 border border-gray-200 rounded-lg hover:border-brand hover:shadow-md transition cursor-pointer"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2 mb-2">
                          <h3 className="font-semibold text-gray-900">{product.product_name}</h3>
                          {getTrendIcon(product.sales_trend)}
                          <span className={`text-xs font-semibold ${
                            product.sales_trend === 'increasing' ? 'text-green-600' :
                            product.sales_trend === 'decreasing' ? 'text-red-600' :
                            'text-gray-500'
                          }`}>
                            {getTrendText(product.sales_trend)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-600">
                          <span>ID: {product.product_id.slice(0, 12)}...</span>
                          {product.category && <span>Kategori: {product.category}</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-brand">
                          {product.total_revenue.toFixed(2)} TL
                        </p>
                        <p className="text-sm text-gray-600">
                          {product.total_sales} adet satıldı
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {product.orders_count} sipariş
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Ürün Detayları */}
        <div className="lg:col-span-1">
          {selectedProduct ? (
            <div className="card sticky top-4">
              {detailLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-gray-900">Ürün Detayları</h2>
                    <button
                      onClick={() => setSelectedProduct(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">{selectedProduct.product.product_name}</h3>
                      <div className="text-sm text-gray-600 space-y-1">
                        <p>ID: {selectedProduct.product.product_id}</p>
                        {selectedProduct.product.category && <p>Kategori: {selectedProduct.product.category}</p>}
                        {selectedProduct.product.barcode && <p>Barkod: {selectedProduct.product.barcode}</p>}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-gray-200">
                      <h4 className="font-semibold text-gray-700 mb-3">İstatistikler</h4>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Toplam Satış:</span>
                          <span className="font-semibold">{selectedProduct.statistics.total_sales} adet</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Toplam Gelir:</span>
                          <span className="font-semibold text-green-600">{selectedProduct.statistics.total_revenue.toFixed(2)} TL</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Ortalama Fiyat:</span>
                          <span className="font-semibold">{selectedProduct.statistics.average_price.toFixed(2)} TL</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Sipariş Sayısı:</span>
                          <span className="font-semibold">{selectedProduct.statistics.orders_count}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Satış Trendi:</span>
                          <div className="flex items-center space-x-1">
                            {getTrendIcon(selectedProduct.statistics.sales_trend)}
                            <span className={`text-sm font-semibold ${
                              selectedProduct.statistics.sales_trend === 'increasing' ? 'text-green-600' :
                              selectedProduct.statistics.sales_trend === 'decreasing' ? 'text-red-600' :
                              'text-gray-500'
                            }`}>
                              {selectedProduct.statistics.trend_percent > 0 ? '+' : ''}{selectedProduct.statistics.trend_percent.toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Günlük Satış Grafiği */}
                    {selectedProduct.daily_sales && selectedProduct.daily_sales.length > 0 && (
                      <div className="pt-4 border-t border-gray-200">
                        <h4 className="font-semibold text-gray-700 mb-3">Son 30 Günlük Satış</h4>
                        <div className="flex items-end justify-between gap-1 h-32">
                          {selectedProduct.daily_sales.slice(-7).map((day, index) => {
                            const maxSales = Math.max(...selectedProduct.daily_sales.map(d => d.sales), 1)
                            const height = (day.sales / maxSales) * 100
                            return (
                              <div key={index} className="flex-1 flex flex-col items-center group">
                                <div className="relative w-full flex items-end justify-center h-24">
                                  <div
                                    className="w-full bg-gradient-to-t from-brand to-brand-hover rounded-t transition-all hover:opacity-80 cursor-pointer"
                                    style={{ height: `${height}%`, minHeight: day.sales > 0 ? '4px' : '0' }}
                                    title={`${day.date}: ${day.sales} adet`}
                                  />
                                  {day.sales > 0 && (
                                    <div className="absolute -top-6 opacity-0 group-hover:opacity-100 transition-opacity bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                                      {day.sales} adet
                                    </div>
                                  )}
                                </div>
                                <div className="mt-1 text-[10px] text-gray-500 text-center">
                                  {new Date(day.date).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {/* Son Siparişler */}
                    {selectedProduct.order_history && selectedProduct.order_history.length > 0 && (
                      <div className="pt-4 border-t border-gray-200">
                        <h4 className="font-semibold text-gray-700 mb-3">Son Siparişler</h4>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {selectedProduct.order_history.slice(0, 5).map((order, index) => (
                            <div key={index} className="text-xs text-gray-600 flex justify-between">
                              <span>{new Date(order.order_date).toLocaleDateString('tr-TR')}</span>
                              <span className="font-semibold">{order.quantity} adet - {order.revenue.toFixed(2)} TL</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="card">
              <div className="text-center py-12 text-gray-500">
                <Package className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p className="text-sm">Bir ürün seçin</p>
                <p className="text-xs text-gray-400 mt-1">Detayları görmek için listeden bir ürüne tıklayın</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

