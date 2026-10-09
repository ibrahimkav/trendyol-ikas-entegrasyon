import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { Package, DollarSign, TrendingUp, CheckCircle, XCircle, AlertCircle, Loader } from 'lucide-react'

interface BulkOperationResult {
  success: boolean
  message: string
  affected_products: number
  details?: {
    updates: Array<{
      product_id: string
      product_name: string
      old_price?: number
      new_price?: number
      old_stock?: number
      new_stock?: number
      change?: number
      change_percent?: number
    }>
    total_updates: number
  }
}

export default function BulkOperations() {
  const [activeTab, setActiveTab] = useState<'price' | 'stock'>('price')
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BulkOperationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Fiyat güncelleme formu
  const [priceForm, setPriceForm] = useState({
    product_ids: [] as string[],
    category: '',
    update_type: 'percentage' as 'percentage' | 'fixed',
    value: 0,
    min_price: '',
    max_price: ''
  })

  // Stok güncelleme formu
  const [stockForm, setStockForm] = useState({
    product_ids: [] as string[],
    category: '',
    update_type: 'set' as 'set' | 'add' | 'subtract',
    value: 0
  })

  useEffect(() => {
    fetchCategories()
  }, [])

  const fetchCategories = async () => {
    try {
      const response = await apiClient.get('/bulk/categories')
      setCategories(response.data.categories || [])
    } catch (err: any) {
      console.error('[BulkOperations] Error fetching categories:', err)
    }
  }

  const handlePriceUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const requestData: any = {
        update_type: priceForm.update_type,
        value: priceForm.value
      }

      if (priceForm.product_ids.length > 0) {
        requestData.product_ids = priceForm.product_ids
      }

      if (priceForm.category) {
        requestData.category = priceForm.category
      }

      if (priceForm.min_price) {
        requestData.min_price = parseFloat(priceForm.min_price)
      }

      if (priceForm.max_price) {
        requestData.max_price = parseFloat(priceForm.max_price)
      }

      const response = await apiClient.post('/bulk/price-update', requestData)
      setResult(response.data)
      
      // Formu sıfırla
      setPriceForm({
        product_ids: [],
        category: '',
        update_type: 'percentage',
        value: 0,
        min_price: '',
        max_price: ''
      })
    } catch (err: any) {
      console.error('[BulkOperations] Error updating prices:', err)
      setError('Fiyat güncelleme hatası: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleStockUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const requestData: any = {
        update_type: stockForm.update_type,
        value: stockForm.value
      }

      if (stockForm.product_ids.length > 0) {
        requestData.product_ids = stockForm.product_ids
      }

      if (stockForm.category) {
        requestData.category = stockForm.category
      }

      const response = await apiClient.post('/bulk/stock-update', requestData)
      setResult(response.data)
      
      // Formu sıfırla
      setStockForm({
        product_ids: [],
        category: '',
        update_type: 'set',
        value: 0
      })
    } catch (err: any) {
      console.error('[BulkOperations] Error updating stock:', err)
      setError('Stok güncelleme hatası: ' + (err.response?.data?.detail || err.message))
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

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-title">Toplu işlemler</h1>
        <p className="page-subtitle">Toplu fiyat ve stok güncellemeleri</p>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => {
              setActiveTab('price')
              setResult(null)
              setError(null)
            }}
            className={`flex-1 px-6 py-4 text-center font-medium transition ${
              activeTab === 'price'
                ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <DollarSign className="w-5 h-5 inline-block mr-2" />
            Toplu Fiyat Güncelleme
          </button>
          <button
            onClick={() => {
              setActiveTab('stock')
              setResult(null)
              setError(null)
            }}
            className={`flex-1 px-6 py-4 text-center font-medium transition ${
              activeTab === 'stock'
                ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <Package className="w-5 h-5 inline-block mr-2" />
            Toplu Stok Güncelleme
          </button>
        </div>

        <div className="p-6">
          {/* Fiyat Güncelleme Formu */}
          {activeTab === 'price' && (
            <form onSubmit={handlePriceUpdate} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Güncelleme Tipi
                  </label>
                  <select
                    value={priceForm.update_type}
                    onChange={(e) => setPriceForm({ ...priceForm, update_type: e.target.value as 'percentage' | 'fixed' })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  >
                    <option value="percentage">Yüzde (%)</option>
                    <option value="fixed">Sabit Miktar (TL)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {priceForm.update_type === 'percentage' ? 'Yüzde (%)' : 'Miktar (TL)'}
                  </label>
                  <input
                    type="number"
                    step={priceForm.update_type === 'percentage' ? '0.1' : '0.01'}
                    value={priceForm.value || ''}
                    onChange={(e) => setPriceForm({ ...priceForm, value: parseFloat(e.target.value) || 0 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    required
                  />
                  {priceForm.update_type === 'percentage' && (
                    <p className="text-xs text-gray-500 mt-1">
                      Örnek: 10 = %10 artış, -5 = %5 azalış
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Kategori (Opsiyonel)
                  </label>
                  <select
                    value={priceForm.category}
                    onChange={(e) => setPriceForm({ ...priceForm, category: e.target.value })}
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
                    Minimum Fiyat (Opsiyonel)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={priceForm.min_price}
                    onChange={(e) => setPriceForm({ ...priceForm, min_price: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    placeholder="0.00"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Maksimum Fiyat (Opsiyonel)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={priceForm.max_price}
                    onChange={(e) => setPriceForm({ ...priceForm, max_price: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start">
                  <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 mr-3" />
                  <div className="text-sm text-yellow-800">
                    <p className="font-semibold mb-1">Önemli Not:</p>
                    <p>Bu işlem simüle edilmiştir. Gerçek fiyat güncellemesi için Trendyol API entegrasyonu gereklidir.</p>
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-orange-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-orange-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {loading ? (
                  <>
                    <Loader className="w-5 h-5 mr-2 animate-spin" />
                    Güncelleniyor...
                  </>
                ) : (
                  <>
                    <TrendingUp className="w-5 h-5 mr-2" />
                    Fiyatları Güncelle
                  </>
                )}
              </button>
            </form>
          )}

          {/* Stok Güncelleme Formu */}
          {activeTab === 'stock' && (
            <form onSubmit={handleStockUpdate} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Güncelleme Tipi
                  </label>
                  <select
                    value={stockForm.update_type}
                    onChange={(e) => setStockForm({ ...stockForm, update_type: e.target.value as 'set' | 'add' | 'subtract' })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  >
                    <option value="set">Belirli Değere Ayarla</option>
                    <option value="add">Ekle</option>
                    <option value="subtract">Çıkar</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Stok Miktarı
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={stockForm.value || ''}
                    onChange={(e) => setStockForm({ ...stockForm, value: parseInt(e.target.value) || 0 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    required
                  />
                  {stockForm.update_type === 'set' && (
                    <p className="text-xs text-gray-500 mt-1">Tüm ürünlerin stokunu bu değere ayarlar</p>
                  )}
                  {stockForm.update_type === 'add' && (
                    <p className="text-xs text-gray-500 mt-1">Mevcut stoka bu miktarı ekler</p>
                  )}
                  {stockForm.update_type === 'subtract' && (
                    <p className="text-xs text-gray-500 mt-1">Mevcut stoktan bu miktarı çıkarır</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Kategori (Opsiyonel)
                  </label>
                  <select
                    value={stockForm.category}
                    onChange={(e) => setStockForm({ ...stockForm, category: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  >
                    <option value="">Tüm Kategoriler</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start">
                  <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 mr-3" />
                  <div className="text-sm text-yellow-800">
                    <p className="font-semibold mb-1">Önemli Not:</p>
                    <p>Bu işlem simüle edilmiştir. Gerçek stok güncellemesi için Trendyol API entegrasyonu gereklidir.</p>
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-orange-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-orange-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {loading ? (
                  <>
                    <Loader className="w-5 h-5 mr-2 animate-spin" />
                    Güncelleniyor...
                  </>
                ) : (
                  <>
                    <Package className="w-5 h-5 mr-2" />
                    Stokları Güncelle
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Sonuç */}
      {result && (
        <div className={`rounded-lg p-6 ${
          result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
        }`}>
          <div className="flex items-start">
            {result.success ? (
              <CheckCircle className="w-6 h-6 text-green-600 mr-3 mt-0.5" />
            ) : (
              <XCircle className="w-6 h-6 text-red-600 mr-3 mt-0.5" />
            )}
            <div className="flex-1">
              <h3 className={`font-semibold mb-2 ${
                result.success ? 'text-green-900' : 'text-red-900'
              }`}>
                {result.message}
              </h3>
              <p className={`text-sm mb-4 ${
                result.success ? 'text-green-700' : 'text-red-700'
              }`}>
                Etkilenen ürün sayısı: <strong>{result.affected_products}</strong>
              </p>
              
              {result.details && result.details.updates && result.details.updates.length > 0 && (
                <div className="mt-4">
                  <h4 className="font-semibold text-gray-900 mb-3">Güncelleme Detayları (İlk 50):</h4>
                  <div className="bg-white rounded-lg border border-gray-200 max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left text-gray-700 font-semibold">Ürün</th>
                          {activeTab === 'price' ? (
                            <>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Eski Fiyat</th>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Yeni Fiyat</th>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Değişim</th>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">%</th>
                            </>
                          ) : (
                            <>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Eski Stok</th>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Yeni Stok</th>
                              <th className="px-4 py-3 text-right text-gray-700 font-semibold">Değişim</th>
                            </>
                          )}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {result.details.updates.map((update, index) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-gray-900">{update.product_name}</td>
                            {activeTab === 'price' ? (
                              <>
                                <td className="px-4 py-3 text-right text-gray-600">{formatCurrency(update.old_price || 0)}</td>
                                <td className="px-4 py-3 text-right font-semibold text-gray-900">{formatCurrency(update.new_price || 0)}</td>
                                <td className={`px-4 py-3 text-right font-medium ${
                                  (update.change || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                                }`}>
                                  {(update.change || 0) >= 0 ? '+' : ''}{formatCurrency(update.change || 0)}
                                </td>
                                <td className={`px-4 py-3 text-right font-medium ${
                                  (update.change_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                                }`}>
                                  {(update.change_percent || 0) >= 0 ? '+' : ''}{(update.change_percent || 0).toFixed(2)}%
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="px-4 py-3 text-right text-gray-600">{update.old_stock || 0}</td>
                                <td className="px-4 py-3 text-right font-semibold text-gray-900">{update.new_stock || 0}</td>
                                <td className={`px-4 py-3 text-right font-medium ${
                                  (update.change || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                                }`}>
                                  {(update.change || 0) >= 0 ? '+' : ''}{update.change || 0}
                                </td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {result.details.total_updates > 50 && (
                    <p className="text-xs text-gray-500 mt-2">
                      Toplam {result.details.total_updates} ürün güncellendi. İlk 50 ürün gösteriliyor.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Hata */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <XCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      )}
    </div>
  )
}


