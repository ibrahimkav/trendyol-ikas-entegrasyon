import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { 
  RefreshCw, 
  Search, 
  Plus, 
  Edit, 
  Trash2, 
  ToggleLeft, 
  ToggleRight,
  Tag,
  Percent,
  TrendingUp,
  X,
  Save,
  AlertCircle,
  Zap
} from 'lucide-react'

interface Campaign {
  id: number
  campaign_id: string
  name: string
  description: string | null
  campaign_type: 'coupon' | 'flash_sale' | 'bulk_discount' | 'category_discount'
  discount_type: 'percentage' | 'fixed_amount'
  discount_value: number
  min_purchase_amount: number
  max_discount_amount: number | null
  coupon_code: string | null
  start_date: string
  end_date: string
  status: 'draft' | 'active' | 'paused' | 'expired' | 'cancelled'
  usage_limit: number | null
  usage_count: number
  max_usage_per_customer: number
  is_active: boolean
  created_at: string
  updated_at: string
}

interface CampaignStats {
  total_campaigns: number
  active_campaigns: number
  total_discount_amount: number
  total_orders: number
  total_revenue: number
  average_discount_rate: number
  top_campaigns: Array<{
    campaign_id: string
    name: string
    orders: number
    revenue: number
  }>
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [filteredCampaigns, setFilteredCampaigns] = useState<Campaign[]>([])
  const [stats, setStats] = useState<CampaignStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [showModal, setShowModal] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null)
  const [formData, setFormData] = useState<{
    name: string
    description: string
    campaign_type: 'coupon' | 'flash_sale' | 'bulk_discount' | 'category_discount'
    discount_type: 'percentage' | 'fixed_amount'
    discount_value: number
    min_purchase_amount: number
    max_discount_amount: number | null
    coupon_code: string
    start_date: string
    end_date: string
    target_products: string[]
    target_categories: string[]
    usage_limit: number | null
    max_usage_per_customer: number
  }>({
    name: '',
    description: '',
    campaign_type: 'coupon',
    discount_type: 'percentage',
    discount_value: 0,
    min_purchase_amount: 0,
    max_discount_amount: null,
    coupon_code: '',
    start_date: '',
    end_date: '',
    target_products: [],
    target_categories: [],
    usage_limit: null,
    max_usage_per_customer: 1
  })

  useEffect(() => {
    fetchCampaigns()
    fetchStats()
  }, [])

  useEffect(() => {
    filterCampaigns()
  }, [searchTerm, typeFilter, statusFilter, campaigns])

  const fetchCampaigns = async () => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams()
      if (typeFilter !== 'all') params.append('campaign_type', typeFilter)
      if (statusFilter !== 'all') params.append('status', statusFilter)
      
      const response = await apiClient.get(`/campaigns/?${params.toString()}`)
      setCampaigns(response.data || [])
    } catch (err: any) {
      setError('Kampanyalar yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/campaigns/stats?days=30')
      setStats(response.data)
    } catch (err: any) {
      console.error('İstatistikler yüklenemedi:', err)
    }
  }

  const filterCampaigns = () => {
    let filtered = [...campaigns]

    if (searchTerm) {
      filtered = filtered.filter(c =>
        c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.coupon_code && c.coupon_code.toLowerCase().includes(searchTerm.toLowerCase())) ||
        c.campaign_id.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    setFilteredCampaigns(filtered)
  }

  const handleCreate = () => {
    setEditingCampaign(null)
    setFormData({
      name: '',
      description: '',
      campaign_type: 'coupon',
      discount_type: 'percentage',
      discount_value: 0,
      min_purchase_amount: 0,
      max_discount_amount: null,
      coupon_code: '',
      start_date: '',
      end_date: '',
      target_products: [],
      target_categories: [],
      usage_limit: null,
      max_usage_per_customer: 1
    })
    setShowModal(true)
  }

  const handleEdit = (campaign: Campaign) => {
    setEditingCampaign(campaign)
    setFormData({
      name: campaign.name,
      description: campaign.description || '',
      campaign_type: campaign.campaign_type,
      discount_type: campaign.discount_type,
      discount_value: campaign.discount_value,
      min_purchase_amount: campaign.min_purchase_amount,
      max_discount_amount: campaign.max_discount_amount,
      coupon_code: campaign.coupon_code || '',
      start_date: campaign.start_date.split('T')[0],
      end_date: campaign.end_date.split('T')[0],
      target_products: [],
      target_categories: [],
      usage_limit: campaign.usage_limit,
      max_usage_per_customer: campaign.max_usage_per_customer
    })
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload = {
        ...formData,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
        coupon_code: formData.coupon_code || undefined
      }

      if (editingCampaign) {
        await apiClient.patch(`/campaigns/${editingCampaign.campaign_id}`, payload)
      } else {
        await apiClient.post('/campaigns/', payload)
      }

      setShowModal(false)
      await fetchCampaigns()
      await fetchStats()
    } catch (err: any) {
      setError('Kampanya kaydedilemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleToggle = async (campaignId: string) => {
    try {
      await apiClient.patch(`/campaigns/${campaignId}/toggle`)
      await fetchCampaigns()
      await fetchStats()
    } catch (err: any) {
      setError('Kampanya durumu güncellenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (campaignId: string) => {
    if (!confirm('Bu kampanyayı silmek istediğinize emin misiniz?')) return
    
    try {
      await apiClient.delete(`/campaigns/${campaignId}`)
      await fetchCampaigns()
      await fetchStats()
    } catch (err: any) {
      setError('Kampanya silinemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'coupon':
        return 'Kupon'
      case 'flash_sale':
        return 'Flash Sale'
      case 'bulk_discount':
        return 'Toplu İndirim'
      case 'category_discount':
        return 'Kategori İndirimi'
      default:
        return type
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'coupon':
        return 'bg-blue-100 text-blue-800'
      case 'flash_sale':
        return 'bg-red-100 text-red-800'
      case 'bulk_discount':
        return 'bg-green-100 text-green-800'
      case 'category_discount':
        return 'bg-purple-100 text-purple-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'draft':
        return 'Taslak'
      case 'active':
        return 'Aktif'
      case 'paused':
        return 'Duraklatıldı'
      case 'expired':
        return 'Süresi Doldu'
      case 'cancelled':
        return 'İptal Edildi'
      default:
        return status
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft':
        return 'bg-gray-100 text-gray-800'
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'paused':
        return 'bg-yellow-100 text-yellow-800'
      case 'expired':
        return 'bg-red-100 text-red-800'
      case 'cancelled':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const formatDiscount = (campaign: Campaign) => {
    if (campaign.discount_type === 'percentage') {
      return `%${campaign.discount_value}`
    } else {
      return `${campaign.discount_value.toLocaleString('tr-TR')} ₺`
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Kampanya ve indirim</h1>
          <p className="page-subtitle">Kampanyaları oluşturun ve yönetin</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => { fetchCampaigns(); fetchStats(); }}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Yenile</span>
          </button>
          <button
            onClick={handleCreate}
            className="flex items-center space-x-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
          >
            <Plus className="w-4 h-4" />
            <span>Yeni Kampanya</span>
          </button>
        </div>
      </div>

      {/* İstatistikler */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam Kampanya</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_campaigns}</p>
              </div>
              <div className="bg-blue-100 p-3 rounded-full">
                <Tag className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Aktif Kampanya</p>
                <p className="text-2xl font-bold text-gray-900">{stats.active_campaigns}</p>
              </div>
              <div className="bg-green-100 p-3 rounded-full">
                <Zap className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Toplam İndirim</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total_discount_amount.toLocaleString('tr-TR', { style: 'currency', currency: 'TRY' })}
                </p>
              </div>
              <div className="bg-yellow-100 p-3 rounded-full">
                <Percent className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Ortalama İndirim</p>
                <p className="text-2xl font-bold text-gray-900">%{stats.average_discount_rate}</p>
              </div>
              <div className="bg-purple-100 p-3 rounded-full">
                <TrendingUp className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filtreler */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Kampanya ara..."
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
            <option value="coupon">Kupon</option>
            <option value="flash_sale">Flash Sale</option>
            <option value="bulk_discount">Toplu İndirim</option>
            <option value="category_discount">Kategori İndirimi</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          >
            <option value="all">Tüm Durumlar</option>
            <option value="draft">Taslak</option>
            <option value="active">Aktif</option>
            <option value="paused">Duraklatıldı</option>
            <option value="expired">Süresi Doldu</option>
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
      ) : filteredCampaigns.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Tag className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Kampanya bulunamadı</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCampaigns.map((campaign) => (
            <div key={campaign.id} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition">
              <div className="flex justify-between items-start mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">{campaign.name}</h3>
                  <div className="flex items-center space-x-2 mb-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getTypeColor(campaign.campaign_type)}`}>
                      {getTypeLabel(campaign.campaign_type)}
                    </span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(campaign.status)}`}>
                      {getStatusLabel(campaign.status)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleToggle(campaign.campaign_id)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  {campaign.is_active ? (
                    <ToggleRight className="w-6 h-6 text-green-500" />
                  ) : (
                    <ToggleLeft className="w-6 h-6 text-gray-400" />
                  )}
                </button>
              </div>

              {campaign.description && (
                <p className="text-sm text-gray-600 mb-3">{campaign.description}</p>
              )}

              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">İndirim:</span>
                  <span className="font-semibold text-orange-600">{formatDiscount(campaign)}</span>
                </div>
                {campaign.coupon_code && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Kupon Kodu:</span>
                    <span className="font-mono font-semibold text-blue-600">{campaign.coupon_code}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Kullanım:</span>
                  <span className="font-semibold">
                    {campaign.usage_count} / {campaign.usage_limit || '∞'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Tarih:</span>
                  <span className="text-xs text-gray-500">
                    {new Date(campaign.start_date).toLocaleDateString('tr-TR')} - {new Date(campaign.end_date).toLocaleDateString('tr-TR')}
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2 pt-4 border-t">
                <button
                  onClick={() => handleEdit(campaign)}
                  className="flex-1 px-3 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition text-sm font-medium"
                >
                  <Edit className="w-4 h-4 inline mr-1" />
                  Düzenle
                </button>
                {campaign.status === 'draft' && (
                  <button
                    onClick={() => handleDelete(campaign.campaign_id)}
                    className="px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold text-gray-900">
                  {editingCampaign ? 'Kampanya Düzenle' : 'Yeni Kampanya'}
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Kampanya Adı *</label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Açıklama</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Kampanya Tipi *</label>
                    <select
                      required
                      value={formData.campaign_type}
                      onChange={(e) => setFormData({ ...formData, campaign_type: e.target.value as any })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    >
                      <option value="coupon">Kupon</option>
                      <option value="flash_sale">Flash Sale</option>
                      <option value="bulk_discount">Toplu İndirim</option>
                      <option value="category_discount">Kategori İndirimi</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">İndirim Tipi *</label>
                    <select
                      required
                      value={formData.discount_type}
                      onChange={(e) => setFormData({ ...formData, discount_type: e.target.value as any })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    >
                      <option value="percentage">Yüzde (%)</option>
                      <option value="fixed_amount">Sabit Tutar (₺)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">İndirim Değeri *</label>
                    <input
                      type="number"
                      required
                      min="0"
                      step="0.01"
                      value={formData.discount_value}
                      onChange={(e) => setFormData({ ...formData, discount_value: parseFloat(e.target.value) })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Min. Alışveriş Tutarı</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={formData.min_purchase_amount}
                      onChange={(e) => setFormData({ ...formData, min_purchase_amount: parseFloat(e.target.value) || 0 })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>
                </div>

                {formData.campaign_type === 'coupon' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Kupon Kodu (boş bırakılırsa otomatik oluşturulur)</label>
                    <input
                      type="text"
                      value={formData.coupon_code}
                      onChange={(e) => setFormData({ ...formData, coupon_code: e.target.value.toUpperCase() })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent font-mono"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Başlangıç Tarihi *</label>
                    <input
                      type="date"
                      required
                      value={formData.start_date}
                      onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Bitiş Tarihi *</label>
                    <input
                      type="date"
                      required
                      value={formData.end_date}
                      onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Kullanım Limiti (boş = sınırsız)</label>
                    <input
                      type="number"
                      min="1"
                      value={formData.usage_limit || ''}
                      onChange={(e) => setFormData({ ...formData, usage_limit: e.target.value ? parseInt(e.target.value) : null })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Müşteri Başına Max. Kullanım</label>
                    <input
                      type="number"
                      min="1"
                      value={formData.max_usage_per_customer}
                      onChange={(e) => setFormData({ ...formData, max_usage_per_customer: parseInt(e.target.value) || 1 })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="flex space-x-2 pt-4 border-t">
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition flex items-center justify-center"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Kaydet
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
                  >
                    İptal
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

