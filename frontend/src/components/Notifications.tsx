import { useState, useEffect, useRef } from 'react'
import apiClient from '../config/api'
import { Bell, Package, DollarSign, Truck, AlertCircle, CheckCircle, X, RefreshCw, Volume2, VolumeX, Settings, Search, Filter, Trash2, History, BarChart3, CheckSquare } from 'lucide-react'
import NotificationStats from './NotificationStats'

interface Notification {
  id: string
  type: string
  title: string
  message: string
  priority: string
  timestamp: string
  read: boolean
  action_url?: string
  metadata?: any
}

// Bildirim ayarları (localStorage'da saklanır)
interface NotificationSettings {
  soundEnabled: boolean
  browserNotificationsEnabled: boolean
  checkInterval: number // saniye cinsinden
  soundType: string // 'beep', 'ding', 'chime', 'notification'
  soundVolume: number // 0-1 arası
}

const defaultSettings: NotificationSettings = {
  soundEnabled: true,
  browserNotificationsEnabled: true,
  checkInterval: 10, // 10 saniyede bir kontrol
  soundType: 'beep',
  soundVolume: 0.5
}

export default function Notifications() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState<NotificationSettings>(defaultSettings)
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [showStats, setShowStats] = useState(false)
  const [selectedNotifications, setSelectedNotifications] = useState<Set<string>>(new Set())
  const [filterType, setFilterType] = useState<string>('all')
  const [filterPriority, setFilterPriority] = useState<string>('all')
  const [filterRead, setFilterRead] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const lastOrderIdsRef = useRef<Set<string>>(new Set())

  // Bildirim ayarlarını yükle
  useEffect(() => {
    const savedSettings = localStorage.getItem('notificationSettings')
    if (savedSettings) {
      try {
        setSettings(JSON.parse(savedSettings))
      } catch {
        setSettings(defaultSettings)
      }
    }
  }, [])

  // Browser notification izni iste
  useEffect(() => {
    if (settings.browserNotificationsEnabled && 'Notification' in window) {
      if (Notification.permission === 'default') {
        Notification.requestPermission()
      }
    }
  }, [settings.browserNotificationsEnabled])

  // Ses dosyasını yükle
  useEffect(() => {
    // Basit bir beep sesi oluştur (Web Audio API ile)
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    oscillator.frequency.value = 800
    oscillator.type = 'sine'
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5)
    
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.5)
    
    // Alternatif: HTML5 Audio kullan
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIG2m98OSfTQ8OUKfk8LZjHAY4kdfyzHksBSR3x/DdkEAKFF606euoVRQKRp/g8r5sIQUrgc7y2Yk2CBtpvfDkn00PDlCn5PC2YxwGOJHX8sx5LAUkd8fw3ZBACg==')
    audioRef.current = audio
  }, [])

  // Yeni siparişleri kontrol et
  const checkNewOrders = async () => {
    try {
      const response = await apiClient.get('/notifications/new-orders')
      const newOrders = response.data.new_orders || []
      
      if (newOrders.length > 0) {
        // Yeni siparişler var - ses çal ve bildirim göster
        newOrders.forEach((order: any) => {
          const orderId = order.id || order.order_number
          
          // Eğer bu sipariş daha önce görülmemişse
          if (!lastOrderIdsRef.current.has(orderId)) {
            lastOrderIdsRef.current.add(orderId)
            
            // Ses çal
            if (settings.soundEnabled) {
              playNotificationSound()
            }
            
            // Browser notification göster
            if (settings.browserNotificationsEnabled && 'Notification' in window && Notification.permission === 'granted') {
              new Notification('🛒 Yeni Sipariş!', {
                body: `${order.customer_name} - ${order.order_number} - ${order.total_amount.toFixed(2)} TL`,
                icon: '/favicon.ico',
                badge: '/favicon.ico',
                tag: `order-${orderId}`,
                requireInteraction: false
              })
            }
          }
        })
      }
    } catch (err) {
      console.error('Yeni sipariş kontrolü hatası:', err)
    }
  }

  const playNotificationSound = () => {
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    // Ses tipine göre frekans ve tip ayarla
    switch (settings.soundType) {
      case 'beep':
        oscillator.frequency.value = 800
        oscillator.type = 'sine'
        break
      case 'ding':
        oscillator.frequency.value = 1000
        oscillator.type = 'sine'
        break
      case 'chime':
        oscillator.frequency.value = 600
        oscillator.type = 'triangle'
        break
      case 'notification':
        oscillator.frequency.value = 700
        oscillator.type = 'square'
        break
      default:
        oscillator.frequency.value = 800
        oscillator.type = 'sine'
    }
    
    gainNode.gain.setValueAtTime(settings.soundVolume * 0.3, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5)
    
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.5)
  }

  useEffect(() => {
    fetchNotifications()
    checkNewOrders()
    
    // Bildirimleri güncelle
    const notificationInterval = setInterval(fetchNotifications, settings.checkInterval * 1000)
    
    // Yeni siparişleri kontrol et (daha sık)
    const newOrderInterval = setInterval(checkNewOrders, settings.checkInterval * 1000)
    
    return () => {
      clearInterval(notificationInterval)
      clearInterval(newOrderInterval)
    }
  }, [settings.checkInterval])

  const fetchNotifications = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/notifications/')
      setNotifications(response.data.notifications || [])
    } catch (err: any) {
      setError('Bildirimler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const markAsRead = async (notificationId: string) => {
    try {
      await apiClient.post(`/notifications/mark-read/${notificationId}`)
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
      )
    } catch (err) {
      console.error('Bildirim okundu olarak işaretlenemedi:', err)
    }
  }

  const markAllAsRead = async () => {
    try {
      await apiClient.post('/notifications/mark-all-read')
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
    } catch (err) {
      console.error('Tüm bildirimler okundu olarak işaretlenemedi:', err)
    }
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'order':
        return <Package className="w-5 h-5" />
      case 'payment':
        return <DollarSign className="w-5 h-5" />
      case 'cargo':
        return <Truck className="w-5 h-5" />
      default:
        return <Bell className="w-5 h-5" />
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'border-red-500 bg-red-50'
      case 'high':
        return 'border-orange-500 bg-orange-50'
      case 'medium':
        return 'border-yellow-500 bg-yellow-50'
      case 'low':
        return 'border-blue-500 bg-blue-50'
      default:
        return 'border-gray-500 bg-gray-50'
    }
  }

  const unreadCount = notifications.filter(n => !n.read).length

  // Filtrelenmiş bildirimler
  const filteredNotifications = notifications.filter(n => {
    if (filterType !== 'all' && n.type !== filterType) return false
    if (filterPriority !== 'all' && n.priority !== filterPriority) return false
    if (filterRead !== 'all') {
      const isRead = filterRead === 'read'
      if (n.read !== isRead) return false
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      if (!n.title.toLowerCase().includes(query) && !n.message.toLowerCase().includes(query)) {
        return false
      }
    }
    return true
  })

  const toggleNotificationSelection = (id: string) => {
    const newSelected = new Set(selectedNotifications)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedNotifications(newSelected)
  }

  const selectAll = () => {
    if (selectedNotifications.size === filteredNotifications.length) {
      setSelectedNotifications(new Set())
    } else {
      setSelectedNotifications(new Set(filteredNotifications.map(n => n.id)))
    }
  }

  const deleteSelected = async () => {
    if (selectedNotifications.size === 0) return
    
    try {
      await apiClient.delete('/notifications/', {
        data: Array.from(selectedNotifications)
      })
      setNotifications(prev => prev.filter(n => !selectedNotifications.has(n.id)))
      setSelectedNotifications(new Set())
    } catch (err) {
      console.error('Bildirimler silinemedi:', err)
    }
  }

  const fetchHistory = async () => {
    try {
      const params: any = {
        limit: 100,
        offset: 0
      }
      if (filterType !== 'all') params.type_filter = filterType
      if (filterPriority !== 'all') params.priority_filter = filterPriority
      if (filterRead !== 'all') params.read_filter = filterRead === 'read'
      if (searchQuery) params.search = searchQuery
      
      const response = await apiClient.get('/notifications/history', { params })
      setNotifications(response.data.notifications || [])
    } catch (err: any) {
      setError('Bildirim geçmişi yüklenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const toggleSound = () => {
    const newSettings = { ...settings, soundEnabled: !settings.soundEnabled }
    setSettings(newSettings)
    localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
  }

  const toggleBrowserNotifications = async () => {
    if ('Notification' in window) {
      if (Notification.permission === 'default') {
        const permission = await Notification.requestPermission()
        if (permission === 'granted') {
          const newSettings = { ...settings, browserNotificationsEnabled: true }
          setSettings(newSettings)
          localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
        }
      } else if (Notification.permission === 'granted') {
        const newSettings = { ...settings, browserNotificationsEnabled: !settings.browserNotificationsEnabled }
        setSettings(newSettings)
        localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Bildirimler</h1>
          <p className="page-subtitle">
            {unreadCount > 0 ? `${unreadCount} okunmamış bildirim` : 'Tüm bildirimler okundu'}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowStats(!showStats)}
            className="p-2 text-gray-600 hover:text-gray-900 transition"
            title="İstatistikler"
          >
            <BarChart3 className="w-5 h-5" />
          </button>
          <button
            onClick={() => {
              setShowHistory(!showHistory)
              if (!showHistory) fetchHistory()
            }}
            className="p-2 text-gray-600 hover:text-gray-900 transition"
            title="Geçmiş"
          >
            <History className="w-5 h-5" />
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-600 hover:text-gray-900 transition"
            title="Bildirim Ayarları"
          >
            <Settings className="w-5 h-5" />
          </button>
          <button
            onClick={fetchNotifications}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Yenile</span>
          </button>
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              className="flex items-center space-x-2 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition"
            >
              <CheckCircle className="w-4 h-4" />
              <span>Tümünü Okundu İşaretle</span>
            </button>
          )}
        </div>
      </div>

      {/* İstatistikler */}
      {showStats && (
        <div className="bg-white p-6 rounded-lg shadow-md">
          <NotificationStats />
        </div>
      )}

      {/* Filtreler ve Arama */}
      <div className="bg-white p-4 rounded-lg shadow-md">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
            />
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-trendyol-primary"
          >
            <option value="all">Tüm Tipler</option>
            <option value="order">Sipariş</option>
            <option value="payment">Ödeme</option>
            <option value="cargo">Kargo</option>
            <option value="stock">Stok</option>
          </select>
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-trendyol-primary"
          >
            <option value="all">Tüm Öncelikler</option>
            <option value="urgent">Acil</option>
            <option value="high">Yüksek</option>
            <option value="medium">Orta</option>
            <option value="low">Düşük</option>
          </select>
          <select
            value={filterRead}
            onChange={(e) => setFilterRead(e.target.value)}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-trendyol-primary"
          >
            <option value="all">Tümü</option>
            <option value="unread">Okunmamış</option>
            <option value="read">Okunmuş</option>
          </select>
        </div>
        
        {/* Toplu İşlemler */}
        {selectedNotifications.size > 0 && (
          <div className="flex items-center justify-between p-3 bg-trendyol-primary/10 rounded-lg">
            <span className="text-sm font-semibold text-gray-700">
              {selectedNotifications.size} bildirim seçildi
            </span>
            <div className="flex items-center space-x-2">
              <button
                onClick={selectAll}
                className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition"
              >
                <CheckSquare className="w-4 h-4 inline mr-1" />
                Tümünü Seç/Kaldır
              </button>
              <button
                onClick={deleteSelected}
                className="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition flex items-center"
              >
                <Trash2 className="w-4 h-4 mr-1" />
                Sil
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Bildirim Ayarları */}
      {showSettings && (
        <div className="bg-white p-4 rounded-lg shadow-md border">
          <h3 className="font-semibold text-gray-900 mb-3">Bildirim Ayarları</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {settings.soundEnabled ? (
                  <Volume2 className="w-5 h-5 text-gray-600" />
                ) : (
                  <VolumeX className="w-5 h-5 text-gray-400" />
                )}
                <span className="text-sm text-gray-700">Sesli Bildirim</span>
              </div>
              <button
                onClick={toggleSound}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.soundEnabled ? 'bg-trendyol-primary' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.soundEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Bell className="w-5 h-5 text-gray-600" />
                <span className="text-sm text-gray-700">Tarayıcı Bildirimleri</span>
              </div>
              <button
                onClick={toggleBrowserNotifications}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.browserNotificationsEnabled ? 'bg-trendyol-primary' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.browserNotificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700">Kontrol Aralığı</span>
              <select
                value={settings.checkInterval}
                onChange={(e) => {
                  const newSettings = { ...settings, checkInterval: parseInt(e.target.value) }
                  setSettings(newSettings)
                  localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
                }}
                className="px-3 py-1 border rounded-lg text-sm"
              >
                <option value="5">5 saniye</option>
                <option value="10">10 saniye</option>
                <option value="30">30 saniye</option>
                <option value="60">1 dakika</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700">Ses Tipi</span>
              <select
                value={settings.soundType}
                onChange={(e) => {
                  const newSettings = { ...settings, soundType: e.target.value }
                  setSettings(newSettings)
                  localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
                }}
                className="px-3 py-1 border rounded-lg text-sm"
              >
                <option value="beep">Beep</option>
                <option value="ding">Ding</option>
                <option value="chime">Chime</option>
                <option value="notification">Notification</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700">Ses Seviyesi</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.soundVolume}
                onChange={(e) => {
                  const newSettings = { ...settings, soundVolume: parseFloat(e.target.value) }
                  setSettings(newSettings)
                  localStorage.setItem('notificationSettings', JSON.stringify(newSettings))
                }}
                className="w-32"
              />
              <span className="text-sm text-gray-600 w-12 text-right">
                {Math.round(settings.soundVolume * 100)}%
              </span>
            </div>
          </div>
        </div>
      )}

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
      ) : notifications.length === 0 ? (
        <div className="bg-white p-12 rounded-lg shadow-md text-center">
          <Bell className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Henüz bildirim yok</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredNotifications.length === 0 ? (
            <div className="bg-white p-12 rounded-lg shadow-md text-center">
              <Filter className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Filtre kriterlerine uygun bildirim bulunamadı</p>
            </div>
          ) : (
            filteredNotifications.map((notification) => (
              <div
                key={notification.id}
                className={`bg-white p-5 rounded-lg shadow-md border-l-4 ${getPriorityColor(notification.priority)} ${!notification.read ? 'ring-2 ring-trendyol-primary' : ''} ${selectedNotifications.has(notification.id) ? 'ring-2 ring-blue-500' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4 flex-1">
                    <input
                      type="checkbox"
                      checked={selectedNotifications.has(notification.id)}
                      onChange={() => toggleNotificationSelection(notification.id)}
                      className="mt-1 w-4 h-4 text-trendyol-primary focus:ring-trendyol-primary border-gray-300 rounded"
                    />
                    <div className={`p-2 rounded-lg ${notification.read ? 'bg-gray-100' : 'bg-trendyol-primary/10'}`}>
                      {getIcon(notification.type)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <h3 className="font-semibold text-gray-900">{notification.title}</h3>
                        {!notification.read && (
                          <span className="px-2 py-0.5 bg-trendyol-primary text-white text-xs rounded-full">
                            Yeni
                          </span>
                        )}
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          notification.priority === 'urgent' ? 'bg-red-100 text-red-800' :
                          notification.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                          notification.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {notification.priority === 'urgent' ? 'Acil' :
                           notification.priority === 'high' ? 'Yüksek' :
                           notification.priority === 'medium' ? 'Orta' : 'Düşük'}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{notification.message}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(notification.timestamp).toLocaleString('tr-TR')}
                      </p>
                      {notification.action_url && (
                        <a
                          href={notification.action_url}
                          className="text-sm text-trendyol-primary hover:text-trendyol-secondary mt-2 inline-block"
                        >
                          Detayları Gör →
                        </a>
                      )}
                    </div>
                  </div>
                  {!notification.read && (
                    <button
                      onClick={() => markAsRead(notification.id)}
                      className="ml-4 p-2 text-gray-400 hover:text-gray-600 transition"
                      title="Okundu işaretle"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

