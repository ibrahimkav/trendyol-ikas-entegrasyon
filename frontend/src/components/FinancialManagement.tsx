import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { DollarSign, TrendingUp, TrendingDown, Calculator, Plus, Edit, Trash2, Settings, BarChart2, ShoppingCart } from 'lucide-react'

interface FinancialSummary {
  period: string
  start_date: string
  end_date: string
  total_revenue: number
  total_vat?: number
  vat_rate?: number
  total_commission: number
  total_cargo_cost: number
  total_expenses: number
  net_profit: number
  order_count: number
  average_order_value: number
  profit_margin: number
  cargo_cost_per_product?: number
  note?: string
}

interface Expense {
  id?: string
  name: string
  amount: number
  category: string
  date: string
  description?: string
  created_at?: string
}

interface OrderProfitability {
  order_number: string
  order_date: string
  customer_name: string
  total_revenue: number
  vat: number
  commission: number
  cargo_cost: number
  product_cost: number
  net_profit: number
  profit_margin: number
  status: string
}

interface ProductProfitability {
  product_id: string
  product_name: string
  total_quantity: number
  total_revenue: number
  total_cost: number
  total_commission: number
  total_cargo: number
  net_profit: number
  profit_margin: number
  low_margin: boolean
}

export default function FinancialManagement() {
  const toast = useToast()
  const [summary, setSummary] = useState<FinancialSummary | null>(null)
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly' | 'yearly'>('monthly')
  const [showExpenseModal, setShowExpenseModal] = useState(false)
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)
  const [showCommissionCalculator, setShowCommissionCalculator] = useState(false)
  const [showCargoSetting, setShowCargoSetting] = useState(false)
  const [cargoCostPerProduct, setCargoCostPerProduct] = useState(75.0)
  const [activeTab, setActiveTab] = useState<'summary' | 'orders' | 'products'>('summary')
  // Bu state'ler henüz UI'da render edilmiyor (Wave 2 kapsamı) — sadece setter kullanılıyor.
  const [, setOrderProfitability] = useState<OrderProfitability[]>([])
  const [, setProductProfitability] = useState<ProductProfitability[]>([])
  const [profitLoading, setProfitLoading] = useState(false)

  const [expenseForm, setExpenseForm] = useState({
    name: '',
    amount: 0,
    category: 'diğer',
    date: new Date().toISOString().split('T')[0],
    description: ''
  })

  const [commissionCalc, setCommissionCalc] = useState({
    amount: 0,
    category: ''
  })

  useEffect(() => {
    fetchSummary()
    fetchExpenses()
    fetchCargoSetting()
  }, [period])

  useEffect(() => {
    if (activeTab === 'orders') {
      fetchOrderProfitability()
    } else if (activeTab === 'products') {
      fetchProductProfitability()
    }
  }, [activeTab])

  const fetchCargoSetting = async () => {
    try {
      const response = await apiClient.get('/financial/cargo-cost-setting')
      setCargoCostPerProduct(response.data.cargo_cost_per_product || 75.0)
    } catch (err: any) {
      console.error('Kargo ayarı yüklenemedi:', err)
    }
  }

  const updateCargoSetting = async () => {
    try {
      await apiClient.put('/financial/cargo-cost-setting', { cargo_cost_per_product: cargoCostPerProduct })
      setShowCargoSetting(false)
      fetchSummary()
      toast({ type: 'success', message: 'Kargo maliyeti güncellendi.' })
    } catch (err: any) {
      toast({
        type: 'error',
        message: 'Kargo maliyeti güncellenemedi: ' + (err.response?.data?.detail || err.message),
      })
    }
  }

  const fetchSummary = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get(`/financial/summary?period=${period}`)
      setSummary(response.data)
    } catch (err: any) {
      setError('Finansal özet yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchExpenses = async () => {
    try {
      const response = await apiClient.get('/financial/expenses')
      setExpenses(response.data.expenses || [])
    } catch (err: any) {
      console.error('Giderler yüklenemedi:', err)
    }
  }

  const fetchOrderProfitability = async () => {
    setProfitLoading(true)
    try {
      const response = await apiClient.get('/financial/order-profitability?limit=100')
      setOrderProfitability(response.data.orders || [])
    } catch (err: any) {
      console.error('Sipariş kârlılığı yüklenemedi:', err)
    } finally {
      setProfitLoading(false)
    }
  }

  const fetchProductProfitability = async () => {
    setProfitLoading(true)
    try {
      const response = await apiClient.get('/financial/product-profitability')
      setProductProfitability(response.data.products || [])
    } catch (err: any) {
      console.error('Ürün kârlılığı yüklenemedi:', err)
    } finally {
      setProfitLoading(false)
    }
  }

  const handleCreateExpense = async () => {
    try {
      if (editingExpense) {
        await apiClient.put(`/financial/expenses/${editingExpense.id}`, expenseForm)
      } else {
        await apiClient.post('/financial/expenses', expenseForm)
      }
      setShowExpenseModal(false)
      setEditingExpense(null)
      setExpenseForm({
        name: '',
        amount: 0,
        category: 'diğer',
        date: new Date().toISOString().split('T')[0],
        description: ''
      })
      fetchExpenses()
      fetchSummary()
    } catch (err: any) {
      toast({ type: 'error', message: 'Gider kaydedilemedi: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const handleDeleteExpense = async (expenseId: string) => {
    if (!confirm('Bu gideri silmek istediğinizden emin misiniz?')) {
      return
    }

    try {
      await apiClient.delete(`/financial/expenses/${expenseId}`)
      fetchExpenses()
      fetchSummary()
    } catch (err: any) {
      toast({ type: 'error', message: 'Gider silinemedi: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const handleEditExpense = (expense: Expense) => {
    setEditingExpense(expense)
    setExpenseForm({
      name: expense.name,
      amount: expense.amount,
      category: expense.category,
      date: expense.date,
      description: expense.description || ''
    })
    setShowExpenseModal(true)
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
      minimumFractionDigits: 2
    }).format(amount)
  }

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      kargo: 'Kargo',
      reklam: 'Reklam',
      stok: 'Stok',
      diğer: 'Diğer'
    }
    return labels[category] || category
  }

  const getPeriodLabel = (p: string) => {
    const labels: Record<string, string> = {
      daily: 'Günlük',
      weekly: 'Haftalık',
      monthly: 'Aylık',
      yearly: 'Yıllık'
    }
    return labels[p] || p
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Finansal yönetim</h1>
          <p className="page-subtitle">Gelir/gider takibi ve komisyon hesaplama</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowCargoSetting(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition"
          >
            <Settings className="w-4 h-4" />
            <span>Kargo Ayarı</span>
          </button>
          <button
            onClick={() => setShowCommissionCalculator(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            <Calculator className="w-4 h-4" />
            <span>Komisyon Hesapla</span>
          </button>
          <button
            onClick={() => {
              setEditingExpense(null)
              setShowExpenseModal(true)
            }}
            className="flex items-center space-x-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
          >
            <Plus className="w-4 h-4" />
            <span>Gider Ekle</span>
          </button>
        </div>
      </div>

      {/* Period Selection */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center space-x-2">
          {(['daily', 'weekly', 'monthly', 'yearly'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 rounded-lg transition ${
                period === p
                  ? 'bg-brand text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {getPeriodLabel(p)}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px" aria-label="Tabs">
            {[
              { id: 'summary', label: 'Özet', icon: DollarSign },
              { id: 'orders', label: 'Sipariş Kârlılığı', icon: ShoppingCart },
              { id: 'products', label: 'Ürün Kârlılığı', icon: BarChart2 },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition ${
                  activeTab === tab.id
                    ? 'border-brand text-brand'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Loading */}
      {(activeTab === 'summary' ? loading : profitLoading) && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand mx-auto mb-4"></div>
          <p className="text-gray-600">Yükleniyor...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Summary Tab */}
      {activeTab === 'summary' && !loading && !error && summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Toplam Gelir</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(summary.total_revenue)}</p>
              </div>
              <DollarSign className="w-8 h-8 text-green-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">KDV (%{summary.vat_rate || 10})</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(summary.total_vat || 0)}</p>
              </div>
              <TrendingDown className="w-8 h-8 text-purple-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Toplam Komisyon</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(summary.total_commission)}</p>
              </div>
              <TrendingDown className="w-8 h-8 text-red-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Toplam Gider</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(summary.total_expenses + summary.total_cargo_cost)}</p>
                {summary.total_cargo_cost === 0 && (
                  <p className="text-xs text-gray-500 mt-1">Kargo: API'den alınamadı</p>
                )}
              </div>
              <TrendingDown className="w-8 h-8 text-orange-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Net Kâr</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(summary.net_profit)}</p>
                <p className="text-sm text-gray-500 mt-1">%{summary.profit_margin} kâr marjı</p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-600" />
            </div>
          </div>
        </div>
      )}

      {/* Info Note */}
      {!loading && !error && summary && summary.note && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">{summary.note}</p>
        </div>
      )}

      {/* Detailed Breakdown */}
      {!loading && !error && summary && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Detaylı Döküm</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-700 mb-3">Gelirler</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Toplam Gelir:</span>
                  <span className="font-medium">{formatCurrency(summary.total_revenue)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Sipariş Sayısı:</span>
                  <span className="font-medium">{summary.order_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Ortalama Sipariş:</span>
                  <span className="font-medium">{formatCurrency(summary.average_order_value)}</span>
                </div>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-700 mb-3">Giderler</h3>
              <div className="space-y-2">
                {summary.total_vat !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">KDV (%{summary.vat_rate || 10}):</span>
                    <span className="font-medium text-red-600">-{formatCurrency(summary.total_vat)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-600">Komisyon:</span>
                  <span className="font-medium text-red-600">-{formatCurrency(summary.total_commission)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">
                    Kargo {summary.cargo_cost_per_product && `(Ürün başına ${formatCurrency(summary.cargo_cost_per_product)})`}:
                  </span>
                  <span className="font-medium text-red-600">
                    -{formatCurrency(summary.total_cargo_cost)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Diğer Giderler:</span>
                  <span className="font-medium text-red-600">-{formatCurrency(summary.total_expenses)}</span>
                </div>
                <div className="flex justify-between pt-2 border-t border-gray-200">
                  <span className="font-semibold text-gray-900">Net Kâr:</span>
                  <span className={`font-bold ${summary.net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(summary.net_profit)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Expenses List */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Giderler</h2>
          <span className="text-sm text-gray-600">
            Toplam: {formatCurrency(expenses.reduce((sum, exp) => sum + exp.amount, 0))}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tarih</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Açıklama</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Kategori</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tutar</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">İşlemler</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {expenses.map((expense) => (
                <tr key={expense.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                    {new Date(expense.date).toLocaleDateString('tr-TR')}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">{expense.name}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                    {getCategoryLabel(expense.category)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-red-600">
                    -{formatCurrency(expense.amount)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleEditExpense(expense)}
                        className="text-yellow-600 hover:text-yellow-800"
                        title="Düzenle"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteExpense(expense.id!)}
                        className="text-red-600 hover:text-red-800"
                        title="Sil"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {expenses.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <p>Henüz gider eklenmemiş</p>
            </div>
          )}
        </div>
      </div>

      {/* Expense Modal */}
      {showExpenseModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              {editingExpense ? 'Gideri Düzenle' : 'Yeni Gider Ekle'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Açıklama</label>
                <input
                  type="text"
                  value={expenseForm.name}
                  onChange={(e) => setExpenseForm({ ...expenseForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tutar (₺)</label>
                <input
                  type="number"
                  step="0.01"
                  value={expenseForm.amount}
                  onChange={(e) => setExpenseForm({ ...expenseForm, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
                <select
                  value={expenseForm.category}
                  onChange={(e) => setExpenseForm({ ...expenseForm, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                >
                  <option value="kargo">Kargo</option>
                  <option value="reklam">Reklam</option>
                  <option value="stok">Stok</option>
                  <option value="diğer">Diğer</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tarih</label>
                <input
                  type="date"
                  value={expenseForm.date}
                  onChange={(e) => setExpenseForm({ ...expenseForm, date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Not (Opsiyonel)</label>
                <textarea
                  value={expenseForm.description}
                  onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowExpenseModal(false)
                  setEditingExpense(null)
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                İptal
              </button>
              <button
                onClick={handleCreateExpense}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
              >
                {editingExpense ? 'Güncelle' : 'Ekle'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cargo Cost Setting Modal */}
      {showCargoSetting && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Kargo Maliyeti Ayarı</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ürün Başına Kargo Maliyeti (₺)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={cargoCostPerProduct}
                  onChange={(e) => setCargoCostPerProduct(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Her ürün için {formatCurrency(cargoCostPerProduct)} kargo maliyeti hesaplanacak
                </p>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-sm text-yellow-800">
                  ⚠️ Bu değişiklik geçicidir. Kalıcı olması için backend'deki .env dosyasındaki CARGO_COST_PER_PRODUCT değişkenini güncelleyin.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowCargoSetting(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                İptal
              </button>
              <button
                onClick={updateCargoSetting}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
              >
                Güncelle
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Commission Calculator Modal */}
      {showCommissionCalculator && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Komisyon Hesaplayıcı</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tutar (₺)</label>
                <input
                  type="number"
                  step="0.01"
                  value={commissionCalc.amount}
                  onChange={(e) => setCommissionCalc({ ...commissionCalc, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Kategori (Opsiyonel)</label>
                <select
                  value={commissionCalc.category}
                  onChange={(e) => setCommissionCalc({ ...commissionCalc, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand"
                >
                  <option value="">Genel (%10)</option>
                  <option value="elektronik">Elektronik (%12)</option>
                  <option value="giyim">Giyim (%15)</option>
                  <option value="ev_yasam">Ev & Yaşam (%10)</option>
                  <option value="kozmetik">Kozmetik (%12)</option>
                </select>
              </div>

              {commissionCalc.amount > 0 && (
                <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Tutar:</span>
                    <span className="font-medium">{formatCurrency(commissionCalc.amount)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Komisyon (%{commissionCalc.category === 'elektronik' ? '12' : commissionCalc.category === 'giyim' ? '15' : '10'}):</span>
                    <span className="font-medium text-red-600">
                      -{formatCurrency(commissionCalc.amount * (commissionCalc.category === 'elektronik' ? 0.12 : commissionCalc.category === 'giyim' ? 0.15 : 0.10))}
                    </span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-gray-200">
                    <span className="font-semibold text-gray-900">Net Tutar:</span>
                    <span className="font-bold text-green-600">
                      {formatCurrency(commissionCalc.amount * (1 - (commissionCalc.category === 'elektronik' ? 0.12 : commissionCalc.category === 'giyim' ? 0.15 : 0.10)))}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end mt-6">
              <button
                onClick={() => setShowCommissionCalculator(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

