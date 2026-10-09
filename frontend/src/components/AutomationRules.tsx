import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { Settings, Plus, Trash2, Edit, Play, Pause, CheckCircle, XCircle, Sparkles, Package, TrendingUp } from 'lucide-react'

interface AutomationRule {
  id?: string
  name: string
  rule_type: string
  enabled: boolean
  conditions: Record<string, any>
  actions: Record<string, any>
  created_at?: string
  updated_at?: string
}

interface RuleTemplate {
  name: string
  rule_type: string
  description: string
  conditions: Record<string, any>
  actions: Record<string, any>
}

export default function AutomationRules() {
  const toast = useToast()
  const [rules, setRules] = useState<AutomationRule[]>([])
  const [templates, setTemplates] = useState<RuleTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null)
  // const [selectedTemplate, setSelectedTemplate] = useState<RuleTemplate | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    rule_type: 'stock_based_price',
    enabled: true,
    conditions: {
      min_stock: 10,
      max_stock: 100,
      min_sales: 50,
      min_revenue: 1000,
      low_stock_action: true,
      high_stock_action: true
    },
    actions: {
      low_stock_price_change_type: 'percentage',
      low_stock_price_change_value: 10,
      high_stock_price_change_type: 'percentage',
      high_stock_price_change_value: 5,
      price_change_type: 'percentage',
      price_change_value: 5
    }
  })

  useEffect(() => {
    fetchRules()
    fetchTemplates()
  }, [])

  const fetchRules = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get('/automation/rules')
      setRules(response.data.rules || [])
    } catch (err: any) {
      setError('Kurallar yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/automation/templates')
      setTemplates(response.data.templates || [])
    } catch (err: any) {
      console.error('Şablonlar yüklenemedi:', err)
    }
  }

  const handleCreateRule = async () => {
    try {
      if (editingRule) {
        await apiClient.put(`/automation/rules/${editingRule.id}`, formData)
      } else {
        await apiClient.post('/automation/rules', formData)
      }
      setShowCreateModal(false)
      setEditingRule(null)
      setFormData({
        name: '',
        rule_type: 'stock_based_price',
        enabled: true,
        conditions: {
          min_stock: 10,
          max_stock: 100,
          min_sales: 50,
          min_revenue: 1000,
          low_stock_action: true,
          high_stock_action: true
        },
        actions: {
          low_stock_price_change_type: 'percentage',
          low_stock_price_change_value: 10,
          high_stock_price_change_type: 'percentage',
          high_stock_price_change_value: 5,
          price_change_type: 'percentage',
          price_change_value: 5
        }
      })
      fetchRules()
    } catch (err: any) {
      toast({ type: 'error', message: 'Kural kaydedilemedi: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Bu kuralı silmek istediğinizden emin misiniz?')) {
      return
    }

    try {
      await apiClient.delete(`/automation/rules/${ruleId}`)
      fetchRules()
    } catch (err: any) {
      toast({ type: 'error', message: 'Kural silinemedi: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const handleToggleRule = async (ruleId: string) => {
    try {
      await apiClient.post(`/automation/rules/${ruleId}/toggle`)
      fetchRules()
    } catch (err: any) {
      toast({
        type: 'error',
        message: 'Kural durumu değiştirilemedi: ' + (err.response?.data?.detail || err.message),
      })
    }
  }

  const handleExecuteRule = async (ruleId: string) => {
    try {
      const response = await apiClient.get(`/automation/rules/${ruleId}/execute`)
      const count = response.data.result.total_updated || 0
      // DÜRÜSTLÜK: /execute sadece bellekte fiyat HESAPLIYOR — ne Trendyol'a yazıyor ne DB'ye
      // (backend/routers/automation.py'de db.commit/requests.post yok, sadece updated_products
      // listesi dönüyor). "Güncellendi" demek kullanıcıyı Trendyol'da fiyatın değiştiğine
      // inandırıp kontrolü bıraktırabilir — bkz. w3-automation-honest-toast.
      toast({
        type: 'info',
        message:
          count > 0
            ? `Kural çalıştırıldı. ${count} ürün için yeni fiyat hesaplandı (Trendyol'a veya veritabanına yazılmadı).`
            : 'Kural çalıştırıldı. Koşullara uyan ürün bulunamadı, hesaplanan bir fiyat yok.',
      })
    } catch (err: any) {
      toast({ type: 'error', message: 'Kural çalıştırılamadı: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const handleUseTemplate = (template: RuleTemplate) => {
    setFormData({
      name: template.name,
      rule_type: template.rule_type,
      enabled: true,
      conditions: template.conditions as any,
      actions: template.actions as any
    })
    // setSelectedTemplate(null)
    setShowTemplateModal(false)
    setShowCreateModal(true)
  }

  const handleEditRule = (rule: AutomationRule) => {
    setEditingRule(rule)
    setFormData({
      name: rule.name,
      rule_type: rule.rule_type,
      enabled: rule.enabled,
      conditions: rule.conditions as any,
      actions: rule.actions as any
    })
    setShowCreateModal(true)
  }

  const getRuleTypeLabel = (type: string) => {
    switch (type) {
      case 'stock_based_price':
        return 'Stok Bazlı Fiyat'
      case 'price_update':
        return 'Fiyat Güncelleme'
      default:
        return type
    }
  }

  const getRuleTypeIcon = (type: string) => {
    switch (type) {
      case 'stock_based_price':
        return <Package className="w-5 h-5" />
      case 'price_update':
        return <TrendingUp className="w-5 h-5" />
      default:
        return <Settings className="w-5 h-5" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Otomasyon kuralları</h1>
          <p className="page-subtitle">Otomatik fiyat güncelleme ve stok bazlı kurallar</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setShowTemplateModal(true)
            }}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            <Sparkles className="w-4 h-4" />
            <span>Şablon Kullan</span>
          </button>
          <button
            onClick={() => {
              setEditingRule(null)
              setShowCreateModal(true)
            }}
            className="flex items-center space-x-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
          >
            <Plus className="w-4 h-4" />
            <span>Yeni Kural</span>
          </button>
        </div>
      </div>

      {/* w3-automation-honest-toast: kalıcı durustluk notu — bu ekran ne yaptığını, ne yapmadığını
          söylemeli. "Çalıştır" sadece bellekte fiyat hesaplar, Trendyol'a/DB'ye yazmaz; kurallar da
          sunucu belleğinde tutuluyor, DB modeli yok. */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        Bu ekran şu an yalnızca <strong>öneri hesaplıyor</strong> — bir kuralı çalıştırdığınızda hesaplanan yeni
        fiyatlar Trendyol'a veya veritabanına yazılmaz; fiyatı gerçekten değiştirmek için Ürün Fiyatlandırma
        ekranını kullanmanız gerekir. Ayrıca kurallar şu an sunucu belleğinde tutuluyor — sunucu yeniden
        başlatılırsa oluşturduğunuz kurallar kaybolur.
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand mx-auto mb-4"></div>
          <p className="text-gray-600">Kurallar yükleniyor...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Rules List */}
      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`bg-white rounded-lg shadow p-6 border-2 ${
                rule.enabled ? 'border-green-200' : 'border-gray-200'
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${
                    rule.enabled ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {getRuleTypeIcon(rule.rule_type)}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900">{rule.name}</h3>
                    <p className="text-sm text-gray-500">{getRuleTypeLabel(rule.rule_type)}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-1">
                  {rule.enabled ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <XCircle className="w-5 h-5 text-gray-400" />
                  )}
                </div>
              </div>

              <div className="space-y-2 mb-4">
                {rule.rule_type === 'stock_based_price' && (
                  <>
                    {rule.conditions.low_stock_action && (
                      <p className="text-sm text-gray-600">
                        Düşük stok ({rule.conditions.min_stock || 10}): Fiyatı{' '}
                        {rule.actions.low_stock_price_change_type === 'percentage' ? '%' : '₺'}{' '}
                        {rule.actions.low_stock_price_change_value} {rule.actions.low_stock_price_change_type === 'percentage' ? 'artır' : 'ekle'}
                      </p>
                    )}
                    {rule.conditions.high_stock_action && (
                      <p className="text-sm text-gray-600">
                        Yüksek stok ({rule.conditions.max_stock || 100}): Fiyatı{' '}
                        {rule.actions.high_stock_price_change_type === 'percentage' ? '%' : '₺'}{' '}
                        {rule.actions.high_stock_price_change_value} {rule.actions.high_stock_price_change_type === 'percentage' ? 'düşür' : 'azalt'}
                      </p>
                    )}
                  </>
                )}
                {rule.rule_type === 'price_update' && (
                  <p className="text-sm text-gray-600">
                    {rule.conditions.min_sales && `Min satış: ${rule.conditions.min_sales}`}
                    {rule.conditions.min_revenue && ` Min gelir: ${rule.conditions.min_revenue}₺`}
                    {' → '}
                    Fiyatı {rule.actions.price_change_type === 'percentage' ? '%' : '₺'}{' '}
                    {rule.actions.price_change_value} {rule.actions.price_change_type === 'percentage' ? 'artır' : 'ekle'}
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2 pt-4 border-t border-gray-200">
                <button
                  onClick={() => handleToggleRule(rule.id!)}
                  className={`flex-1 flex items-center justify-center space-x-2 px-3 py-2 rounded-lg transition ${
                    rule.enabled
                      ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      : 'bg-green-100 text-green-700 hover:bg-green-200'
                  }`}
                >
                  {rule.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  <span className="text-sm">{rule.enabled ? 'Pasif Et' : 'Aktif Et'}</span>
                </button>
                <button
                  onClick={() => handleExecuteRule(rule.id!)}
                  className="flex items-center justify-center px-3 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition"
                  title="Fiyat Hesapla (Trendyol'a veya veritabanına yazmaz)"
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEditRule(rule)}
                  className="flex items-center justify-center px-3 py-2 bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200 transition"
                  title="Düzenle"
                >
                  <Edit className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDeleteRule(rule.id!)}
                  className="flex items-center justify-center px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition"
                  title="Sil"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}

          {rules.length === 0 && (
            <div className="col-span-full bg-white rounded-lg shadow p-12 text-center">
              <Settings className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-4">Henüz kural oluşturulmamış</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
              >
                İlk Kuralınızı Oluşturun
              </button>
            </div>
          )}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              {editingRule ? 'Kuralı Düzenle' : 'Yeni Kural Oluştur'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Kural Adı</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Kural Tipi</label>
                <select
                  value={formData.rule_type}
                  onChange={(e) => setFormData({ ...formData, rule_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                >
                  <option value="stock_based_price">Stok Bazlı Fiyat</option>
                  <option value="price_update">Fiyat Güncelleme</option>
                </select>
              </div>

              {formData.rule_type === 'stock_based_price' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Min Stok</label>
                      <input
                        type="number"
                        value={formData.conditions.min_stock}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, min_stock: parseInt(e.target.value) }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Max Stok</label>
                      <input
                        type="number"
                        value={formData.conditions.max_stock}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, max_stock: parseInt(e.target.value) }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={formData.conditions.low_stock_action}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, low_stock_action: e.target.checked }
                          })
                        }
                        className="w-4 h-4"
                      />
                      <label className="text-sm font-medium text-gray-700">Düşük Stokta Fiyat Artır</label>
                    </div>

                    {formData.conditions.low_stock_action && (
                      <div className="ml-6 grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-600 mb-1">Değişim Tipi</label>
                          <select
                            value={formData.actions.low_stock_price_change_type}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                actions: { ...formData.actions, low_stock_price_change_type: e.target.value }
                              })
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          >
                            <option value="percentage">Yüzde (%)</option>
                            <option value="fixed">Sabit (₺)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm text-gray-600 mb-1">Değer</label>
                          <input
                            type="number"
                            value={formData.actions.low_stock_price_change_value}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                actions: { ...formData.actions, low_stock_price_change_value: parseFloat(e.target.value) }
                              })
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={formData.conditions.high_stock_action}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, high_stock_action: e.target.checked }
                          })
                        }
                        className="w-4 h-4"
                      />
                      <label className="text-sm font-medium text-gray-700">Yüksek Stokta Fiyat Düşür</label>
                    </div>

                    {formData.conditions.high_stock_action && (
                      <div className="ml-6 grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-600 mb-1">Değişim Tipi</label>
                          <select
                            value={formData.actions.high_stock_price_change_type}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                actions: { ...formData.actions, high_stock_price_change_type: e.target.value }
                              })
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          >
                            <option value="percentage">Yüzde (%)</option>
                            <option value="fixed">Sabit (₺)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm text-gray-600 mb-1">Değer</label>
                          <input
                            type="number"
                            value={formData.actions.high_stock_price_change_value}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                actions: { ...formData.actions, high_stock_price_change_value: parseFloat(e.target.value) }
                              })
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              {formData.rule_type === 'price_update' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Min Satış</label>
                      <input
                        type="number"
                        value={formData.conditions.min_sales}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, min_sales: parseInt(e.target.value) }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Min Gelir (₺)</label>
                      <input
                        type="number"
                        value={formData.conditions.min_revenue}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            conditions: { ...formData.conditions, min_revenue: parseFloat(e.target.value) }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Fiyat Değişim Tipi</label>
                      <select
                        value={formData.actions.price_change_type}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            actions: { ...formData.actions, price_change_type: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      >
                        <option value="percentage">Yüzde (%)</option>
                        <option value="fixed">Sabit (₺)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Değer</label>
                      <input
                        type="number"
                        value={formData.actions.price_change_value}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            actions: { ...formData.actions, price_change_value: parseFloat(e.target.value) }
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      />
                    </div>
                  </div>
                </>
              )}

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="w-4 h-4"
                />
                <label className="text-sm font-medium text-gray-700">Kuralı Aktif Et</label>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setEditingRule(null)
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                İptal
              </button>
              <button
                onClick={handleCreateRule}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
              >
                {editingRule ? 'Güncelle' : 'Oluştur'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Template Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Şablon Seç</h2>

            <div className="space-y-4">
              {templates.map((template, idx) => (
                <div
                  key={idx}
                  className="border border-gray-200 rounded-lg p-4 hover:border-brand transition cursor-pointer"
                  onClick={() => handleUseTemplate(template)}
                >
                  <h3 className="font-bold text-gray-900 mb-1">{template.name}</h3>
                  <p className="text-sm text-gray-600">{template.description}</p>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end mt-6">
              <button
                onClick={() => setShowTemplateModal(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                İptal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


