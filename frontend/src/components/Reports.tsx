import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { Download, Calendar, TrendingUp, Package, DollarSign, BarChart3, RefreshCw } from 'lucide-react'

interface DailyReport {
  date: string
  total_orders: number
  total_revenue: number
  total_quantity: number
  average_order_value: number
  orders: any[]
}

interface WeeklyReport {
  week_start: string
  week_end: string
  total_orders: number
  total_revenue: number
  total_quantity: number
  average_order_value: number
  daily_stats: Array<{
    date: string
    orders: number
    revenue: number
    quantity: number
  }>
  orders: any[]
}

interface MonthlyReport {
  year: number
  month: number
  month_name: string
  start_date: string
  end_date: string
  total_orders: number
  total_revenue: number
  total_quantity: number
  average_order_value: number
  average_daily_revenue: number
  daily_stats: Array<{
    date: string
    orders: number
    revenue: number
    quantity: number
  }>
  orders: any[]
}

interface YearlyReport {
  year: number
  start_date: string
  end_date: string
  total_orders: number
  total_revenue: number
  total_quantity: number
  average_order_value: number
  average_daily_revenue: number
  average_monthly_revenue: number
  monthly_stats: Array<{
    month: string
    orders: number
    revenue: number
    quantity: number
  }>
  daily_stats: Array<{
    date: string
    orders: number
    revenue: number
    quantity: number
  }>
  orders: any[]
}

export default function Reports() {
  const toast = useToast()
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly' | 'yearly'>('monthly')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reportData, setReportData] = useState<DailyReport | WeeklyReport | MonthlyReport | YearlyReport | null>(null)
  
  // Tarih seçimi
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [selectedWeek, setSelectedWeek] = useState('')
  const [selectedMonth, setSelectedMonth] = useState(
    `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`
  )
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear().toString())

  useEffect(() => {
    fetchReport()
  }, [period, selectedDate, selectedWeek, selectedMonth, selectedYear])

  const fetchReport = async () => {
    setLoading(true)
    setError(null)
    
    try {
      let url = ''
      if (period === 'daily') {
        url = `/reports/daily?date=${selectedDate}`
      } else if (period === 'weekly') {
        url = `/reports/weekly${selectedWeek ? `?week_start=${selectedWeek}` : ''}`
      } else if (period === 'monthly') {
        const parts = selectedMonth.split('-').map(Number)
        const year = parts[0]
        const month = parts[1]
        url = `/reports/monthly?year=${year}&month=${month}`
      } else if (period === 'yearly') {
        url = `/reports/yearly?year=${selectedYear}`
      }
      
      console.log('[Reports] Fetching:', url)
      const response = await apiClient.get(url)
      console.log('[Reports] Response:', response.data)
      setReportData(response.data)
      
      if (response.data.total_orders === 0) {
        setError('Bu dönem için sipariş bulunamadı.')
      }
    } catch (err: any) {
      console.error('[Reports] Error:', err)
      setError('Rapor yüklenemedi: ' + (err.response?.data?.detail || err.message || 'Bilinmeyen hata'))
    } finally {
      setLoading(false)
    }
  }

  const exportReport = async (format: 'csv' | 'json') => {
    try {
      let url = ''
      if (period === 'daily') {
        url = `/reports/export/${format}?period=daily&date=${selectedDate}`
      } else if (period === 'weekly') {
        url = `/reports/export/${format}?period=weekly${selectedWeek ? `&date=${selectedWeek}` : ''}`
      } else if (period === 'monthly') {
        url = `/reports/export/${format}?period=monthly&date=${selectedMonth}`
      } else if (period === 'yearly') {
        url = `/reports/export/${format}?period=yearly&date=${selectedYear}`
      }
      
      if (format === 'csv') {
        const response = await apiClient.get(url, { 
          responseType: 'blob',
          headers: {
            'Accept': 'text/csv'
          }
        })
        const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8-sig;' })
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `rapor_${period}_${new Date().toISOString().split('T')[0]}.csv`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(link.href)
      } else {
        const response = await apiClient.get(url)
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `rapor_${period}_${new Date().toISOString().split('T')[0]}.json`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(link.href)
      }
    } catch (err: any) {
      toast({ type: 'error', message: 'Rapor export edilemedi: ' + (err.response?.data?.detail || err.message) })
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
      minimumFractionDigits: 2
    }).format(amount)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('tr-TR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Raporlama</h1>
          <p className="page-subtitle">Günlük, haftalık ve aylık raporlar</p>
        </div>
        {reportData && (
          <div className="flex items-center space-x-2">
            <button
              onClick={() => exportReport('csv')}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
            >
              <Download className="w-4 h-4" />
              <span>CSV İndir</span>
            </button>
            <button
              onClick={() => exportReport('json')}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              <Download className="w-4 h-4" />
              <span>JSON İndir</span>
            </button>
          </div>
        )}
      </div>

      {/* Period Seçimi */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center space-x-4 mb-4">
          <button
            onClick={() => setPeriod('daily')}
            className={`px-4 py-2 rounded-lg transition ${
              period === 'daily'
                ? 'bg-trendyol-primary text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Günlük
          </button>
          <button
            onClick={() => setPeriod('weekly')}
            className={`px-4 py-2 rounded-lg transition ${
              period === 'weekly'
                ? 'bg-trendyol-primary text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Haftalık
          </button>
          <button
            onClick={() => setPeriod('monthly')}
            className={`px-4 py-2 rounded-lg transition ${
              period === 'monthly'
                ? 'bg-trendyol-primary text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Aylık
          </button>
          <button
            onClick={() => setPeriod('yearly')}
            className={`px-4 py-2 rounded-lg transition ${
              period === 'yearly'
                ? 'bg-trendyol-primary text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Yıllık
          </button>
        </div>

        <div className="flex items-center space-x-4">
          {period === 'daily' && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-5 h-5 text-gray-500" />
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-trendyol-primary"
              />
            </div>
          )}
          {period === 'weekly' && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-5 h-5 text-gray-500" />
              <input
                type="date"
                value={selectedWeek}
                onChange={(e) => setSelectedWeek(e.target.value)}
                placeholder="Hafta başlangıcı (Pazartesi)"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-trendyol-primary"
              />
              <span className="text-sm text-gray-500">(Pazartesi seçin)</span>
            </div>
          )}
          {period === 'monthly' && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-5 h-5 text-gray-500" />
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-trendyol-primary"
              />
            </div>
          )}
          {period === 'yearly' && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-5 h-5 text-gray-500" />
              <input
                type="number"
                value={selectedYear}
                onChange={(e) => setSelectedYear(e.target.value)}
                min="2020"
                max={new Date().getFullYear()}
                placeholder="Yıl"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-trendyol-primary w-32"
              />
            </div>
          )}
          <button
            onClick={fetchReport}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Yenile</span>
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-trendyol-primary mb-4" />
          <p className="text-gray-600">Rapor yükleniyor...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Report Data */}
      {!loading && !error && reportData && (
        <div className="space-y-6">
          {/* Özet Kartları */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Toplam Sipariş</p>
                  <p className="text-2xl font-bold text-gray-900">{reportData.total_orders}</p>
                </div>
                <Package className="w-8 h-8 text-trendyol-primary" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Toplam Gelir</p>
                  <p className="text-2xl font-bold text-gray-900">{formatCurrency(reportData.total_revenue)}</p>
                </div>
                <DollarSign className="w-8 h-8 text-green-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Toplam Ürün</p>
                  <p className="text-2xl font-bold text-gray-900">{reportData.total_quantity}</p>
                </div>
                <BarChart3 className="w-8 h-8 text-blue-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Ortalama Sipariş</p>
                  <p className="text-2xl font-bold text-gray-900">{formatCurrency(reportData.average_order_value)}</p>
                </div>
                <TrendingUp className="w-8 h-8 text-purple-600" />
              </div>
            </div>
          </div>

          {/* Günlük İstatistikler (Haftalık ve Aylık için) */}
          {(period === 'weekly' || period === 'monthly') && 'daily_stats' in reportData && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">
                {period === 'weekly' ? 'Haftalık' : 'Aylık'} Günlük Dağılım
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Tarih
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Sipariş
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Gelir
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ürün
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {reportData.daily_stats.map((stat, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {formatDate(stat.date)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {stat.orders}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                          {formatCurrency(stat.revenue)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {stat.quantity}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Aylık Rapor için Ekstra Bilgi */}
          {period === 'monthly' && 'average_daily_revenue' in reportData && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Ortalama Günlük Gelir</p>
                  <p className="text-xl font-bold text-gray-900">
                    {formatCurrency((reportData as MonthlyReport).average_daily_revenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Dönem</p>
                  <p className="text-xl font-bold text-gray-900">
                    {formatDate((reportData as MonthlyReport).start_date)} - {formatDate((reportData as MonthlyReport).end_date)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Yıllık Rapor için Aylık İstatistikler */}
          {period === 'yearly' && 'monthly_stats' in reportData && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Aylık Dağılım</h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ay
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Sipariş
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Gelir
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ürün
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(reportData as YearlyReport).monthly_stats.map((stat, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {new Date(stat.month + '-01').toLocaleDateString('tr-TR', { year: 'numeric', month: 'long' })}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {stat.orders}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                          {formatCurrency(stat.revenue)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                          {stat.quantity}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Yıllık Rapor için Ekstra Bilgi */}
          {period === 'yearly' && 'average_monthly_revenue' in reportData && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Ortalama Günlük Gelir</p>
                  <p className="text-xl font-bold text-gray-900">
                    {formatCurrency((reportData as YearlyReport).average_daily_revenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Ortalama Aylık Gelir</p>
                  <p className="text-xl font-bold text-gray-900">
                    {formatCurrency((reportData as YearlyReport).average_monthly_revenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Dönem</p>
                  <p className="text-xl font-bold text-gray-900">
                    {formatDate((reportData as YearlyReport).start_date)} - {formatDate((reportData as YearlyReport).end_date)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Sipariş Listesi */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Siparişler</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Sipariş No
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tarih
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Müşteri
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Durum
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tutar
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {reportData.orders.slice(0, 50).map((order: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {order.orderNumber || order.id || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {order.orderDate || order.order_date ? formatDate(order.orderDate || order.order_date) : '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {(
                          (order.customerFirstName || '') + ' ' + (order.customerLastName || '')
                        ).trim() || 'Bilinmeyen'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {order.status || order.orderStatus || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        {formatCurrency(
                          parseFloat(
                            (order.totalPrice || order.totalPriceValue || order.totalAmount || 0).toString().replace(',', '.')
                          ) || 0
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {reportData.orders.length > 50 && (
              <p className="text-sm text-gray-500 mt-4 text-center">
                Toplam {reportData.orders.length} sipariş var. İlk 50 tanesi gösteriliyor. Tüm verileri görmek için CSV/JSON export kullanın.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

