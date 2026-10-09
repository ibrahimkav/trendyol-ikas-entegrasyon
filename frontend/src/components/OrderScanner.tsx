import { useState, useRef, useEffect } from 'react'
import apiClient from '../config/api'
import { formatOrderDateTime } from '../utils/formatOrderDateTime'
import { Scan, Search, Package, Image as ImageIcon, X, RefreshCw, AlertCircle, Camera, QrCode, Loader2 } from 'lucide-react'

type ZxingReader = {
  decodeFromCanvas: (canvas: HTMLCanvasElement) => { getText: () => string }
}

let zxingLoadPromise: Promise<{
  BrowserMultiFormatReader: (typeof import('@zxing/browser'))['BrowserMultiFormatReader']
  BarcodeFormat: (typeof import('@zxing/library'))['BarcodeFormat']
  DecodeHintType: (typeof import('@zxing/library'))['DecodeHintType']
}> | null = null

function loadZxing() {
  if (!zxingLoadPromise) {
    zxingLoadPromise = Promise.all([import('@zxing/browser'), import('@zxing/library')]).then(([b, lib]) => ({
      BrowserMultiFormatReader: b.BrowserMultiFormatReader,
      BarcodeFormat: lib.BarcodeFormat,
      DecodeHintType: lib.DecodeHintType,
    }))
  }
  return zxingLoadPromise
}

/**
 * Kargo etiketlerinde barkod sık dikey basılır (çizgiler görüntüde yatay).
 * ZXing 1D için çizgilerin bitmap'te dikey olması daha iyi sonuç verir; dört açıyı deneriz.
 */
function tryDecodeVideoFrame(reader: ZxingReader, video: HTMLVideoElement): string | null {
  if (video.readyState < video.HAVE_ENOUGH_DATA) return null
  const w = video.videoWidth
  const h = video.videoHeight
  if (w < 2 || h < 2) return null

  const drawRotated = (deg: 0 | 90 | 180 | 270): HTMLCanvasElement => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) {
      canvas.width = 1
      canvas.height = 1
      return canvas
    }
    if (deg === 0) {
      canvas.width = w
      canvas.height = h
      ctx.drawImage(video, 0, 0, w, h)
    } else if (deg === 90) {
      canvas.width = h
      canvas.height = w
      ctx.translate(h, 0)
      ctx.rotate(Math.PI / 2)
      ctx.drawImage(video, 0, 0, w, h)
    } else if (deg === 180) {
      canvas.width = w
      canvas.height = h
      ctx.translate(w, h)
      ctx.rotate(Math.PI)
      ctx.drawImage(video, 0, 0, w, h)
    } else {
      canvas.width = h
      canvas.height = w
      ctx.translate(0, w)
      ctx.rotate(-Math.PI / 2)
      ctx.drawImage(video, 0, 0, w, h)
    }
    return canvas
  }

  for (const deg of [0, 90, 180, 270] as const) {
    try {
      const canvas = drawRotated(deg)
      const result = reader.decodeFromCanvas(canvas)
      const text = result?.getText()?.trim()
      if (text) return text
    } catch {
      // okunamadı, sonraki açı
    }
  }
  return null
}

interface OrderItem {
  product_id: string
  product_name: string
  quantity: number
  price: number
  images: string[]
  model_number?: string
  size?: string
  color?: string
  barcode?: string
  sku?: string
  category?: string
}

interface OrderData {
  success: boolean
  order_id: string
  order_number: string
  order_date: string
  status: string
  total_amount: number
  total_items: number
  items: OrderItem[]
  customer: {
    first_name: string
    last_name: string
    email: string
    phone: string
  }
  cargo: {
    tracking_number: string
    company: string
  }
}

export default function OrderScanner() {
  const [scanning, setScanning] = useState(false)
  const [orderData, setOrderData] = useState<OrderData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualInput, setManualInput] = useState('')
  const [showManualInput, setShowManualInput] = useState(true) // Default olarak manuel input göster
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const zxingControlsRef = useRef<{ stop: () => void } | null>(null)
  const [scanMode, setScanMode] = useState<'camera' | 'manual'>('manual')
  const [insecureContext, setInsecureContext] = useState(false)

  // Güvenli bağlam: http://192.168.x.x gibi adreslerde kamera çoğu tarayıcıda kapalıdır.
  useEffect(() => {
    setInsecureContext(typeof window !== 'undefined' && !window.isSecureContext)
  }, [])

  useEffect(() => {
    setScanMode('manual')
    setShowManualInput(true)
    setScanning(false)

    return () => {
      zxingControlsRef.current?.stop()
      zxingControlsRef.current = null
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }
  }, [])

  const stopCamera = () => {
    zxingControlsRef.current?.stop()
    zxingControlsRef.current = null
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setScanning(false)
    setScanMode('manual')
  }

  const scanBarcode = async (barcodeData: string) => {
    if (!barcodeData || !barcodeData.trim()) {
      setError('Barkod verisi boş olamaz')
      return
    }

    setLoading(true)
    setError(null)
    setOrderData(null)

    try {
      const response = await apiClient.post('/barcode/scan-order', {
        barcode_data: barcodeData
      })

      if (response.data.success) {
        setOrderData(response.data)
        setManualInput('')
        if (scanning) {
          stopCamera()
        }
      } else {
        setError('Sipariş bulunamadı')
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Barkod okuma hatası'
      setError(errorMsg)
      setOrderData(null)
    } finally {
      setLoading(false)
    }
  }

  /** Kargo etiketi CODE128 + QR; dikey etiket için çoklu açı + TRY_HARDER (ZXing yalnızca kamera açılırken yüklenir). */
  const startBarcodeContinuousScan = async () => {
    const videoEl = videoRef.current
    if (!videoEl) return

    zxingControlsRef.current?.stop()
    zxingControlsRef.current = null

    const { BrowserMultiFormatReader, BarcodeFormat, DecodeHintType } = await loadZxing()

    const hints = new Map<import('@zxing/library').DecodeHintType, unknown>()
    hints.set(DecodeHintType.POSSIBLE_FORMATS, [
      BarcodeFormat.CODE_128,
      BarcodeFormat.QR_CODE,
      BarcodeFormat.EAN_13,
      BarcodeFormat.CODE_39,
    ])
    hints.set(DecodeHintType.TRY_HARDER, true)

    const reader = new BrowserMultiFormatReader(hints as Map<import('@zxing/library').DecodeHintType, unknown>)
    let handled = false

    try {
      await videoEl.play().catch(() => undefined)

      const intervalMs = 120
      const id = window.setInterval(() => {
        if (handled) return
        const v = videoRef.current
        if (!v?.srcObject) return
        const text = tryDecodeVideoFrame(reader, v)
        if (!text) return
        handled = true
        window.clearInterval(id)
        zxingControlsRef.current = null
        void scanBarcode(text)
        stopCamera()
      }, intervalMs)

      zxingControlsRef.current = {
        stop: () => {
          window.clearInterval(id)
        },
      }
    } catch (e) {
      console.error('Barkod tarama başlatılamadı:', e)
    }
  }

  const startCamera = async () => {
    try {
      setError(null)
      setShowManualInput(false) // Kamera açılırken manuel input'u gizle
      
      // Mobil cihaz tespiti
      const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
      
      // Mobil cihazlarda önce kamera iznini kontrol et
      if (isMobile && navigator.permissions && navigator.permissions.query) {
        try {
          console.log('Kamera izni kontrol ediliyor...')
          const permissionStatus = await navigator.permissions.query({ name: 'camera' as PermissionName })
          console.log('Kamera izin durumu:', permissionStatus.state)
          
          if (permissionStatus.state === 'denied') {
            throw new Error('Kamera erişim izni reddedildi. Lütfen tarayıcı ayarlarından kamera iznini açın.')
          }
          
          // İzin durumunu dinle
          permissionStatus.onchange = () => {
            console.log('Kamera izin durumu değişti:', permissionStatus.state)
          }
        } catch (permError: any) {
          // Permissions API desteklenmiyorsa veya hata varsa devam et
          console.log('İzin kontrolü yapılamadı, devam ediliyor:', permError)
        }
      }
      
      // Önce modern API'yi dene
      // navigator.mediaDevices kontrolü - mobil Chrome'da HTTP üzerinden undefined olabilir
      if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
        // Mobil cihaz tespiti
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
        const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)
        const isAndroid = /Android/i.test(navigator.userAgent)
        
        console.log('Cihaz bilgisi:', { 
          isMobile, 
          isIOS, 
          isAndroid, 
          userAgent: navigator.userAgent,
          protocol: window.location.protocol,
          hostname: window.location.hostname
        })

        // Barkod okutmak için arka kamera (environment) tercih edilir; masaüstünde ideal yok sayılır / tek kamera
        const videoConstraints: MediaTrackConstraints | boolean = isMobile
          ? { facingMode: { ideal: 'environment' } }
          : true

        console.log('Kamera açılıyor (mobilde önce arka kamera):', { isMobile, videoConstraints })

        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: videoConstraints
          })
          
          console.log('Kamera başarıyla açıldı:', stream)
          
          // Önce state'leri güncelle (video element render edilsin)
          setScanMode('camera')
          setScanning(true)
          setShowManualInput(false)
          
          // Stream'i kaydet
          streamRef.current = stream
          
          // React render cycle için kısa bir bekleme (video element render edilsin)
          await new Promise(resolve => setTimeout(resolve, 100))
          
          // Video element kontrolü
          let retries = 0
          while (!videoRef.current && retries < 20) {
            console.log(`Video element bekleniyor... (${retries + 1}/20)`)
            await new Promise(resolve => setTimeout(resolve, 50))
            retries++
          }
          
          if (!videoRef.current) {
            console.error('Video element bulunamadı! Stream kaydedildi ama görüntü gösterilemiyor.')
            throw new Error('Video element render edilemedi. Sayfayı yenileyin.')
          }
          
          // Stream'i video elementine ata
          try {
            console.log('Stream video elementine atanıyor, videoRef.current:', videoRef.current)
            videoRef.current.srcObject = stream
            
            // Video element'in yüklenmesini bekle
            await new Promise((resolve) => {
              if (videoRef.current) {
                const onLoaded = () => {
                  console.log('Video metadata yüklendi')
                  resolve(true)
                }
                videoRef.current.onloadedmetadata = onLoaded
                // Timeout ekle (3 saniye)
                setTimeout(() => resolve(true), 3000)
              } else {
                resolve(true)
              }
            })
            
            console.log('Kamera başarıyla video elementine atandı ve hazır')

            await startBarcodeContinuousScan()
            return
          } catch (assignError: any) {
            console.error('Stream video elementine atanırken hata:', assignError)
            stream.getTracks().forEach(track => track.stop()) // Stream'i temizle
            throw new Error('Kamera görüntüsü gösterilemedi: ' + (assignError.message || 'Bilinmeyen hata'))
          }
        } catch (modernError: any) {
          // Modern API başarısız oldu - hatayı logla
          console.error('Modern API hatası (ilk deneme):', {
            name: modernError.name,
            message: modernError.message,
            constraint: modernError.constraint,
            error: modernError
          })
          
          // İzin hatası ise direkt fırlat (retry gereksiz)
          if (modernError.name === 'NotAllowedError' || modernError.name === 'PermissionDeniedError') {
            throw modernError
          }
          
          // Diğer hatalar için retry yap (mobil cihazlarda veya constraint hatası)
          // İlk denemede zaten en basit constraint kullandık, bu yüzden retry'da da aynı şeyi yapıyoruz
          // Ama belki izin verildikten sonra çalışır
          console.log('Retry yapılıyor (izin verildikten sonra tekrar deneme)...', {
            errorName: modernError.name,
            errorMessage: modernError.message,
            isMobile
          })
          
          try {
            // Kısa bir bekleme (izin işleminin tamamlanması için)
            await new Promise(resolve => setTimeout(resolve, 200))

            // Arka kamera kısıtı reddedildiyse herhangi bir kamera
            const simpleStream = await navigator.mediaDevices.getUserMedia({
              video: true
            })
              
              console.log('Basit constraint ile kamera başarıyla açıldı:', simpleStream)
              
              // Önce state'leri güncelle
              setScanMode('camera')
              setScanning(true)
              setShowManualInput(false)
              streamRef.current = simpleStream
              
              // React render cycle için bekle
              await new Promise(resolve => setTimeout(resolve, 100))
              
              // Video element kontrolü
              let retries = 0
              while (!videoRef.current && retries < 20) {
                await new Promise(resolve => setTimeout(resolve, 50))
                retries++
              }
              
              if (!videoRef.current) {
                simpleStream.getTracks().forEach(track => track.stop())
                throw new Error('Video element render edilemedi')
              }
              
              videoRef.current.srcObject = simpleStream

              await new Promise((resolve) => {
                if (videoRef.current) {
                  videoRef.current.onloadedmetadata = () => resolve(true)
                  setTimeout(() => resolve(true), 3000)
                } else resolve(true)
              })
              await startBarcodeContinuousScan()
              return // Başarılı, çık
            } catch (retryError: any) {
              console.error('Basit constraint ile de başarısız:', {
                name: retryError.name,
                message: retryError.message
              })
              // İkinci deneme de başarısız oldu, orijinal hatayı fırlat
              throw modernError
            }
          
          // Retry başarısız oldu, orijinal hatayı fırlat
          throw modernError
        }
      }
      
      // Modern API yoksa eski API'yi dene
      // Eski tarayıcılar için fallback
      const getUserMedia = 
        (navigator as any).webkitGetUserMedia ||
        (navigator as any).mozGetUserMedia ||
        (navigator as any).msGetUserMedia
      
      if (getUserMedia) {
        try {
          console.log('Eski API deneniyor...')
          // Eski API için Promise wrapper
          const stream = await new Promise<MediaStream>((resolve, reject) => {
            const videoOpt = /Android|webOS|iPhone|iPad|iPod/i.test(navigator.userAgent)
              ? { facingMode: 'environment' as const }
              : true
            getUserMedia.call(
              navigator,
              { video: videoOpt },
              resolve,
              reject
            )
          })
          
          console.log('Eski API ile kamera başarıyla açıldı:', stream)
          
          // State'leri güncelle
          setScanMode('camera')
          setScanning(true)
          setShowManualInput(false)
          streamRef.current = stream
          
          // React render cycle için bekle
          await new Promise(resolve => setTimeout(resolve, 100))
          
          // Video element kontrolü
          let retries = 0
          while (!videoRef.current && retries < 20) {
            await new Promise(resolve => setTimeout(resolve, 50))
            retries++
          }
          
          if (!videoRef.current) {
            stream.getTracks().forEach(track => track.stop())
            throw new Error('Video element render edilemedi')
          }
          
          videoRef.current.srcObject = stream

          await new Promise((resolve) => {
            if (videoRef.current) {
              videoRef.current.onloadedmetadata = () => resolve(true)
              setTimeout(() => resolve(true), 3000)
            } else resolve(true)
          })
          await startBarcodeContinuousScan()
          return // Başarılı, çık
        } catch (legacyError: any) {
          console.error('Eski API de başarısız:', legacyError)
          // Eski API de başarısız, devam et
        }
      }
      
      // Hiçbir API çalışmadı - detaylı hata mesajı
      const isHttp = window.location.protocol === 'http:'
      const isLocalNetwork = window.location.hostname.startsWith('192.168.') || 
                            window.location.hostname.startsWith('10.') ||
                            window.location.hostname === 'localhost' ||
                            window.location.hostname === '127.0.0.1'
      const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
      const isChromeBrowser = /Chrome/i.test(navigator.userAgent) && !/Edge/i.test(navigator.userAgent)
      
      console.error('Hiçbir kamera API\'si çalışmadı:', {
        hasMediaDevices: !!navigator.mediaDevices,
        hasGetUserMedia: !!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function'),
        hasLegacyAPI: !!getUserMedia,
        isHttp,
        isLocalNetwork,
        isMobile: isMobileDevice,
        isChrome: isChromeBrowser,
        userAgent: navigator.userAgent,
        protocol: window.location.protocol,
        hostname: window.location.hostname
      })
      
      // Mobil Chrome HTTP üzerinden kamera erişimine izin vermeyebilir
      // navigator.mediaDevices undefined olabilir
      if (isMobileDevice && isChromeBrowser && isHttp) {
        throw new Error('Mobil Chrome HTTP üzerinden kamera erişimine izin vermiyor (güvenlik nedeniyle).\n\nÇözümler:\n1. HTTPS kullanın (önerilen)\n2. Manuel giriş kullanın\n3. Chrome flags: chrome://flags/#unsafely-treat-insecure-origin-as-secure adresine gidin, siteyi ekleyin ve "Enabled" yapın')
      } else if (!navigator.mediaDevices && !getUserMedia) {
        // API yok - tarayıcı desteklemiyor
        throw new Error('Tarayıcınız kamera API\'sini desteklemiyor. Lütfen güncel bir tarayıcı (Chrome, Firefox, Edge, Safari) kullanın.')
      } else if (isHttp && !isLocalNetwork) {
        throw new Error('Kamera erişimi için HTTPS bağlantısı gerekiyor. Lütfen HTTPS kullanarak tekrar deneyin veya manuel giriş kullanın.')
      } else {
        // Genel hata - muhtemelen izin sorunu veya API yok
        throw new Error('Kamera erişimi sağlanamadı. Lütfen:\n1. Tarayıcı ayarlarından kamera iznini kontrol edin\n2. Sayfayı yenileyin\n3. Manuel giriş kullanın')
      }
      
    } catch (err: any) {
      // Hata detaylarını console'a yazdır (debug için)
      console.error('Kamera erişim hatası:', {
        name: err.name,
        message: err.message,
        stack: err.stack,
        constraint: err.constraint,
        error: err
      })
      
      let errorMessage = 'Kamera erişimi sağlanamadı'
      
      // Hata türüne göre mesaj belirle
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorMessage = 'Kamera erişim izni reddedildi. Lütfen tarayıcı ayarlarından kamera iznini açın ve sayfayı yenileyin.'
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorMessage = 'Kamera bulunamadı. Cihazınızda kamera olduğundan emin olun.'
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errorMessage = 'Kamera başka bir uygulama tarafından kullanılıyor olabilir. Lütfen diğer uygulamaları kapatın.'
      } else if (err.name === 'OverconstrainedError' || err.name === 'ConstraintNotSatisfiedError') {
        // Kısıtlama hatası - facingMode desteklenmiyor olabilir
        errorMessage = 'Kamera ayarları desteklenmiyor. Lütfen manuel giriş kullanın veya farklı bir kamera deneyin.'
      } else if (err.name === 'NotSupportedError') {
        errorMessage = 'Tarayıcınız kamera API\'sini desteklemiyor. Lütfen güncel bir tarayıcı (Chrome, Safari, Firefox) kullanın.'
      } else if (err.message) {
        // Özel hata mesajı varsa onu kullan
        if (err.message.includes('HTTPS')) {
          errorMessage = err.message
        } else if (err.message.includes('kamera')) {
          errorMessage = err.message
        } else if (err.message.includes('API')) {
          errorMessage = err.message
        } else {
          // Genel hata mesajına detay ekle
          errorMessage = `Kamera erişimi sağlanamadı: ${err.message}. Lütfen tarayıcı ayarlarından kamera iznini kontrol edin veya manuel giriş kullanın.`
        }
      } else {
        // Bilinmeyen hata - detaylı mesaj
        const isHttp = window.location.protocol === 'http:'
        const isLocalNetwork = window.location.hostname.startsWith('192.168.') || 
                              window.location.hostname.startsWith('10.') ||
                              window.location.hostname === 'localhost' ||
                              window.location.hostname === '127.0.0.1'
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
        const isChrome = /Chrome/i.test(navigator.userAgent) && !/Edge/i.test(navigator.userAgent)
        
        // Mobil Chrome HTTP üzerinden kamera erişimine izin vermeyebilir
        if (isMobile && isChrome && isHttp) {
          errorMessage = 'Mobil Chrome HTTP üzerinden kamera erişimine izin vermiyor. Çözümler:\n1. HTTPS kullanın\n2. Manuel giriş kullanın\n3. Chrome ayarlarından: chrome://flags/#unsafely-treat-insecure-origin-as-secure adresine gidin ve siteyi güvenli olarak işaretleyin'
        } else if (isHttp && !isLocalNetwork) {
          errorMessage = 'Kamera erişimi için HTTPS bağlantısı gerekiyor. Lütfen HTTPS kullanarak tekrar deneyin veya manuel giriş kullanın.'
        } else {
          errorMessage = 'Kamera erişimi sağlanamadı. Lütfen tarayıcı ayarlarından kamera iznini kontrol edin, sayfayı yenileyin veya manuel giriş kullanın.'
        }
      }
      
      setError(errorMessage)
      setScanMode('manual')
      setShowManualInput(true)
      
      // Hata durumunda kamerayı kapat
      stopCamera()
    }
  }

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (manualInput.trim()) {
      scanBarcode(manualInput.trim())
    }
  }

  const handleReset = () => {
    setOrderData(null)
    setError(null)
    setManualInput('')
    stopCamera()
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
      <div className="page-header">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-trendyol-primary text-white shadow-sm">
            <QrCode className="h-6 w-6" aria-hidden />
          </div>
          <div className="min-w-0">
            <h1 className="page-title">Sipariş barkod okutucu</h1>
            <p className="page-subtitle">
              Kargo etiketindeki barkodu okutarak sipariş detaylarını görüntüleyin
            </p>
          </div>
        </div>
        {insecureContext && (
          <div className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/90 p-3 text-sm text-amber-950">
            <strong>Telefonda kamera:</strong> Bu adres güvenli (HTTPS) değil; çoğu mobil tarayıcı kamerayı açmaz.
            Geliştirme sunucusunu <code className="rounded bg-amber-100 px-1">https://</code> ile açın (Vite HTTPS kullanır).
            Örnek: <code className="break-all rounded bg-amber-100 px-1">https://192.168.x.x:3000</code> — sertifika uyarısında devam edin.
          </div>
        )}
      </div>

      {/* Scanner Section */}
      {!orderData && (
        <div className="card overflow-hidden">
          <div className="dashboard-section-body space-y-4">
            {/* Mode Toggle */}
            <div className="grid grid-cols-2 gap-2 sm:flex sm:gap-3">
              <button
                type="button"
                onClick={() => {
                  setShowManualInput(true)
                  stopCamera()
                  setScanMode('manual')
                }}
                className={`flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-trendyol-primary focus-visible:ring-offset-2 ${
                  scanMode === 'manual'
                    ? 'bg-trendyol-primary text-white shadow-sm'
                    : 'border border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                }`}
              >
                <Search className="h-5 w-5 shrink-0" aria-hidden />
                Manuel giriş
              </button>
              <button
                type="button"
                onClick={startCamera}
                className={`flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-trendyol-primary focus-visible:ring-offset-2 ${
                  scanMode === 'camera'
                    ? 'bg-trendyol-primary text-white shadow-sm'
                    : 'border border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                }`}
              >
                <Camera className="h-5 w-5 shrink-0" aria-hidden />
                Kamera
              </button>
            </div>

              {/* Camera View - Her zaman render et ama görünürlüğünü kontrol et */}
              <div className={`relative bg-black rounded-lg overflow-hidden ${scanning && scanMode === 'camera' ? 'block' : 'hidden'}`}>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-auto max-h-[400px]"
                />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-2 border-orange-500 rounded-lg w-64 h-64">
                      <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-orange-500"></div>
                      <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-orange-500"></div>
                      <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-orange-500"></div>
                      <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-orange-500"></div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={stopCamera}
                    className="absolute right-3 top-3 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-red-600 text-white shadow-md transition hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                    aria-label="Kamerayı kapat"
                  >
                    <X className="h-5 w-5" />
                  </button>
                  <div className="absolute bottom-4 left-0 right-0 text-center px-2">
                    <p className="text-white bg-black/50 px-4 py-2 rounded-lg inline-block text-sm">
                      Barkodu çerçeveye alın; dikey etiketlerde telefonu yatay veya yan tutmayı deneyin.
                    </p>
                  </div>
              </div>

              {/* Manual Input */}
              {(showManualInput || scanMode === 'manual') && !scanning && (
                <form onSubmit={handleManualSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="order-scanner-manual" className="mb-2 block text-sm font-medium text-slate-700">
                      Barkod / sipariş numarası
                    </label>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
                      <input
                        id="order-scanner-manual"
                        type="text"
                        value={manualInput}
                        onChange={(e) => setManualInput(e.target.value)}
                        placeholder="Barkod veya sipariş numarası…"
                        className="min-h-[48px] flex-1 rounded-xl border border-slate-200 px-4 py-3 text-base text-slate-900 shadow-sm outline-none focus:border-trendyol-primary focus:ring-2 focus:ring-trendyol-primary/25"
                        autoComplete="off"
                        autoFocus
                      />
                      <button
                        type="submit"
                        disabled={loading || !manualInput.trim()}
                        className="btn-primary min-h-[48px] w-full shrink-0 disabled:cursor-not-allowed sm:w-auto"
                      >
                        {loading ? (
                          <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            <span>Aranıyor...</span>
                          </>
                        ) : (
                          <>
                            <Scan className="w-5 h-5" />
                            <span>Ara</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </form>
              )}

              {/* Error Message */}
              {error && (
                <div className="flex items-start gap-3 rounded-xl border border-red-200/80 bg-red-50/90 p-4">
                  <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-red-900">{error}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setError(null)}
                    className="shrink-0 rounded-lg p-2 text-red-600 hover:bg-red-100/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                    aria-label="Hatayı kapat"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              )}
          </div>
        </div>
        )}

        {/* Order Details */}
        {orderData && (
          <div className="space-y-6">
            {/* Order Header */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold text-gray-900 mb-2">
                    Sipariş #{orderData.order_number}
                  </h2>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p><span className="font-medium">Sipariş tarihi:</span>{' '}
                      <span className="tabular-nums">{formatOrderDateTime(orderData.order_date)}</span>
                    </p>
                    <p><span className="font-medium">Durum:</span> 
                      <span className={`ml-2 px-2 py-1 rounded text-xs font-medium ${
                        orderData.status === 'Shipped' ? 'bg-green-100 text-green-800' :
                        orderData.status === 'Delivered' ? 'bg-blue-100 text-blue-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {orderData.status}
                      </span>
                    </p>
                    <p><span className="font-medium">Toplam:</span> {orderData.total_amount.toFixed(2)} ₺</p>
                    <p><span className="font-medium">Ürün Sayısı:</span> {orderData.total_items} adet</p>
                  </div>
                </div>
                <button
                  onClick={handleReset}
                  className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
              </div>

              {/* Cargo Info */}
              {orderData.cargo.tracking_number && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-sm text-gray-600">
                    <span className="font-medium">Kargo Takip No:</span> {orderData.cargo.tracking_number}
                  </p>
                  {orderData.cargo.company && (
                    <p className="text-sm text-gray-600 mt-1">
                      <span className="font-medium">Kargo Firması:</span> {orderData.cargo.company}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Products List */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                <Package className="w-5 h-5 mr-2 text-orange-500" />
                Kargolanacak Ürünler ({orderData.items.length})
              </h3>
              
              <div className="space-y-4">
                {orderData.items.map((item, index) => (
                  <div
                    key={`${item.product_id}-${index}`}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                  >
                    <div className="flex space-x-4">
                      {/* Product Image */}
                      <div className="flex-shrink-0">
                        {item.images && item.images.length > 0 ? (
                          <img
                            src={
                              item.images[0].includes('cdn.dsmcdn.com') && item.product_id
                                ? `/api/images/${item.product_id}/image.jpg?url=${encodeURIComponent(item.images[0])}`
                                : item.images[0]
                            }
                            alt={item.product_name}
                            className="w-24 h-24 object-cover rounded-lg border border-gray-200"
                            crossOrigin="anonymous"
                            onError={(e) => {
                              // İlk görsel yüklenemezse, proxy üzerinden dene
                              const img = e.target as HTMLImageElement
                              const raw = item.images[0]
                              if (raw.startsWith('https://cdn.dsmcdn.com') && !img.src.includes('/api/images/')) {
                                img.src = `/api/images/${item.product_id || 'p'}/image.jpg?url=${encodeURIComponent(raw)}`
                              } else if (img.src.includes('/api/images/')) {
                                // Proxy de başarısız oldu, placeholder göster
                                img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23ddd" width="100" height="100"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EGörsel Yok%3C/text%3E%3C/svg%3E'
                              } else {
                                img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23ddd" width="100" height="100"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EGörsel Yok%3C/text%3E%3C/svg%3E'
                              }
                            }}
                          />
                        ) : (
                          <div className="w-24 h-24 bg-gray-100 rounded-lg flex items-center justify-center">
                            <ImageIcon className="w-8 h-8 text-gray-400" />
                          </div>
                        )}
                      </div>

                      {/* Product Details */}
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                          {item.product_name}
                        </h4>
                        
                        <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 mb-2">
                          <div>
                            <span className="font-medium">Miktar:</span> {item.quantity} adet
                          </div>
                          <div>
                            <span className="font-medium">Fiyat:</span> {item.price.toFixed(2)} ₺
                          </div>
                          {item.model_number && (
                            <div>
                              <span className="font-medium">Model:</span> {item.model_number}
                            </div>
                          )}
                          {item.size && (
                            <div>
                              <span className="font-medium">Beden:</span> {item.size}
                            </div>
                          )}
                          {item.color && (
                            <div>
                              <span className="font-medium">Renk:</span> {item.color}
                            </div>
                          )}
                          {item.sku && (
                            <div>
                              <span className="font-medium">SKU:</span> {item.sku}
                            </div>
                          )}
                        </div>

                        {item.barcode && (
                          <div className="text-xs text-gray-500 mt-2">
                            <span className="font-medium">Barkod:</span> {item.barcode}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Customer Info */}
            {orderData.customer.first_name && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Müşteri Bilgileri</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-600">Ad Soyad:</span>
                    <p className="text-gray-900">{orderData.customer.first_name} {orderData.customer.last_name}</p>
                  </div>
                  {orderData.customer.phone && (
                    <div>
                      <span className="font-medium text-gray-600">Telefon:</span>
                      <p className="text-gray-900">{orderData.customer.phone}</p>
                    </div>
                  )}
                  {orderData.customer.email && (
                    <div>
                      <span className="font-medium text-gray-600">E-posta:</span>
                      <p className="text-gray-900">{orderData.customer.email}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Reset Button */}
            <div className="text-center">
              <button
                type="button"
                onClick={handleReset}
                className="btn-primary mx-auto min-h-[48px]"
              >
                <RefreshCw className="h-5 w-5" />
                Yeni barkod okut
              </button>
            </div>
          </div>
        )}
    </div>
  )
}

