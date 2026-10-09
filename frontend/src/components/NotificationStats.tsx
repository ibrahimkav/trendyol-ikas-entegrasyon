import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { TrendingUp, Bell, AlertCircle, CheckCircle } from 'lucide-react'

interface Stats {
  total: number
  unread: number
  read: number
  type_counts: Record<string, number>
  priority_counts: Record<string, number>
  daily_counts: Array<{ date: string; count: number }>
}

export default function NotificationStats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/notifications/stats')
      setStats(response.data)
    } catch (err) {
      console.error('İstatistikler yüklenemedi:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-8">Yükleniyor...</div>
  }

  if (!stats) {
    return <div className="text-center py-8">İstatistikler yüklenemedi</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Bildirim İstatistikleri</h2>
      
      {/* Özet Kartlar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Toplam Bildirim</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
            <Bell className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Okunmamış</p>
              <p className="text-2xl font-bold text-red-600">{stats.unread}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Okunmuş</p>
              <p className="text-2xl font-bold text-green-600">{stats.read}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Okunma Oranı</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.total > 0 ? Math.round((stats.read / stats.total) * 100) : 0}%
              </p>
            </div>
            <TrendingUp className="w-8 h-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Tip Bazında Dağılım */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">Tip Bazında Dağılım</h3>
        <div className="space-y-2">
          {Object.entries(stats.type_counts).map(([type, count]) => (
            <div key={type} className="flex items-center justify-between">
              <span className="text-gray-700 capitalize">{type}</span>
              <div className="flex items-center space-x-2">
                <div className="w-32 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-trendyol-primary h-2 rounded-full"
                    style={{ width: `${(count / stats.total) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold w-12 text-right">{count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Öncelik Bazında Dağılım */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">Öncelik Bazında Dağılım</h3>
        <div className="space-y-2">
          {Object.entries(stats.priority_counts).map(([priority, count]) => (
            <div key={priority} className="flex items-center justify-between">
              <span className="text-gray-700 capitalize">{priority}</span>
              <div className="flex items-center space-x-2">
                <div className="w-32 bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      priority === 'urgent' ? 'bg-red-500' :
                      priority === 'high' ? 'bg-orange-500' :
                      priority === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                    }`}
                    style={{ width: `${(count / stats.total) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold w-12 text-right">{count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Günlük Bildirim Grafiği */}
      {stats.daily_counts.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold mb-4">Son 7 Gün</h3>
          <div className="flex items-end space-x-2 h-48">
            {stats.daily_counts.map((day, index) => {
              const maxCount = Math.max(...stats.daily_counts.map(d => d.count))
              const height = maxCount > 0 ? (day.count / maxCount) * 100 : 0
              
              return (
                <div key={index} className="flex-1 flex flex-col items-center">
                  <div className="w-full bg-gray-200 rounded-t h-full flex items-end">
                    <div
                      className="w-full bg-trendyol-primary rounded-t"
                      style={{ height: `${height}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-600 mt-2">{day.count}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(day.date).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

