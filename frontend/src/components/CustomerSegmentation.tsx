import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { 
  Users, 
  TrendingUp, 
  AlertTriangle,
  Star,
  Target,
  BarChart3,
  Filter,
  RefreshCw,
  Calendar
} from 'lucide-react'

interface CustomerSegment {
  segment_id: string
  segment_name: string
  description: string
  criteria: {
    min_revenue?: number
    min_orders?: number
  }
  customer_count: number
  total_revenue: number
  avg_order_value: number
  created_at: string
}

interface CustomerProfile {
  customer_id: string
  customer_name?: string
  email?: string
  phone?: string
  total_orders: number
  total_revenue: number
  avg_order_value: number
  first_order_date?: string
  last_order_date?: string
  days_since_last_order?: number
  favorite_category?: string
  segment: string
  customer_lifetime_value: number
  churn_risk: string
  created_at: string
}

interface SegmentAnalysis {
  segment_id: string
  segment_name: string
  total_customers: number
  total_revenue: number
  avg_revenue_per_customer: number
  avg_orders_per_customer: number
  top_products: Array<{ name: string; count: number }>
  top_categories: Array<{ name: string; count: number }>
  growth_trend: string
  recommendations: string[]
}

export default function CustomerSegmentation() {
  const [segments, setSegments] = useState<CustomerSegment[]>([])
  const [customers, setCustomers] = useState<CustomerProfile[]>([])
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null)
  const [segmentAnalysis, setSegmentAnalysis] = useState<SegmentAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'segments' | 'customers' | 'churn'>('segments')
  const [filterSegment, setFilterSegment] = useState<string>('')

  useEffect(() => {
    fetchSegments()
  }, [])

  useEffect(() => {
    if (selectedSegment) {
      fetchSegmentAnalysis(selectedSegment)
    }
  }, [selectedSegment])

  useEffect(() => {
    if (activeTab === 'customers') {
      fetchCustomers()
    } else if (activeTab === 'churn') {
      fetchChurnRisk()
    }
  }, [activeTab, filterSegment])

  const fetchSegments = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/customer-segmentation/segments')
      setSegments(response.data || [])
    } catch (err: any) {
      setError('Segmentler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchCustomers = async () => {
    try {
      setLoading(true)
      setError(null)
      const params: any = {}
      if (filterSegment) {
        params.segment = filterSegment
      }
      const response = await apiClient.get('/customer-segmentation/customers', { params })
      setCustomers(response.data || [])
    } catch (err: any) {
      setError('Müşteriler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchSegmentAnalysis = async (segmentId: string) => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get(`/customer-segmentation/segments/${segmentId}/analysis`)
      setSegmentAnalysis(response.data)
    } catch (err: any) {
      setError('Segment analizi yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchChurnRisk = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/customer-segmentation/churn-risk')
      setCustomers(response.data?.customers || [])
    } catch (err: any) {
      setError('Churn risk analizi yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const getSegmentColor = (segmentId: string) => {
    const colors: Record<string, string> = {
      vip: 'bg-purple-100 text-purple-800 border-purple-300',
      loyal: 'bg-blue-100 text-blue-800 border-blue-300',
      regular: 'bg-green-100 text-green-800 border-green-300',
      new: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      at_risk: 'bg-red-100 text-red-800 border-red-300'
    }
    return colors[segmentId] || 'bg-gray-100 text-gray-800 border-gray-300'
  }

  const getSegmentIcon = (segmentId: string) => {
    switch (segmentId) {
      case 'vip':
        return Star
      case 'loyal':
        return TrendingUp
      case 'regular':
        return Users
      case 'new':
        return Target
      case 'at_risk':
        return AlertTriangle
      default:
        return Users
    }
  }

  const getChurnRiskColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return 'text-green-600 bg-green-50'
      case 'medium':
        return 'text-yellow-600 bg-yellow-50'
      case 'high':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY'
    }).format(amount)
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="page-header mb-8">
          <h1 className="page-title">Müşteri segmentasyonu</h1>
          <p className="page-subtitle">Segmentasyon ve churn risk yönetimi</p>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow-md mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('segments')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition ${
                  activeTab === 'segments'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Segmentler
                </div>
              </button>
              <button
                onClick={() => setActiveTab('customers')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition ${
                  activeTab === 'customers'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Müşteriler
                </div>
              </button>
              <button
                onClick={() => setActiveTab('churn')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition ${
                  activeTab === 'churn'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Churn Risk
                </div>
              </button>
            </nav>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Segments Tab */}
        {activeTab === 'segments' && (
          <div className="space-y-6">
            {loading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">Yükleniyor...</p>
              </div>
            ) : segments.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Henüz segment bulunamadı
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {segments.map((segment) => {
                  const Icon = getSegmentIcon(segment.segment_id)
                  return (
                    <div
                      key={segment.segment_id}
                      className={`bg-white rounded-lg shadow-md p-6 border-2 ${getSegmentColor(segment.segment_id)} cursor-pointer hover:shadow-lg transition`}
                      onClick={() => setSelectedSegment(segment.segment_id)}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${getSegmentColor(segment.segment_id)}`}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-lg">{segment.segment_name}</h3>
                            <p className="text-sm opacity-75">{segment.description}</p>
                          </div>
                        </div>
                      </div>
                      
                      <div className="space-y-2 mb-4">
                        <div className="flex justify-between text-sm">
                          <span className="opacity-75">Müşteri Sayısı:</span>
                          <span className="font-semibold">{segment.customer_count}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="opacity-75">Toplam Gelir:</span>
                          <span className="font-semibold">{formatCurrency(segment.total_revenue)}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="opacity-75">Ortalama Sipariş:</span>
                          <span className="font-semibold">{formatCurrency(segment.avg_order_value)}</span>
                        </div>
                      </div>

                      <button className="w-full mt-4 px-4 py-2 bg-white bg-opacity-50 hover:bg-opacity-75 rounded-lg text-sm font-medium transition">
                        Detaylı Analiz
                      </button>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Segment Analysis */}
            {selectedSegment && segmentAnalysis && (
              <div className="bg-white rounded-lg shadow-md p-6 mt-6">
                <h2 className="text-xl font-semibold mb-4">{segmentAnalysis.segment_name} - Detaylı Analiz</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-600 mb-1">Toplam Müşteri</p>
                    <p className="text-2xl font-bold">{segmentAnalysis.total_customers}</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-600 mb-1">Toplam Gelir</p>
                    <p className="text-2xl font-bold">{formatCurrency(segmentAnalysis.total_revenue)}</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-600 mb-1">Müşteri Başına Gelir</p>
                    <p className="text-2xl font-bold">{formatCurrency(segmentAnalysis.avg_revenue_per_customer)}</p>
                  </div>
                </div>

                {segmentAnalysis.recommendations.length > 0 && (
                  <div className="mb-6">
                    <h3 className="font-semibold mb-2">Öneriler</h3>
                    <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                      {segmentAnalysis.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <button
                  onClick={() => {
                    setSelectedSegment(null)
                    setSegmentAnalysis(null)
                  }}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm transition"
                >
                  Kapat
                </button>
              </div>
            )}
          </div>
        )}

        {/* Customers Tab */}
        {activeTab === 'customers' && (
          <div className="space-y-6">
            {/* Filter */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="flex items-center gap-4">
                <Filter className="w-5 h-5 text-gray-400" />
                <select
                  value={filterSegment}
                  onChange={(e) => setFilterSegment(e.target.value)}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                >
                  <option value="">Tüm Segmentler</option>
                  {segments.map((seg) => (
                    <option key={seg.segment_id} value={seg.segment_id}>
                      {seg.segment_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {loading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">Yükleniyor...</p>
              </div>
            ) : customers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Müşteri bulunamadı
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Müşteri</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Segment</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sipariş</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Toplam Gelir</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">CLV</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Churn Risk</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Son Sipariş</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {customers.map((customer) => (
                        <tr key={customer.customer_id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <p className="text-sm font-medium text-gray-900">
                                {customer.customer_name || customer.customer_id}
                              </p>
                              {customer.email && (
                                <p className="text-xs text-gray-500">{customer.email}</p>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSegmentColor(customer.segment)}`}>
                              {customer.segment}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {customer.total_orders}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {formatCurrency(customer.total_revenue)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatCurrency(customer.customer_lifetime_value)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getChurnRiskColor(customer.churn_risk)}`}>
                              {customer.churn_risk === 'low' ? 'Düşük' : customer.churn_risk === 'medium' ? 'Orta' : 'Yüksek'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {customer.days_since_last_order !== undefined
                              ? `${customer.days_since_last_order} gün önce`
                              : 'Bilinmiyor'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Churn Risk Tab */}
        {activeTab === 'churn' && (
          <div className="space-y-6">
            {loading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">Yükleniyor...</p>
              </div>
            ) : customers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                Risk altında müşteri bulunamadı
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-xl font-semibold mb-2">Risk Altındaki Müşteriler</h2>
                  <p className="text-sm text-gray-600">
                    Uzun süredir sipariş vermeyen müşteriler. Geri kazanma kampanyaları için öncelikli müşteriler.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Müşteri</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Son Sipariş</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Toplam Gelir</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sipariş Sayısı</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">İşlem</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {customers.map((customer) => (
                        <tr key={customer.customer_id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <p className="text-sm font-medium text-gray-900">
                                {customer.customer_name || customer.customer_id}
                              </p>
                              {customer.email && (
                                <p className="text-xs text-gray-500">{customer.email}</p>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Calendar className="w-4 h-4 text-gray-400" />
                              <span className="text-sm text-gray-900">
                                {customer.days_since_last_order !== undefined
                                  ? `${customer.days_since_last_order} gün önce`
                                  : 'Bilinmiyor'}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {formatCurrency(customer.total_revenue)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {customer.total_orders}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <button className="px-3 py-1 bg-orange-500 text-white text-sm rounded-lg hover:bg-orange-600 transition">
                              Kampanya Gönder
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

