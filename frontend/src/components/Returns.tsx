import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { 
  RefreshCw, 
  Search, 
  Package, 
  XCircle, 
  DollarSign, 
  AlertCircle,
  CheckCircle,
  Clock,
  X,
  Eye,
  Trash2,
  TrendingDown,
  BarChart3
} from 'lucide-react'

interface ReturnRefund {
  id: number
  return_id: string
  order_id: string
  order_number: string | null
  return_type: 'return' | 'cancel' | 'refund'
  status: 'pending' | 'approved' | 'rejected' | 'completed' | 'cancelled'
  reason: string | null
  total_amount: number
  refund_amount: number
  customer_name: string | null
  created_at: string
  updated_at: string
}

interface ReturnStats {
  total_returns: number
  total_cancels: number
  total_refunds: number
  pending_count: number
  approved_count: number
  rejected_count: number
  completed_count: number
  total_refund_amount: number
  return_rate: number
  top_reasons: Array<{ reason: string; count: number }>
}

export default function Returns() {
  const [returns, setReturns] = useState<ReturnRefund[]>([])
  const [filteredReturns, setFilteredReturns] = useState<ReturnRefund[]>([])
  const [stats, setStats] = useState<ReturnStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedReturn, setSelectedReturn] = useState<ReturnRefund | null>(null)
  const [daysFilter, setDaysFilter] = useState(30)

  useEffect(() => {
    fetchReturns()
    fetchStats()
  }, [daysFilter])

  useEffect(() => {
    filterReturns()
  }, [searchTerm, typeFilter, statusFilter, returns])

  const fetchReturns = async () => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams()
      if (typeFilter !== 'all') params.append('return_type', typeFilter)
      if (statusFilter !== 'all') params.append('status', statusFilter)
      params.append('days', daysFilter.toString())
      
      const response = await apiClient.get(`/returns/?${params.toString()}`)
      setReturns(response.data || [])
    } catch (err: any) {
      setError('İade/İptal kayıtları yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await apiClient.get(`/returns/stats?days=${daysFilter}`)
      setStats(response.data)
    } catch (err: any) {
      console.error('İstatistikler yüklenemedi:', err)
    }
  }

  const filterReturns = () => {
    let filtered = [...returns]

    // Arama filtresi
    if (searchTerm) {
      filtered = filtered.filter(r =>
        r.order_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (r.order_number && r.order_number.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (r.customer_name && r.customer_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
        r.return_id.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    setFilteredReturns(filtered)
  }

  const updateStatus = async (returnId: string, newStatus: string) => {
    try {
      await apiClient.patch(`/returns/${returnId}/status?status=${newStatus}`)
      await fetchReturns()
      await fetchStats()
      setSelectedReturn(null)
    } catch (err: any) {
      setError('Durum güncellenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const deleteReturn = async (returnId: string) => {
    if (!confirm('Bu kaydı silmek istediğinize emin misiniz?')) return
    
    try {
      await apiClient.delete(`/returns/${returnId}`)
      await fetchReturns()
      await fetchStats()
    } catch (err: any) {
      setError('Kayıt silinemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'return':
        return 'İade'
      case 'cancel':
        return 'İptal'
      case 'refund':
        return 'Para İadesi'
      default:
        return type
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'return':
        return <Package className="w-4 h-4" />
      case 'cancel':
        return <XCircle className="w-4 h-4" />
      case 'refund':
        return <DollarSign className="w-4 h-4" />
      default:
        return <AlertCircle className="w-4 h-4" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'return':
        return 'bg-blue-100 text-blue-800'
      case 'cancel':
        return 'bg-red-100 text-red-800'
      case 'refund':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Beklemede'
      case 'approved':
        return 'Onaylandı'
      case 'rejected':
        return 'Reddedildi'
      case 'completed':
        return 'Tamamlandı'
      case 'cancelled':
        return 'İptal Edildi'
      default:
        return status
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4" />
      case 'approved':
        return <CheckCircle className="w-4 h-4" />
      case 'rejected':
        return <X className="w-4 h-4" />
      case 'completed':
        return <CheckCircle className="w-4 h-4" />
      case 'cancelled':
        return <XCircle className="w-4 h-4" />
      default:
        return <AlertCircle className="w-4 h-4" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'approved':
        return 'bg-green-100 text-green-800'
      case 'rejected':
        return 'bg-red-100 text-red-800'
      case 'completed':
        return 'bg-blue-100 text-blue-800'
      case 'cancelled':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">İade ve iptal</h1>
          <p className="page-subtitle">İade ve iptal işlemlerini yönetin</p>
        </div>
        <button
          onClick={() => { fetchReturns(); fetchStats(); }}
          className="flex items-center space-x-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Yenile</span>
        </button>
      </div>

      {/* İstatistikler */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam İade</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_returns}</p>
              </div>
              <div className="bg-blue-100 p-3 rounded-full">
                <Package className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam İptal</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_cancels}</p>
              </div>
              <div className="bg-red-100 p-3 rounded-full">
                <XCircle className="w-6 h-6 text-red-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam İade Tutarı</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total_refund_amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })}
                </p>
              </div>
              <div className="bg-yellow-100 p-3 rounded-full">
                <DollarSign className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">İade Oranı</p>
                <p className="text-2xl font-bold text-gray-900">%{stats.return_rate}</p>
              </div>
              <div className="bg-purple-100 p-3 rounded-full">
                <TrendingDown className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Durum Özeti */}
      {stats && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <BarChart3 className="w-5 h-5 mr-2" />
            Durum Özeti
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-2xl font-bold text-yellow-800">{stats.pending_count}</p>
              <p className="text-sm text-gray-600">Beklemede</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-2xl font-bold text-green-800">{stats.approved_count}</p>
              <p className="text-sm text-gray-600">Onaylandı</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-2xl font-bold text-red-800">{stats.rejected_count}</p>
              <p className="text-sm text-gray-600">Reddedildi</p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-800">{stats.completed_count}</p>
              <p className="text-sm text-gray-600">Tamamlandı</p>
            </div>
          </div>
        </div>
      )}

      {/* Filtreler */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Sipariş, müşteri ara..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
            />
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          >
            <option value="all">Tüm Tipler</option>
            <option value="return">İade</option>
            <option value="cancel">İptal</option>
            <option value="refund">Para İadesi</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          >
            <option value="all">Tüm Durumlar</option>
            <option value="pending">Beklemede</option>
            <option value="approved">Onaylandı</option>
            <option value="rejected">Reddedildi</option>
            <option value="completed">Tamamlandı</option>
            <option value="cancelled">İptal Edildi</option>
          </select>

          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          >
            <option value="7">Son 7 Gün</option>
            <option value="15">Son 15 Gün</option>
            <option value="30">Son 30 Gün</option>
            <option value="60">Son 60 Gün</option>
            <option value="90">Son 90 Gün</option>
          </select>
        </div>
      </div>

      {/* Hata Mesajı */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      {/* Liste */}
      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-orange-500 mx-auto" />
          <p className="text-gray-600 mt-2">Yükleniyor...</p>
        </div>
      ) : filteredReturns.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Package className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">İade/İptal kaydı bulunamadı</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İade/İptal ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sipariş</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tip</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Durum</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tutar</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Müşteri</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tarih</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İşlemler</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredReturns.map((returnItem) => (
                  <tr key={returnItem.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{returnItem.return_id}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{returnItem.order_number || returnItem.order_id}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(returnItem.return_type)}`}>
                        {getTypeIcon(returnItem.return_type)}
                        <span className="ml-1">{getTypeLabel(returnItem.return_type)}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(returnItem.status)}`}>
                        {getStatusIcon(returnItem.status)}
                        <span className="ml-1">{getStatusLabel(returnItem.status)}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {returnItem.refund_amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{returnItem.customer_name || '-'}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {new Date(returnItem.created_at).toLocaleDateString('tr-TR')}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setSelectedReturn(returnItem)}
                          className="text-blue-600 hover:text-blue-900"
                          title="Detay"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {returnItem.status === 'pending' && (
                          <>
                            <button
                              onClick={() => updateStatus(returnItem.return_id, 'approved')}
                              className="text-green-600 hover:text-green-900"
                              title="Onayla"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => updateStatus(returnItem.return_id, 'rejected')}
                              className="text-red-600 hover:text-red-900"
                              title="Reddet"
                            >
                              <X className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => deleteReturn(returnItem.return_id)}
                              className="text-red-600 hover:text-red-900"
                              title="Sil"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detay Modal */}
      {selectedReturn && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold text-gray-900">İade/İptal Detayı</h2>
                <button
                  onClick={() => setSelectedReturn(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700">İade/İptal ID</label>
                    <p className="text-gray-900">{selectedReturn.return_id}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Sipariş No</label>
                    <p className="text-gray-900">{selectedReturn.order_number || selectedReturn.order_id}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Tip</label>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(selectedReturn.return_type)}`}>
                      {getTypeLabel(selectedReturn.return_type)}
                    </span>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Durum</label>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(selectedReturn.status)}`}>
                      {getStatusLabel(selectedReturn.status)}
                    </span>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Toplam Tutar</label>
                    <p className="text-gray-900">
                      {selectedReturn.total_amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">İade Tutarı</label>
                    <p className="text-gray-900">
                      {selectedReturn.refund_amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Müşteri</label>
                    <p className="text-gray-900">{selectedReturn.customer_name || '-'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Neden</label>
                    <p className="text-gray-900">{selectedReturn.reason || '-'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Oluşturulma</label>
                    <p className="text-gray-900">
                      {new Date(selectedReturn.created_at).toLocaleString('tr-TR')}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Güncellenme</label>
                    <p className="text-gray-900">
                      {new Date(selectedReturn.updated_at).toLocaleString('tr-TR')}
                    </p>
                  </div>
                </div>

                {selectedReturn.status === 'pending' && (
                  <div className="flex space-x-2 pt-4 border-t">
                    <button
                      onClick={() => {
                        updateStatus(selectedReturn.return_id, 'approved')
                        setSelectedReturn(null)
                      }}
                      className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition"
                    >
                      Onayla
                    </button>
                    <button
                      onClick={() => {
                        updateStatus(selectedReturn.return_id, 'rejected')
                        setSelectedReturn(null)
                      }}
                      className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition"
                    >
                      Reddet
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

