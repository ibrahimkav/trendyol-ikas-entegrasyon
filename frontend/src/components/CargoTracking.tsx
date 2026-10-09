import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { Truck, Search, RefreshCw, Package, Clock, AlertCircle, CheckCircle } from 'lucide-react'

interface CargoItem {
  order_id: string
  cargo_company: string
  tracking_number: string
  status: string
  status_code: string
  order_date: string
  total_amount: number
}

export default function CargoTracking() {
  const [cargoList, setCargoList] = useState<CargoItem[]>([])
  const [filteredList, setFilteredList] = useState<CargoItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [companyFilter, setCompanyFilter] = useState<string>('all')
  const [cargoCompanies, setCargoCompanies] = useState<string[]>([])

  useEffect(() => {
    fetchCargoTracking()
  }, [])

  useEffect(() => {
    filterCargoList()
  }, [searchTerm, statusFilter, companyFilter, cargoList])
  
  useEffect(() => {
    // Kargo firmalarını çıkar
    const companies = [...new Set(cargoList.map(item => item.cargo_company))].sort()
    setCargoCompanies(companies)
  }, [cargoList])

  const fetchCargoTracking = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/cargo/')
      setCargoList(response.data.cargo_list || [])
    } catch (err: any) {
      setError('Kargo bilgileri yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const filterCargoList = () => {
    let filtered = [...cargoList]

    // Arama filtresi
    if (searchTerm) {
      filtered = filtered.filter(item =>
        item.order_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.tracking_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.cargo_company.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    // Durum filtresi
    if (statusFilter !== 'all') {
      if (statusFilter === 'preparing') {
        filtered = filtered.filter(item => ['Created', 'Picking'].includes(item.status_code))
      } else if (statusFilter === 'shipped') {
        filtered = filtered.filter(item => item.status_code === 'Shipped')
      } else if (statusFilter === 'delivered') {
        filtered = filtered.filter(item => ['Delivered', 'Completed'].includes(item.status_code))
      }
    }

    // Kargo firması filtresi
    if (companyFilter !== 'all') {
      filtered = filtered.filter(item => item.cargo_company === companyFilter)
    }

    setFilteredList(filtered)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Hazırlanıyor':
      case 'Toplanıyor':
        return 'bg-yellow-100 text-yellow-800'
      case 'Faturalandı':
        return 'bg-blue-100 text-blue-800'
      case 'Kargoda':
        return 'bg-purple-100 text-purple-800'
      case 'Teslim Edildi':
      case 'Tamamlandı':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Hazırlanıyor':
      case 'Toplanıyor':
        return <Package className="w-4 h-4" />
      case 'Kargoda':
        return <Truck className="w-4 h-4" />
      case 'Teslim Edildi':
      case 'Tamamlandı':
        return <CheckCircle className="w-4 h-4" />
      default:
        return <Clock className="w-4 h-4" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Kargo takip</h1>
          <p className="page-subtitle">Tüm kargo durumlarını takip edin</p>
        </div>
        <button
          onClick={fetchCargoTracking}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Yenile</span>
        </button>
      </div>

      {/* Filtreler */}
      <div className="bg-white p-4 rounded-lg shadow-md">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Sipariş ID, Takip No veya Kargo Firması ara..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
          >
            <option value="all">Tüm Durumlar</option>
            <option value="preparing">Hazırlanıyor</option>
            <option value="shipped">Kargoda</option>
            <option value="delivered">Teslim Edildi</option>
          </select>
          <select
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
          >
            <option value="all">Tüm Kargo Firmaları</option>
            {cargoCompanies.map((company) => (
              <option key={company} value={company}>
                {company}
              </option>
            ))}
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
      ) : filteredList.length === 0 ? (
        <div className="bg-white p-12 rounded-lg shadow-md text-center">
          <Truck className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Kargo bulunamadı</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sipariş ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Kargo Firması
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Takip No
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Durum
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tutar
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tarih
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredList.map((item, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{item.order_id}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{item.cargo_company}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900 font-mono">{item.tracking_number}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(item.status)}`}>
                        {getStatusIcon(item.status)}
                        <span>{item.status}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{item.total_amount.toFixed(2)} TL</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {new Date(item.order_date).toLocaleDateString('tr-TR')}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}


