import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { Search, RefreshCw, DollarSign, ShoppingCart, Calendar, Mail, Phone, AlertCircle, User } from 'lucide-react'

interface Customer {
  customer_id: string
  name: string
  email: string
  phone: string
  total_orders: number
  total_spent: number
  average_order_value: number
  last_order_date: string
  customer_segment: string
}

export default function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [filteredCustomers, setFilteredCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [segmentFilter, setSegmentFilter] = useState<string>('all')
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)

  useEffect(() => {
    fetchCustomers()
  }, [])

  useEffect(() => {
    filterCustomers()
  }, [searchTerm, segmentFilter, customers])

  const fetchCustomers = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/customers/')
      setCustomers(response.data.customers || [])
    } catch (err: any) {
      setError('Müşteriler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const filterCustomers = () => {
    let filtered = [...customers]

    // Arama filtresi
    if (searchTerm) {
      filtered = filtered.filter(customer =>
        customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        customer.customer_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (customer.email && customer.email.toLowerCase().includes(searchTerm.toLowerCase()))
      )
    }

    // Segment filtresi
    if (segmentFilter !== 'all') {
      filtered = filtered.filter(customer => customer.customer_segment === segmentFilter)
    }

    setFilteredCustomers(filtered)
  }

  const getSegmentColor = (segment: string) => {
    switch (segment) {
      case 'new':
        return 'bg-blue-100 text-blue-800'
      case 'returning':
        return 'bg-green-100 text-green-800'
      case 'loyal':
        return 'bg-purple-100 text-purple-800'
      case 'vip':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getSegmentLabel = (segment: string) => {
    switch (segment) {
      case 'new':
        return 'Yeni Müşteri'
      case 'returning':
        return 'Tekrar Müşteri'
      case 'loyal':
        return 'Sadık Müşteri'
      case 'vip':
        return 'VIP Müşteri'
      default:
        return segment
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Müşteri yönetimi</h1>
          <p className="page-subtitle">{customers.length} toplam müşteri</p>
        </div>
        <button
          onClick={fetchCustomers}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Yenile</span>
        </button>
      </div>

      {/* Filtreler */}
      <div className="bg-white p-4 rounded-lg shadow-md">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Müşteri adı, ID veya e-posta ara..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
            />
          </div>
          <select
            value={segmentFilter}
            onChange={(e) => setSegmentFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
          >
            <option value="all">Tüm Segmentler</option>
            <option value="new">Yeni Müşteri</option>
            <option value="returning">Tekrar Müşteri</option>
            <option value="loyal">Sadık Müşteri</option>
            <option value="vip">VIP Müşteri</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
          <div>
            <h3 className="font-semibold text-red-900">Hata</h3>
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-trendyol-primary"></div>
          <p className="mt-4 text-gray-600">Yükleniyor...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCustomers.map((customer) => (
            <div
              key={customer.customer_id}
              className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition cursor-pointer border-2 border-transparent hover:border-trendyol-primary"
              onClick={() => setSelectedCustomer(customer)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 bg-trendyol-primary/10 rounded-full flex items-center justify-center">
                    <User className="w-6 h-6 text-trendyol-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{customer.name || 'Bilinmeyen Müşteri'}</h3>
                    <p className="text-xs text-gray-500">ID: {customer.customer_id}</p>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${getSegmentColor(customer.customer_segment)}`}>
                  {getSegmentLabel(customer.customer_segment)}
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <ShoppingCart className="w-4 h-4" />
                    <span>Sipariş</span>
                  </div>
                  <span className="font-semibold text-gray-900">{customer.total_orders}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <DollarSign className="w-4 h-4" />
                    <span>Toplam Harcama</span>
                  </div>
                  <span className="font-semibold text-gray-900">{customer.total_spent.toFixed(2)} TL</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <DollarSign className="w-4 h-4" />
                    <span>Ortalama Sipariş</span>
                  </div>
                  <span className="font-semibold text-gray-900">{customer.average_order_value.toFixed(2)} TL</span>
                </div>
                {customer.last_order_date && (
                  <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                    <div className="flex items-center space-x-2 text-xs text-gray-500">
                      <Calendar className="w-4 h-4" />
                      <span>Son Sipariş</span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(customer.last_order_date).toLocaleDateString('tr-TR')}
                    </span>
                  </div>
                )}
                {(customer.email || customer.phone) && (
                  <div className="pt-2 border-t border-gray-200 space-y-1">
                    {customer.email && (
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <Mail className="w-4 h-4" />
                        <span>{customer.email}</span>
                      </div>
                    )}
                    {customer.phone && (
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <Phone className="w-4 h-4" />
                        <span>{customer.phone}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Müşteri Detay Modal (basit versiyon) */}
      {selectedCustomer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelectedCustomer(null)}>
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-900">{selectedCustomer.name}</h2>
              <button
                onClick={() => setSelectedCustomer(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600">Müşteri ID</p>
                <p className="font-semibold">{selectedCustomer.customer_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Toplam Sipariş</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedCustomer.total_orders}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Toplam Harcama</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedCustomer.total_spent.toFixed(2)} TL</p>
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-2">Segment</p>
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${getSegmentColor(selectedCustomer.customer_segment)}`}>
                  {getSegmentLabel(selectedCustomer.customer_segment)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


