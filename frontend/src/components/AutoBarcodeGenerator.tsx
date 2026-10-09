import { useState, useEffect, useRef } from 'react'
import apiClient from '../config/api'
import { formatOrderDateTime } from '../utils/formatOrderDateTime'
import { Barcode } from './ui'
import { code128SvgMarkup } from '../lib/code128'
import { Package, Download, RefreshCw, CheckCircle, AlertCircle, Printer, CheckSquare, Square, BarChart3, DollarSign, ShoppingCart, TrendingUp, Search, Settings, FileDown, Eye, Clock, Zap, X, SortAsc, SortDesc, Truck, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'

interface PendingOrder {
  order_id: string
  order_date: string
  status: string
  total_price: number
  item_count: number
  items: Array<{
    product_name: string
    quantity: number
    price: number
  }>
}

interface GeneratedBarcode {
  order_id: string
  order_date: string
  status: string
  barcode_image?: string
  qr_code_image: string
  shipping_label?: string
  barcode_data: string
  order_summary: {
    total_items: number
    unique_products: number
    total_value: number
    discount_code?: string
    discount_website?: string
    discount_percentage?: number
    items: Array<{
      product_id: string
      name: string
      quantity: number
      price: number
    }>
  }
}

// Trendyol Ortak Etiket servisinin döndürdüğü ham hata mesajını/kodunu anlaşılır
// Türkçeye çevirir. Backend ham mesajı olduğu gibi dönüyor (doğru davranış — gerçeği
// gizlemiyor); burada sadece kullanıcıya "ne oldu, ne yapmalıyım" çevirisi ekleniyor.
// Bilinmeyen bir mesaj gelirse ham haliyle gösterilir (uydurmuyoruz).
interface LabelErrorInfo {
  title: string
  detail: string
  action: string
}

const LABEL_ERROR_TRANSLATIONS: Record<string, LabelErrorInfo> = {
  PACKAGE_STATUS_NOT_VALID: {
    title: 'Bu aşamada etiket alınamıyor',
    detail: 'Paket zaten kargoya verilmiş veya teslim edilmiş görünüyor — bu aşamadaki paketler için Trendyol etiket üretmiyor.',
    action: 'Yapılacak bir şey yok; bu siparişin etiketi muhtemelen zaten kullanılmıştı.'
  },
  BARCODE_NOT_FOUND_PACKAGE_CREATED: {
    title: 'Trendyol barkodu henüz hazır değil',
    detail: 'Paket oluşturuldu ama Trendyol bu paket için kendi kargo barkodunu henüz üretmedi.',
    action: 'Birkaç dakika bekleyip tekrar deneyin.'
  },
  COMMON_LABEL_NOT_ALLOWED: {
    title: 'Ortak Etiket yetkiniz yok',
    detail: 'Bu mağaza hesabında Trendyol Ortak Etiket servisini kullanma izni bulunmuyor.',
    action: 'Trendyol kategori sorumlunuzdan Ortak Etiket yetkisi isteyin.'
  }
}

function translateLabelError(raw: string): LabelErrorInfo & { rawMessage: string; isKnown: boolean } {
  const haystack = (raw || '').toUpperCase()
  const matchedCode = Object.keys(LABEL_ERROR_TRANSLATIONS).find((code) => haystack.includes(code))
  if (matchedCode) {
    return { ...LABEL_ERROR_TRANSLATIONS[matchedCode], rawMessage: raw, isKnown: true }
  }
  return {
    title: 'Etiket alınamadı',
    detail: raw || 'Bilinmeyen bir hata oluştu.',
    action: 'Sorun devam ederse bu mesajı destek ile paylaşın.',
    rawMessage: raw,
    isKnown: false
  }
}

export default function AutoBarcodeGenerator() {
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([])
  const [generatedBarcodes, setGeneratedBarcodes] = useState<GeneratedBarcode[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [bulkPrinting, setBulkPrinting] = useState(false)
  const [bulkLabels, setBulkLabels] = useState<Array<{order_id: string, order_date: string, label: string}>>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedOrders, setSelectedOrders] = useState<string[]>([])
  const [printSettings, setPrintSettings] = useState({
    paper_size: '4x6',
    quality: 'high',
    copies: 1,
    orientation: 'portrait'
  })
  const [stats, setStats] = useState({
    total_pending_orders: 0,
    total_value: 0,
    average_order_value: 0,
    today_barcodes: 0,
    total_items: 0
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState<'date' | 'value' | 'items'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(30) // saniye
  const [discountCode, setDiscountCode] = useState('TRENDYOL15')
  const [showOrderDetail, setShowOrderDetail] = useState<string | null>(null)
  const [orderDetail, setOrderDetail] = useState<any>(null)
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'compact'>('list')
  const [showPrintSettings, setShowPrintSettings] = useState(false)
  const [barcodeFormat, setBarcodeFormat] = useState<'qr' | 'code128' | 'both'>('both')
  const [notifications, setNotifications] = useState<Array<{id: string, type: 'success' | 'error' | 'info', message: string, timestamp: Date}>>([])
  const previousPendingIdsRef = useRef<Set<string>>(new Set())
  const [newPendingOrderIds, setNewPendingOrderIds] = useState<Set<string>>(new Set())
  const [labelsPreviewExpanded, setLabelsPreviewExpanded] = useState(true)
  const [lastLabelBatchOrderIds, setLastLabelBatchOrderIds] = useState<Set<string>>(new Set())
  const [bulkLabelErrors, setBulkLabelErrors] = useState<Array<{ order_id: string, error: string }>>([])
  const [labelErrorsPreviewExpanded, setLabelErrorsPreviewExpanded] = useState(true)

  useEffect(() => {
    fetchPendingOrders()
    fetchStats()
    fetchCreatedBarcodes() // Sayfa yüklendiğinde oluşturulan barkodları çek
  }, [])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchPendingOrders()
        fetchStats()
      }, autoRefreshInterval * 1000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh, autoRefreshInterval])

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/barcode/stats')
      setStats(response.data)
    } catch (err: any) {
      console.error('İstatistikler yüklenemedi:', err)
    }
  }

  const fetchPendingOrders = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get('/barcode/pending-orders')
      const orders: PendingOrder[] = response.data.orders || []
      setPendingOrders(orders)

      const ids = new Set(orders.map((o) => o.order_id))
      const prev = previousPendingIdsRef.current
      if (prev.size > 0) {
        const arrived = orders.filter((o) => !prev.has(o.order_id)).map((o) => o.order_id)
        if (arrived.length > 0) {
          setNewPendingOrderIds((cur) => {
            const next = new Set(cur)
            arrived.forEach((id) => next.add(id))
            return next
          })
        }
      }
      previousPendingIdsRef.current = ids
    } catch (err: any) {
      setError('Bekleyen siparişler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchCreatedBarcodes = async (merge: boolean = false) => {
    try {
      // Database'den "created" status'ündeki barkodları çek
      const response = await apiClient.get('/barcode/history?status=created&limit=100')
      const historyBarcodes = response.data.barcodes || []
      
      console.log('[Barcode] Yüklenen barkod sayısı:', historyBarcodes.length)
      
      if (historyBarcodes.length === 0) {
        console.log('[Barcode] Database\'de "created" status\'ünde barkod bulunamadı')
        // Eğer merge modundaysak mevcut state'i koru
        if (merge) {
          return
        }
        return
      }
      
      // Backend formatını frontend formatına dönüştür
      const formattedBarcodes: GeneratedBarcode[] = historyBarcodes.map((b: any) => {
        // barcode_data JSON string ise parse et
        const orderSummary = {
          total_items: b.total_items || 0,
          unique_products: 0,
          total_value: b.total_value || 0,
          discount_code: b.discount_code || 'TRENDYOL15',
          discount_website: 'penaltidenim.com',
          discount_percentage: 15,
          items: []
        }
        
        try {
          if (b.barcode_data) {
            const barcodeData = typeof b.barcode_data === 'string' ? JSON.parse(b.barcode_data) : b.barcode_data
            if (barcodeData.items) {
              orderSummary.items = barcodeData.items.map((item: any) => ({
                product_id: item.product_id || '',
                name: item.name || item.product_name || 'Ürün',
                quantity: item.quantity || 1,
                price: item.price || 0
              }))
              orderSummary.unique_products = barcodeData.items.length
            }
          }
        } catch (e) {
          console.error('Barcode data parse hatası:', e)
        }
        
        return {
          order_id: b.order_id,
          order_date: b.created_at || b.order_date || '',
          status: b.status || 'created',
          qr_code_image: b.qr_code_image || '', // Backend'den gelen görsel
          barcode_image: b.barcode_image || '',
          shipping_label: '', // Shipping label backend'de saklanmıyor, gerektiğinde yeniden oluşturulabilir
          barcode_data: typeof b.barcode_data === 'string' ? b.barcode_data : JSON.stringify(b.barcode_data),
          order_summary: orderSummary
        }
      })
      
      console.log('[Barcode] Formatlanmış barkod sayısı:', formattedBarcodes.length)
      
      // Eğer merge modundaysak, mevcut state ile birleştir
      if (merge) {
        setGeneratedBarcodes(prevBarcodes => {
          // Backend'den gelen barkodları mevcut olanlarla birleştir
          const mergedBarcodes = formattedBarcodes.map(newB => {
            const existing = prevBarcodes.find(prevB => prevB.order_id === newB.order_id)
            // Eğer mevcut barkod varsa, görselleri backend'den gelenlerle güncelle
            if (existing) {
              return {
                ...existing,
                barcode_image: newB.barcode_image || existing.barcode_image,
                qr_code_image: newB.qr_code_image || existing.qr_code_image
              }
            }
            return newB
          })
          // Mevcut listede olmayan yeni barkodları ekle
          const newBarcodes = prevBarcodes.filter(b => {
            const backendOrderIds = new Set(formattedBarcodes.map(fb => fb.order_id))
            return !backendOrderIds.has(b.order_id)
          })
          // Yeni olanlar önce, sonra güncellenmiş olanlar
          return [...newBarcodes, ...mergedBarcodes]
        })
      } else {
        setGeneratedBarcodes(formattedBarcodes)
      }
      // Sessizce yükle, bildirim gösterme (sayfa yüklenirken kullanıcıyı rahatsız etme)
    } catch (err: any) {
      // Database yoksa veya hata varsa sessizce devam et (503 hatası normal olabilir)
      if (err.response?.status === 503) {
        console.log('[Barcode] Database mevcut değil (ghost mode)')
      } else {
        console.error('Barkod geçmişi yüklenemedi:', err.response?.data?.detail || err.message)
        addNotification('error', 'Barkod geçmişi yüklenemedi: ' + (err.response?.data?.detail || err.message))
      }
    }
  }

  const addNotification = (type: 'success' | 'error' | 'info', message: string) => {
    const notification = {
      id: Date.now().toString(),
      type,
      message,
      timestamp: new Date()
    }
    setNotifications(prev => [...prev, notification])
    // 5 saniye sonra otomatik kaldır
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== notification.id))
    }, 5000)
  }

  const generateAllBarcodes = async () => {
    setGenerating(true)
    setError(null)
    try {
      const response = await apiClient.get('/barcode/auto-generate')
      const newBarcodes = response.data.barcodes || []
      
      if (newBarcodes.length > 0) {
        // Yeni oluşturulan barkodları mevcut listeye ekle (duplicate'leri önle)
        setGeneratedBarcodes(prevBarcodes => {
          const existingOrderIds = new Set(prevBarcodes.map(b => b.order_id))
          const uniqueNewBarcodes = newBarcodes.filter((b: GeneratedBarcode) => !existingOrderIds.has(b.order_id))
          return [...uniqueNewBarcodes, ...prevBarcodes] // Yeni olanlar önce
        })
        addNotification('success', `${newBarcodes.length} barkod başarıyla oluşturuldu`)
      } else {
        addNotification('info', 'Oluşturulacak yeni barkod bulunamadı')
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message
      setError('Barkod oluşturma hatası: ' + errorMsg)
      addNotification('error', 'Barkod oluşturma hatası: ' + errorMsg)
    } finally {
      setGenerating(false)
    }
  }

  const batchGenerateSelected = async () => {
    if (selectedOrders.length === 0) {
      addNotification('info', 'Lütfen en az bir sipariş seçin')
      return
    }

    setGenerating(true)
    setError(null)
    try {
      const response = await apiClient.post('/barcode/batch/generate', {
        order_ids: selectedOrders,
        discount_code: discountCode || 'TRENDYOL15'
      })
      
      if (response.data.barcodes && response.data.barcodes.length > 0) {
        // Yeni oluşturulan barkodları mevcut listeye ekle (duplicate'leri önle)
        setGeneratedBarcodes(prevBarcodes => {
          const existingOrderIds = new Set(prevBarcodes.map(b => b.order_id))
          const newBarcodes = response.data.barcodes.filter((b: GeneratedBarcode) => !existingOrderIds.has(b.order_id))
          return [...newBarcodes, ...prevBarcodes] // Yeni olanlar önce
        })
        setSelectedOrders([])
        addNotification('success', `${response.data.success} barkod başarıyla oluşturuldu`)
        // Barkodlar oluşturulduktan sonra database'den tekrar yükle (görselleri almak için)
        // Ama mevcut state'i koruyarak merge et
        setTimeout(() => {
          fetchCreatedBarcodes(true) // merge=true parametresi ile
        }, 1000)
      }
      
      if (response.data.errors && response.data.errors.length > 0) {
        addNotification('error', `${response.data.failed} sipariş için hata oluştu`)
      }
    } catch (err: any) {
      setError('Toplu barkod oluşturma hatası: ' + (err.response?.data?.detail || err.message))
    } finally {
      setGenerating(false)
    }
  }

  const toggleOrderSelect = (orderId: string) => {
    setSelectedOrders(prev => 
      prev.includes(orderId)
        ? prev.filter(id => id !== orderId)
        : [...prev, orderId]
    )
  }

  const downloadImage = (imageData: string, filename: string) => {
    const link = document.createElement('a')
    link.href = imageData
    link.download = filename
    link.click()
  }

  const bulkPrintLabels = async () => {
    setBulkPrinting(true)
    setError(null)
    setBulkLabels([])
    setLastLabelBatchOrderIds(new Set())
    try {
      const response = await apiClient.get('/barcode/bulk-print')
      const labels = response.data.labels || []
      setBulkLabels(labels)
      setLastLabelBatchOrderIds(new Set(labels.map((l: { order_id: string }) => l.order_id)))
      setLabelsPreviewExpanded(true)

      // Her etiketi ayrı ayrı yazdır
      if (response.data.labels && response.data.labels.length > 0) {
        // Kullanıcıya onay iste
        const confirmed = window.confirm(
          `${response.data.labels.length} etiket yazdırılacak. Her etiket ayrı bir sayfa olarak çıkacak. Devam etmek istiyor musunuz?`
        )
        
        if (confirmed) {
          // Her etiketi sırayla yazdır
          for (let i = 0; i < response.data.labels.length; i++) {
            const label = response.data.labels[i]
            await printSingleLabel(label.label, label.order_id)
            // Her yazdırma arasında kısa bir bekleme (yazıcının hazır olması için)
            if (i < response.data.labels.length - 1) {
              await new Promise(resolve => setTimeout(resolve, 500))
            }
          }
        }
      }
    } catch (err: any) {
      setError('Toplu yazdırma hatası: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBulkPrinting(false)
    }
  }

  const bulkPrintTrendyolLabels = async () => {
    setBulkPrinting(true)
    setError(null)
    setBulkLabels([])
    setBulkLabelErrors([])
    setLastLabelBatchOrderIds(new Set())
    try {
      const response = await apiClient.get('/barcode/bulk-print-trendyol')
      const labels = response.data.labels || []
      setBulkLabels(labels)
      setLastLabelBatchOrderIds(new Set(labels.map((l: { order_id: string }) => l.order_id)))
      setLabelsPreviewExpanded(true)

      const labelErrors = response.data.errors || []
      setBulkLabelErrors(labelErrors)
      if (labelErrors.length > 0) {
        setLabelErrorsPreviewExpanded(true)
        addNotification('error', `${response.data.error_count} sipariş için kargo etiketi alınamadı — nedenleri aşağıda listelendi`)
      }

      // Her etiketi ayrı ayrı yazdır veya indir
      if (response.data.labels && response.data.labels.length > 0) {
        addNotification('success', `${response.data.labels.length} Trendyol kargo etiketi hazırlandı`)
        
        // Kullanıcıya seçenek sun
        const action = window.confirm(
          `${response.data.labels.length} Trendyol kargo etiketi hazırlandı.\n\n"Tamam" = Yazdır\n"İptal" = İndir`
        )
        
        if (action) {
          // Yazdır
          for (let i = 0; i < response.data.labels.length; i++) {
            const label = response.data.labels[i]
            await printSingleLabel(label.label, label.order_id)
            if (i < response.data.labels.length - 1) {
              await new Promise(resolve => setTimeout(resolve, 500))
            }
          }
        } else {
          // İndir
          for (let i = 0; i < response.data.labels.length; i++) {
            const label = response.data.labels[i]
            const filename = `trendyol-label-${label.order_id}.${label.content_type === 'application/pdf' ? 'pdf' : 'png'}`
            downloadImage(label.label, filename)
            await new Promise(resolve => setTimeout(resolve, 200))
          }
        }
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message
      setError('Trendyol kargo etiketi çıkarma hatası: ' + errorMsg)
      addNotification('error', 'Trendyol kargo etiketi çıkarma hatası: ' + errorMsg)
    } finally {
      setBulkPrinting(false)
    }
  }

  const printSingleLabel = (imageData: string, orderId: string): Promise<void> => {
    return new Promise((resolve) => {
      const printWindow = window.open('', '_blank')
      if (!printWindow) {
        addNotification(
          'error',
          'Popup engelleyici nedeniyle yazdırma penceresi açılamadı. Popup engelleyiciyi kapatıp tekrar deneyin.'
        )
        resolve()
        return
      }

      printWindow.document.write(`
        <!DOCTYPE html>
        <html>
          <head>
            <title>Etiket Yazdır - ${orderId}</title>
            <style>
              @media print {
                body {
                  margin: 0;
                  padding: 0;
                }
                img {
                  width: 100%;
                  height: auto;
                  page-break-after: always;
                }
              }
              @page {
                size: 4in 6in;
                margin: 0;
              }
              body {
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
              }
              img {
                max-width: 100%;
                height: auto;
              }
            </style>
          </head>
          <body>
            ${imageData
              ? `<img src="${imageData}" alt="Kargo Etiketi - ${orderId}" />`
              : code128SvgMarkup(orderId, { height: 90 })}
            <script>
              window.onload = function() {
                setTimeout(function() {
                  window.print();
                  window.onafterprint = function() {
                    window.close();
                  };
                }, 250);
              };
            </script>
          </body>
        </html>
      `)
      
      printWindow.document.close()
      
      // Yazdırma işlemi tamamlandığında resolve et
      printWindow.addEventListener('afterprint', () => {
        printWindow.close()
        resolve()
      })
      
      // Eğer afterprint eventi çalışmazsa, timeout ile resolve et
      setTimeout(() => {
        if (!printWindow.closed) {
          printWindow.close()
        }
        resolve()
      }, 3000)
    })
  }

  // Filtrelenmiş ve sıralanmış siparişler
  const filteredAndSortedOrders = pendingOrders
    .filter(order => {
      const matchesSearch = !searchQuery || 
        order.order_id.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesStatus = !statusFilter || order.status === statusFilter
      return matchesSearch && matchesStatus
    })
    .sort((a, b) => {
      let comparison = 0
      if (sortBy === 'date') {
        comparison = new Date(a.order_date).getTime() - new Date(b.order_date).getTime()
      } else if (sortBy === 'value') {
        comparison = a.total_price - b.total_price
      } else if (sortBy === 'items') {
        comparison = a.item_count - b.item_count
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

  const handleBulkDownload = async () => {
    if (generatedBarcodes.length === 0) {
      addNotification('info', 'İndirilecek barkod bulunamadı')
      return
    }

    try {
      // Her barkodu ayrı ayrı indir
      for (const barcode of generatedBarcodes) {
        if (barcode.qr_code_image) {
          const link = document.createElement('a')
          link.href = barcode.qr_code_image
          link.download = `qr-${barcode.order_id}.png`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          // Her indirme arasında kısa bir bekleme
          await new Promise(resolve => setTimeout(resolve, 100))
        }
        if (barcode.shipping_label) {
          const link = document.createElement('a')
          link.href = barcode.shipping_label
          link.download = `label-${barcode.order_id}.png`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          await new Promise(resolve => setTimeout(resolve, 100))
        }
      }
    } catch (err: any) {
      addNotification('error', 'İndirme hatası: ' + err.message)
    }
  }

  const fetchOrderDetail = async (orderId: string) => {
    try {
      // Trendyol API'den sipariş detayını çek
      const response = await apiClient.get(`/orders/${orderId}`)
      setOrderDetail(response.data)
      setShowOrderDetail(orderId)
    } catch (err: any) {
      addNotification('error', 'Sipariş detayı yüklenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  return (
    <div className="space-y-6">
      {/* Bildirimler */}
      <div className="fixed right-4 top-[calc(5rem+env(safe-area-inset-top,0px))] z-50 max-w-md space-y-2 max-[380px]:right-2 max-[380px]:max-w-[calc(100vw-1rem)]">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            className={`p-4 rounded-lg shadow-lg flex items-start space-x-3 animate-slide-in ${
              notification.type === 'success' ? 'bg-green-50 border border-green-200' :
              notification.type === 'error' ? 'bg-red-50 border border-red-200' :
              'bg-blue-50 border border-blue-200'
            }`}
          >
            {notification.type === 'success' ? (
              <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
            ) : notification.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
            )}
            <div className="flex-1">
              <p className={`text-sm font-medium ${
                notification.type === 'success' ? 'text-green-900' :
                notification.type === 'error' ? 'text-red-900' :
                'text-blue-900'
              }`}>
                {notification.message}
              </p>
            </div>
            <button
              onClick={() => setNotifications(prev => prev.filter(n => n.id !== notification.id))}
              className="text-text-muted hover:text-text-secondary"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="page-header">
        <h1 className="page-title">Otomatik barkod oluşturucu</h1>
        <p className="page-subtitle">
          Kargoya gönderilmesi gereken siparişler için otomatik barkod oluşturun
        </p>
      </div>

      {/* İstatistik Kartları */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Bekleyen sipariş</p>
              <p className="text-2xl font-semibold tabular-nums text-text-primary">{stats.total_pending_orders}</p>
            </div>
            <Package className="h-8 w-8 text-sky-500" />
          </div>
        </div>
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Toplam tutar</p>
              <p className="text-2xl font-semibold tabular-nums text-text-primary">{stats.total_value.toFixed(2)} ₺</p>
            </div>
            <DollarSign className="h-8 w-8 text-emerald-500" />
          </div>
        </div>
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Ortalama sipariş</p>
              <p className="text-2xl font-semibold tabular-nums text-text-primary">{stats.average_order_value.toFixed(2)} ₺</p>
            </div>
            <TrendingUp className="h-8 w-8 text-violet-500" />
          </div>
        </div>
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Bugün oluşturulan</p>
              <p className="text-2xl font-semibold tabular-nums text-text-primary">{stats.today_barcodes}</p>
            </div>
            <BarChart3 className="h-8 w-8 text-brand" />
          </div>
        </div>
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">Toplam ürün</p>
              <p className="text-2xl font-semibold tabular-nums text-text-primary">{stats.total_items}</p>
            </div>
            <ShoppingCart className="h-8 w-8 text-rose-500" />
          </div>
        </div>
      </div>

      {/* Hızlı Erişim Butonları */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button
          onClick={() => {
            setSearchQuery('')
            setStatusFilter('')
            setSortBy('date')
            setSortOrder('desc')
            fetchPendingOrders()
          }}
          className="p-3 bg-app-surface rounded-lg shadow-card hover:shadow-lg transition text-left border-l-4 border-blue-500"
        >
          <div className="flex items-center space-x-2">
            <Zap className="w-5 h-5 text-blue-500" />
            <div>
              <p className="text-sm font-semibold text-text-primary">Tüm Siparişler</p>
              <p className="text-xs text-text-secondary">{pendingOrders.length} sipariş</p>
            </div>
          </div>
        </button>
        <button
          onClick={() => {
            setSearchQuery('')
            setStatusFilter('')
            setSortBy('date')
            setSortOrder('desc')
            fetchPendingOrders()
          }}
          className="p-3 bg-app-surface rounded-lg shadow-card hover:shadow-lg transition text-left border-l-4 border-green-500"
        >
          <div className="flex items-center space-x-2">
            <Clock className="w-5 h-5 text-green-500" />
            <div>
              <p className="text-sm font-semibold text-text-primary">Bugünkü</p>
              <p className="text-xs text-text-secondary">Siparişler</p>
            </div>
          </div>
        </button>
        <button
          onClick={() => {
            setSortBy('value')
            setSortOrder('desc')
          }}
          className="p-3 bg-app-surface rounded-lg shadow-card hover:shadow-lg transition text-left border-l-4 border-purple-500"
        >
          <div className="flex items-center space-x-2">
            <DollarSign className="w-5 h-5 text-purple-500" />
            <div>
              <p className="text-sm font-semibold text-text-primary">Yüksek Tutar</p>
              <p className="text-xs text-text-secondary">Sırala</p>
            </div>
          </div>
        </button>
        <button
          type="button"
          onClick={() => {
            document.getElementById('auto-barcode-generated')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
          className="p-3 bg-app-surface rounded-lg shadow-card hover:shadow-lg transition text-left border-l-4 border-orange-500"
        >
          <div className="flex items-center space-x-2">
            <Package className="w-5 h-5 text-orange-500" />
            <div>
              <p className="text-sm font-semibold text-text-primary">Son Barkodlar</p>
              <p className="text-xs text-text-secondary">{generatedBarcodes.length} oluşturuldu</p>
            </div>
          </div>
        </button>
      </div>

      {/* Filtreleme ve Arama */}
      <div className="bg-app-surface p-4 rounded-lg shadow-card">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Ara</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Sipariş ID ara..."
                className="w-full pl-10 pr-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Durum</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
            >
              <option value="">Tümü</option>
              <option value="Created">Created (Oluşturulan)</option>
              <option value="Picking">Picking (Toplanıyor)</option>
              <option value="Invoiced">Invoiced (Faturalandı)</option>
              <option value="printed">Printed (Yazdırıldı)</option>
              <option value="shipped">Shipped (Gönderildi)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Sırala</label>
            <div className="flex space-x-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="flex-1 px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
              >
                <option value="date">Tarih</option>
                <option value="value">Tutar</option>
                <option value="items">Ürün Sayısı</option>
              </select>
              <button
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="px-3 py-2 border border-app-border rounded-lg hover:bg-app-surface-muted"
              >
                {sortOrder === 'asc' ? <SortAsc className="w-4 h-4" /> : <SortDesc className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">İndirim Kodu</label>
            <input
              type="text"
              value={discountCode}
              onChange={(e) => setDiscountCode(e.target.value)}
              className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
            />
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => {
                fetchPendingOrders()
                fetchStats()
              }}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-app-surface-muted text-text-secondary rounded-lg hover:bg-app-surface-muted transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>Yenile</span>
            </button>
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-app-border"
              />
              <span className="text-sm text-text-secondary">Otomatik Yenile</span>
            </label>
            {autoRefresh && (
              <select
                value={autoRefreshInterval}
                onChange={(e) => setAutoRefreshInterval(parseInt(e.target.value))}
                className="px-2 py-1 text-sm border border-app-border rounded"
              >
                <option value="30">30 saniye</option>
                <option value="60">1 dakika</option>
                <option value="300">5 dakika</option>
              </select>
            )}
            <span className="text-sm text-text-secondary">
              {filteredAndSortedOrders.length} sipariş • {generatedBarcodes.filter(b => {
                if (statusFilter === 'Created') return b.status === 'created'
                if (statusFilter && statusFilter !== '') return b.status === statusFilter.toLowerCase()
                return true
              }).length} barkod gösteriliyor
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 text-sm rounded ${viewMode === 'list' ? 'bg-brand text-white' : 'bg-app-surface-muted text-text-secondary'}`}
            >
              Liste
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`px-3 py-1 text-sm rounded ${viewMode === 'grid' ? 'bg-brand text-white' : 'bg-app-surface-muted text-text-secondary'}`}
            >
              Grid
            </button>
            <button
              onClick={() => setViewMode('compact')}
              className={`px-3 py-1 text-sm rounded ${viewMode === 'compact' ? 'bg-brand text-white' : 'bg-app-surface-muted text-text-secondary'}`}
            >
              Kompakt
            </button>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="bg-app-surface p-4 rounded-lg shadow-card">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={generateAllBarcodes}
            disabled={generating || pendingOrders.length === 0}
            className="flex-1 min-w-[200px] flex items-center justify-center space-x-2 px-6 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition disabled:opacity-50"
          >
            <Package className={`w-5 h-5 ${generating ? 'animate-pulse' : ''}`} />
            <span className="whitespace-nowrap">{generating ? 'Oluşturuluyor...' : 'Tümü İçin Barkod Oluştur'}</span>
          </button>
          <button
            onClick={batchGenerateSelected}
            disabled={generating || selectedOrders.length === 0}
            className="flex-1 min-w-[180px] flex items-center justify-center space-x-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            <CheckSquare className={`w-5 h-5 ${generating ? 'animate-pulse' : ''}`} />
            <span className="whitespace-nowrap">{generating ? 'Oluşturuluyor...' : `Seçilenler İçin (${selectedOrders.length})`}</span>
          </button>
          <button
            onClick={bulkPrintLabels}
            disabled={bulkPrinting || pendingOrders.length === 0}
            className="flex-1 min-w-[150px] flex items-center justify-center space-x-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
          >
            <Printer className={`w-5 h-5 ${bulkPrinting ? 'animate-pulse' : ''}`} />
            <span className="whitespace-nowrap">{bulkPrinting ? 'Hazırlanıyor...' : 'Toplu Yazdır'}</span>
          </button>
          <button
            onClick={bulkPrintTrendyolLabels}
            disabled={bulkPrinting || pendingOrders.length === 0}
            className="flex-1 min-w-[200px] flex items-center justify-center space-x-2 px-6 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition disabled:opacity-50"
            title="Trendyol'un kendi kargo etiketlerini toplu çıkarır"
          >
            <Truck className={`w-5 h-5 ${bulkPrinting ? 'animate-pulse' : ''}`} />
            <span className="whitespace-nowrap">{bulkPrinting ? 'Hazırlanıyor...' : 'Trendyol Kargo Etiketleri'}</span>
          </button>
          {generatedBarcodes.length > 0 && (
            <button
              onClick={handleBulkDownload}
              className="flex items-center justify-center space-x-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition whitespace-nowrap"
            >
              <FileDown className="w-5 h-5" />
              <span>Toplu İndir</span>
            </button>
          )}
          <button
            onClick={() => setShowPrintSettings(true)}
            className="flex items-center justify-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition whitespace-nowrap"
          >
            <Settings className="w-5 h-5" />
            <span>Yazdırma Ayarları</span>
          </button>
          <button
            onClick={() => {
              const format = window.confirm('Excel formatında indirmek ister misiniz? (Hayır = CSV)') ? 'excel' : 'csv'
              window.open(`/api/barcode/export/${format}`, '_blank')
              addNotification('success', `${format.toUpperCase()} formatında export başlatıldı`)
            }}
            className="flex items-center justify-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition whitespace-nowrap"
          >
            <FileDown className="w-5 h-5" />
            <span>Export</span>
          </button>
          <label className="flex items-center justify-center space-x-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition cursor-pointer whitespace-nowrap">
            <FileDown className="w-5 h-5" />
            <span>Import</span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (!file) return
                
                try {
                  const formData = new FormData()
                  formData.append('file', file)
                  
                  const response = await apiClient.post('/barcode/import', formData, {
                    headers: {
                      'Content-Type': 'multipart/form-data'
                    }
                  })
                  
                  addNotification('success', `${response.data.imported_count} kayıt başarıyla import edildi`)
                  fetchPendingOrders()
                  fetchStats()
                } catch (err: any) {
                  addNotification('error', 'Import hatası: ' + (err.response?.data?.detail || err.message))
                }
                
                // Input'u temizle
                e.target.value = ''
              }}
              className="hidden"
            />
          </label>
        </div>
        <div className="mt-3 flex items-center space-x-2">
          <button
            onClick={() => {
              if (selectedOrders.length === filteredAndSortedOrders.length) {
                setSelectedOrders([])
              } else {
                setSelectedOrders(filteredAndSortedOrders.map(o => o.order_id))
              }
            }}
            className="text-sm px-3 py-1 text-text-secondary hover:bg-app-surface-muted rounded"
          >
            {selectedOrders.length === filteredAndSortedOrders.length ? 'Tümünü Kaldır' : 'Tümünü Seç'}
          </button>
          {selectedOrders.length > 0 && (
            <>
              <span className="text-sm text-text-secondary">{selectedOrders.length} sipariş seçili</span>
              <button
                onClick={() => setSelectedOrders([])}
                className="text-sm px-3 py-1 text-red-600 hover:bg-red-50 rounded"
              >
                Seçimi Temizle
              </button>
            </>
          )}
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

      {/* Sıradaki siparişler — barkod geçmişi olsa bile her zaman görünür */}
      {filteredAndSortedOrders.length > 0 && (
        <div id="auto-barcode-pending" className="rounded-xl border-2 border-sky-200 bg-sky-50/40 shadow-card scroll-mt-24">
          <div className="border-b border-sky-200 bg-app-surface/80 px-4 py-3 rounded-t-xl">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                  <Package className="h-5 w-5 text-sky-600" />
                  Sıradaki siparişler
                </h2>
                <p className="text-sm text-text-secondary mt-0.5">
                  Kuyruk: işlem veya etiket için bekleyen siparişler (aşağıdaki “Son kargo etiketi önizlemesi”nden ayrıdır).
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {newPendingOrderIds.size > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900">
                    <Sparkles className="h-3.5 w-3.5" />
                    {newPendingOrderIds.size} yeni
                  </span>
                )}
                {newPendingOrderIds.size > 0 && (
                  <button
                    type="button"
                    onClick={() => setNewPendingOrderIds(new Set())}
                    className="text-xs font-medium text-sky-800 underline hover:text-sky-950"
                  >
                    Yeni işaretini kaldır
                  </button>
                )}
              </div>
            </div>
            {bulkLabels.length > 0 && newPendingOrderIds.size > 0 && (
              <p className="mt-2 text-xs text-text-secondary rounded-md bg-app-surface/90 border border-slate-200 px-3 py-2">
                <strong className="text-slate-800">İpucu:</strong> Turuncu “Yeni” rozetli satırlar, son etiket çıkarma işleminden sonra gelen (veya yenilemede görünen) siparişlerdir; yeşil önizleme kutusu yalnızca az önce çıkardığınız etiketler içindir.
              </p>
            )}
          </div>
          <div className="p-4">
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : viewMode === 'compact' ? 'space-y-1' : 'space-y-2'}>
              {filteredAndSortedOrders.map((order, index) => {
                const isNew = newPendingOrderIds.has(order.order_id)
                const hadLabelInLastBatch = lastLabelBatchOrderIds.has(order.order_id)
                return (
                  <div
                    key={index}
                    className={`${viewMode === 'compact' ? 'p-2' : 'p-3'} rounded-lg flex items-center space-x-3 border ${
                      isNew
                        ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200'
                        : selectedOrders.includes(order.order_id)
                          ? 'bg-blue-50 border-blue-500 border-2'
                          : 'bg-app-surface border-slate-200'
                    }`}
                  >
                    <button type="button" onClick={() => toggleOrderSelect(order.order_id)} className="flex-shrink-0">
                      {selectedOrders.includes(order.order_id) ? (
                        <CheckSquare className="w-5 h-5 text-blue-600" />
                      ) : (
                        <Square className="w-5 h-5 text-text-muted" />
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={`${viewMode === 'compact' ? 'text-sm' : ''} font-medium text-text-primary`}>
                          Sipariş: {order.order_id}
                        </p>
                        {isNew && (
                          <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-amber-200 text-amber-950">
                            <Sparkles className="h-3 w-3" />
                            Yeni
                          </span>
                        )}
                        {hadLabelInLastBatch && bulkLabels.length > 0 && (
                          <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded" title="Son etiket önizlemesinde bu sipariş vardı">
                            Son etiket grubunda
                          </span>
                        )}
                      </div>
                      <p className={`${viewMode === 'compact' ? 'text-xs' : 'text-sm'} text-text-secondary`}>
                        {order.item_count} ürün • {order.total_price.toFixed(2)} TL
                        {viewMode === 'compact' && (
                          <span className="text-text-muted"> • {formatOrderDateTime(order.order_date)}</span>
                        )}
                      </p>
                      {viewMode !== 'compact' && (
                        <p className="text-xs text-text-muted mt-1">
                          Sipariş: {formatOrderDateTime(order.order_date)}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 flex-shrink-0">
                      <button
                        type="button"
                        onClick={() => fetchOrderDetail(order.order_id)}
                        className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                        title="Detayları Gör"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 rounded">{order.status}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Alınamayan Trendyol etiketleri — ham hata mesajı anlaşılır Türkçeye çevrilip nedene/yapılacağa göre gruplanır */}
      {bulkLabelErrors.length > 0 && (
        <div className="rounded-xl border-2 border-amber-600/40 bg-amber-50/30 shadow-card scroll-mt-24">
          <div className="flex flex-col gap-3 border-b border-amber-200 bg-app-surface/90 px-4 py-3 sm:flex-row sm:items-center sm:justify-between rounded-t-xl">
            <button
              type="button"
              onClick={() => setLabelErrorsPreviewExpanded((e) => !e)}
              className="flex w-full items-center gap-2 text-left sm:w-auto"
            >
              {labelErrorsPreviewExpanded ? <ChevronUp className="h-5 w-5 text-amber-700" /> : <ChevronDown className="h-5 w-5 text-amber-700" />}
              <div>
                <h2 className="text-lg font-semibold text-amber-950">Alınamayan Trendyol etiketleri ({bulkLabelErrors.length})</h2>
                <p className="text-sm text-amber-900/80">
                  Bu siparişler için Trendyol Ortak Etiket servisinden etiket alınamadı — nedenleri ve ne yapmanız gerektiği aşağıda.
                </p>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setBulkLabelErrors([])}
              className="px-4 py-2 text-sm font-medium text-amber-900 bg-app-surface border border-amber-300 rounded-lg hover:bg-amber-50"
            >
              Kapat
            </button>
          </div>
          {labelErrorsPreviewExpanded && (
            <div className="p-4 space-y-3">
              {(() => {
                const groups = new Map<string, { info: ReturnType<typeof translateLabelError>, orderIds: string[] }>()
                for (const item of bulkLabelErrors) {
                  const info = translateLabelError(item.error)
                  const groupKey = info.isKnown ? info.title : `__unknown__:${item.error}`
                  if (!groups.has(groupKey)) {
                    groups.set(groupKey, { info, orderIds: [] })
                  }
                  groups.get(groupKey)!.orderIds.push(item.order_id)
                }
                return Array.from(groups.values()).map((group, index) => (
                  <div key={index} className="bg-app-surface p-3 rounded-lg border border-amber-200">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-text-primary">
                        {group.info.title}{' '}
                        <span className="text-xs font-normal text-text-muted">({group.orderIds.length} sipariş)</span>
                      </p>
                    </div>
                    <p className="text-xs text-text-secondary mt-1">{group.info.detail}</p>
                    <p className="text-xs text-emerald-700 mt-1 font-medium">Ne yapmalı: {group.info.action}</p>
                    <details className="mt-2">
                      <summary className="text-xs text-text-muted cursor-pointer select-none">
                        Sipariş numaraları ve ham Trendyol mesajı
                      </summary>
                      <p className="text-xs text-text-muted mt-1 break-words">
                        Sipariş no'ları: {group.orderIds.join(', ')}
                      </p>
                      <p className="text-[10px] text-text-muted mt-1 font-mono break-words">
                        Ham mesaj: {group.info.rawMessage}
                      </p>
                    </details>
                  </div>
                ))
              })()}
            </div>
          )}
        </div>
      )}

      {/* Son kargo etiketi önizlemesi — yazdırma tamamlandıktan sonra kapatılabilir */}
      {bulkLabels.length > 0 && (
        <div className="rounded-xl border-2 border-emerald-600/40 bg-emerald-50/30 shadow-card scroll-mt-24">
          <div className="flex flex-col gap-3 border-b border-emerald-200 bg-app-surface/90 px-4 py-3 sm:flex-row sm:items-center sm:justify-between rounded-t-xl">
            <button
              type="button"
              onClick={() => setLabelsPreviewExpanded((e) => !e)}
              className="flex w-full items-center gap-2 text-left sm:w-auto"
            >
              {labelsPreviewExpanded ? <ChevronUp className="h-5 w-5 text-emerald-700" /> : <ChevronDown className="h-5 w-5 text-emerald-700" />}
              <div>
                <h2 className="text-lg font-semibold text-emerald-950">Son kargo etiketi önizlemesi</h2>
                <p className="text-sm text-emerald-900/80">
                  {bulkLabels.length} sipariş — az önce çıkardığınız etiketler. Yeni gelen siparişler yukarıdaki “Sıradaki siparişler” listesinde görünür.
                </p>
              </div>
            </button>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={async () => {
                  const confirmed = window.confirm(
                    `${bulkLabels.length} etiket yazdırılacak. Her etiket ayrı bir sayfa olarak çıkacak. Devam etmek istiyor musunuz?`
                  )
                  if (confirmed) {
                    for (let i = 0; i < bulkLabels.length; i++) {
                      const label = bulkLabels[i]
                      await printSingleLabel(label.label, label.order_id)
                      if (i < bulkLabels.length - 1) {
                        await new Promise(resolve => setTimeout(resolve, 500))
                      }
                    }
                  }
                }}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition text-sm"
              >
                <Printer className="w-4 h-4" />
                Tekrar yazdır
              </button>
              <button
                type="button"
                onClick={() => {
                  setBulkLabels([])
                  setLastLabelBatchOrderIds(new Set())
                }}
                className="px-4 py-2 text-sm font-medium text-emerald-900 bg-app-surface border border-emerald-300 rounded-lg hover:bg-emerald-50"
              >
                Önizlemeyi kapat
              </button>
            </div>
          </div>
          {labelsPreviewExpanded && (
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {bulkLabels.map((label, index) => (
                  <div key={index} className="bg-app-surface p-3 rounded-lg border border-emerald-200 shadow-sm">
                    <p className="text-xs font-semibold text-text-secondary mb-1">Sipariş: {label.order_id}</p>
                    {label.order_date ? (
                      <p className="text-[10px] text-text-muted mb-2 tabular-nums">{formatOrderDateTime(label.order_date)}</p>
                    ) : null}
                    <img
                      src={label.label}
                      alt={`Etiket ${label.order_id}`}
                      className="w-full h-auto rounded border border-app-border mb-2"
                      style={{ maxHeight: '150px', objectFit: 'contain' }}
                    />
                    <button
                      type="button"
                      onClick={() => printSingleLabel(label.label, label.order_id)}
                      className="w-full text-xs px-2 py-1.5 bg-emerald-600 text-white rounded hover:bg-emerald-700 transition"
                    >
                      Yazdır
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-sm text-emerald-900/80 text-center">
                Karışıklığı önlemek için işiniz bitince <strong>Önizlemeyi kapat</strong> ile bu alanı gizleyebilirsiniz.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Generated Barcodes */}
      {generatedBarcodes.length > 0 && (
        <div id="auto-barcode-generated" className="space-y-4 scroll-mt-24">
          <h2 className="text-xl font-semibold text-text-primary">
            Oluşturulan Barkodlar ({generatedBarcodes.filter(b => !statusFilter || b.status === statusFilter || (statusFilter === 'Created' && b.status === 'created')).length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {generatedBarcodes
              .filter(barcode => {
                // Status filtresi: "Created" -> "created" eşleştirmesi
                if (statusFilter) {
                  if (statusFilter === 'Created' && barcode.status !== 'created') {
                    return false
                  }
                  if (statusFilter !== 'Created' && barcode.status !== statusFilter.toLowerCase()) {
                    return false
                  }
                }
                // Arama filtresi
                if (searchQuery) {
                  const query = searchQuery.toLowerCase()
                  if (!barcode.order_id.toLowerCase().includes(query)) {
                    return false
                  }
                }
                return true
              })
              .map((barcode, index) => (
              <div key={index} className="bg-app-surface p-4 rounded-lg shadow-card border-2 border-brand">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold text-text-primary">Sipariş: {barcode.order_id}</h3>
                    <p className="text-sm text-text-secondary tabular-nums">{formatOrderDateTime(barcode.order_date)}</p>
                    <p className="text-xs text-text-muted mt-1">Durum: {barcode.status}</p>
                  </div>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                </div>

                {/* Kargo Etiketi Altına Yapıştırılacak */}
                {barcode.shipping_label && (
                  <div className="mb-3 p-2 bg-yellow-50 border-2 border-brand rounded">
                    <p className="text-xs font-semibold text-brand mb-2 text-center">
                      Kargo Etiketi Altına Yapıştır
                    </p>
                    <img
                      src={barcode.shipping_label}
                      alt={`Shipping Label ${barcode.order_id}`}
                      className="w-full h-auto rounded border border-app-border"
                      style={{ maxHeight: '150px', objectFit: 'contain' }}
                    />
                    <p className="text-xs text-text-secondary mt-2 text-center">
                      %15 indirim • penaltidenim.com
                    </p>
                    <button
                      onClick={() => barcode.shipping_label && downloadImage(barcode.shipping_label, `kargo-etiketi-${barcode.order_id}.png`)}
                      className="mt-2 w-full flex items-center justify-center space-x-1 text-xs px-3 py-1 bg-brand text-white rounded hover:bg-brand-hover transition"
                    >
                      <Download className="w-3 h-3" />
                      <span>Etiketi İndir</span>
                    </button>
                  </div>
                )}

                {/* Barkod gösterimi: backend görseli varsa onu, YOKSA client-side Code128 üret
                    (her kartta gerçek taranabilir lineer barkod görünür — order_id her zaman var). */}
                <div className="mb-3">
                  <div className="rounded border border-app-border bg-app-surface p-3 text-center">
                    {barcode.barcode_image ? (
                      <>
                        <img
                          src={barcode.barcode_image}
                          alt={`Barkod ${barcode.order_id}`}
                          className="mx-auto max-h-16 w-auto object-contain"
                          style={{ imageRendering: 'crisp-edges' }}
                        />
                        <p className="mt-1 font-mono text-xs text-text-secondary">{barcode.order_id}</p>
                      </>
                    ) : (
                      <Barcode value={barcode.order_id} height={56} />
                    )}
                  </div>
                </div>

                <div className="pt-3 border-t border-app-border">
                  <div className="text-sm text-text-primary space-y-1.5">
                    <p><span className="font-semibold">Toplam Ürün:</span> {barcode.order_summary.total_items}</p>
                    <p><span className="font-semibold">Benzersiz:</span> {barcode.order_summary.unique_products}</p>
                    <p><span className="font-semibold">Toplam:</span> {barcode.order_summary.total_value.toFixed(2)} TL</p>
                  </div>
                  {/* Sadece website adı - siyah renkte */}
                  {barcode.order_summary.discount_website && (
                    <div className="mt-3 pt-2 border-t border-app-border">
                      <p className="text-sm font-medium text-black text-center">{barcode.order_summary.discount_website}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {filteredAndSortedOrders.length === 0 && !loading && (
        <div className="bg-app-surface p-6 rounded-lg shadow-card text-center">
          <Package className="w-12 h-12 text-text-muted mx-auto mb-3" />
          <p className="text-text-secondary">
            {searchQuery || statusFilter 
              ? 'Filtrelere uygun sipariş bulunamadı' 
              : 'Kargoya gönderilmesi gereken sipariş bulunmuyor'}
          </p>
        </div>
      )}

      {/* Yazdırma Ayarları Modal */}
      {showPrintSettings && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-app-surface rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6 border-b border-app-border flex items-center justify-between">
              <h2 className="text-xl font-bold text-text-primary">Yazdırma Ayarları</h2>
              <button
                onClick={() => setShowPrintSettings(false)}
                className="text-text-muted hover:text-text-secondary"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Kağıt Boyutu</label>
                <select
                  value={printSettings.paper_size}
                  onChange={(e) => setPrintSettings({...printSettings, paper_size: e.target.value})}
                  className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                >
                  <option value="4x6">4x6 inç</option>
                  <option value="A4">A4</option>
                  <option value="custom">Özel</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Kalite</label>
                <select
                  value={printSettings.quality}
                  onChange={(e) => setPrintSettings({...printSettings, quality: e.target.value})}
                  className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                >
                  <option value="low">Düşük</option>
                  <option value="medium">Orta</option>
                  <option value="high">Yüksek</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Kopya Sayısı</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={printSettings.copies}
                  onChange={(e) => setPrintSettings({...printSettings, copies: parseInt(e.target.value) || 1})}
                  className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Yönlendirme</label>
                <select
                  value={printSettings.orientation}
                  onChange={(e) => setPrintSettings({...printSettings, orientation: e.target.value})}
                  className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                >
                  <option value="portrait">Dikey</option>
                  <option value="landscape">Yatay</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Barkod Formatı</label>
                <select
                  value={barcodeFormat}
                  onChange={(e) => setBarcodeFormat(e.target.value as any)}
                  className="w-full px-3 py-2 border border-app-border rounded-lg focus:ring-2 focus:ring-brand focus:border-transparent"
                >
                  <option value="qr">Sadece QR Kod</option>
                  <option value="code128">Sadece Code128</option>
                  <option value="both">Her İkisi</option>
                </select>
              </div>
            </div>
            <div className="p-6 border-t border-app-border flex items-center justify-end space-x-3">
              <button
                onClick={() => setShowPrintSettings(false)}
                className="px-4 py-2 bg-app-surface-muted text-text-secondary rounded-lg hover:bg-app-surface-muted transition"
              >
                Kapat
              </button>
              <button
                onClick={() => {
                  setShowPrintSettings(false)
                  addNotification('success', 'Yazdırma ayarları kaydedildi')
                }}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition"
              >
                Kaydet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sipariş Detay Modal */}
      {showOrderDetail && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-app-surface rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-app-border flex items-center justify-between">
              <h2 className="text-xl font-bold text-text-primary">Sipariş Detayları - {showOrderDetail}</h2>
              <button
                onClick={() => {
                  setShowOrderDetail(null)
                  setOrderDetail(null)
                }}
                className="text-text-muted hover:text-text-secondary"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6">
              {orderDetail ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-text-secondary">Sipariş tarihi</p>
                      <p className="font-medium tabular-nums">
                        {formatOrderDateTime(orderDetail.order_date ?? orderDetail.orderDate ?? null)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-text-secondary">Durum</p>
                      <p className="font-medium">{orderDetail.status || orderDetail.orderStatus || '-'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-text-secondary">Toplam Tutar</p>
                      <p className="font-medium">
                        {orderDetail.total_amount || orderDetail.totalPrice || orderDetail.totalPriceValue || 0} ₺
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-text-secondary">Kargo Takip</p>
                      <p className="font-medium">{orderDetail.cargo_tracking_number || orderDetail.cargoTrackingNumber || '-'}</p>
                    </div>
                  </div>
                  {orderDetail.items && orderDetail.items.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-text-primary mb-2">Ürünler</h3>
                      <div className="space-y-2">
                        {orderDetail.items.map((item: any, idx: number) => (
                          <div key={idx} className="p-3 bg-app-surface-muted rounded-lg">
                            <p className="font-medium">{item.product_name || item.name}</p>
                            <p className="text-sm text-text-secondary">
                              Adet: {item.quantity} • Fiyat: {item.price} ₺
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <RefreshCw className="w-8 h-8 text-text-muted mx-auto mb-2 animate-spin" />
                  <p className="text-text-secondary">Yükleniyor...</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

