import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import { 
  Upload, 
  Image as ImageIcon, 
  X, 
  Star,
  StarOff,
  Trash2,
  Search,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Eye
} from 'lucide-react'

interface ImageInfo {
  id: string
  product_id: string
  product_name?: string
  filename: string
  url: string
  size: number
  width?: number
  height?: number
  uploaded_at: string
  is_primary: boolean
}

interface ProductWithImages {
  product_id: string
  product_name?: string
  image_count: number
  has_primary: boolean
}

export default function ImageManagement() {
  const [products, setProducts] = useState<ProductWithImages[]>([])
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null)
  const [images, setImages] = useState<ImageInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  useEffect(() => {
    fetchProducts()
  }, [])

  useEffect(() => {
    if (selectedProduct) {
      fetchImages(selectedProduct)
    } else {
      setImages([])
    }
  }, [selectedProduct])

  const fetchProducts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/images/')
      const productsData = response.data || []
      setProducts(productsData)
      
      // Eğer ürün yoksa bilgilendir
      if (productsData.length === 0) {
        setError('Henüz ürün bulunamadı. Siparişler geldikçe ürünler burada görünecek.')
      }
    } catch (err: any) {
      setError('Ürünler yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchImages = async (productId: string) => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get(`/images/${productId}?include_trendyol=true`)
      setImages(response.data || [])
    } catch (err: any) {
      setError('Görseller yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !selectedProduct) return

    // Dosya formatı kontrolü
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if (!validTypes.includes(file.type)) {
      setError('Geçersiz dosya formatı. Sadece JPG, PNG, GIF ve WebP formatları desteklenir.')
      return
    }

    // Dosya boyutu kontrolü (10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('Dosya boyutu çok büyük. Maksimum 10MB olmalıdır.')
      return
    }

    try {
      setUploading(true)
      setError(null)
      setSuccess(null)

      const formData = new FormData()
      formData.append('file', file)
      formData.append('product_id', selectedProduct)
      formData.append('is_primary', 'false')

      await apiClient.post('/images/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setSuccess('Görsel başarıyla yüklendi!')
      await fetchImages(selectedProduct)
      await fetchProducts()
      
      // Input'u temizle
      e.target.value = ''
    } catch (err: any) {
      setError('Görsel yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteImage = async (imageId: string, productId: string) => {
    if (!confirm('Bu görseli silmek istediğinizden emin misiniz?')) {
      return
    }

    try {
      setError(null)
      await apiClient.delete(`/images/${productId}/${imageId}`)
      setSuccess('Görsel başarıyla silindi!')
      await fetchImages(productId)
      await fetchProducts()
    } catch (err: any) {
      setError('Görsel silinemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleSetPrimary = async (imageId: string, productId: string) => {
    try {
      setError(null)
      await apiClient.put(`/images/${productId}/${imageId}/set-primary`)
      setSuccess('Ana görsel güncellendi!')
      await fetchImages(productId)
    } catch (err: any) {
      setError('Ana görsel güncellenemedi: ' + (err.response?.data?.detail || err.message))
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const filteredProducts = products.filter(p =>
    p.product_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.product_name && p.product_name.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-title">Görsel yönetimi</h1>
        <p className="page-subtitle">Ürün görsellerini yükleyin, düzenleyin ve yönetin</p>
      </div>

      {/* Success Message */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center">
            <CheckCircle className="w-5 h-5 mr-2" />
            {success}
          </div>
          <button
            onClick={() => setSuccess(null)}
            className="text-green-600 hover:text-green-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 mr-2" />
            {error}
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-600 hover:text-red-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ürün Listesi */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Ürünler</h2>
              <button
                onClick={fetchProducts}
                className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
                title="Yenile"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>

            {/* Arama */}
            <div className="mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Ürün ara..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Ürün Listesi */}
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {loading && !selectedProduct ? (
                <div className="text-center py-8 text-gray-500">Yükleniyor...</div>
              ) : filteredProducts.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  {searchTerm ? 'Arama sonucu bulunamadı' : 'Henüz görsel yüklenmemiş'}
                </div>
              ) : (
                filteredProducts.map((product) => (
                  <button
                    key={product.product_id}
                    onClick={() => setSelectedProduct(product.product_id)}
                    className={`w-full text-left p-3 rounded-lg border-2 transition ${
                      selectedProduct === product.product_id
                        ? 'border-orange-500 bg-orange-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">
                          {product.product_name || product.product_id}
                        </p>
                        <p className="text-sm text-gray-500">
                          {product.image_count} görsel
                          {product.has_primary && (
                            <span className="ml-2 text-orange-500">★</span>
                          )}
                        </p>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Görsel Yönetimi */}
        <div className="lg:col-span-2">
          {selectedProduct ? (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {products.find(p => p.product_id === selectedProduct)?.product_name || selectedProduct}
                </h2>
                <button
                  onClick={() => setSelectedProduct(null)}
                  className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Yükleme Alanı */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Yeni Görsel Yükle
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-orange-500 transition">
                  <input
                    type="file"
                    accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
                    onChange={handleFileUpload}
                    disabled={uploading}
                    className="hidden"
                    id="image-upload"
                  />
                  <label
                    htmlFor="image-upload"
                    className="cursor-pointer flex flex-col items-center"
                  >
                    {uploading ? (
                      <RefreshCw className="w-12 h-12 text-orange-500 animate-spin mb-2" />
                    ) : (
                      <Upload className="w-12 h-12 text-gray-400 mb-2" />
                    )}
                    <span className="text-gray-600">
                      {uploading ? 'Yükleniyor...' : 'Görsel seçmek için tıklayın'}
                    </span>
                    <span className="text-xs text-gray-500 mt-1">
                      JPG, PNG, GIF, WebP (Max 10MB)
                    </span>
                  </label>
                </div>
              </div>

              {/* Görsel Listesi */}
              {loading ? (
                <div className="text-center py-8 text-gray-500">Yükleniyor...</div>
              ) : images.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  Bu ürün için henüz görsel yüklenmemiş
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {images.map((image) => (
                    <div
                      key={image.id}
                      className="relative group border-2 rounded-lg overflow-hidden"
                    >
                      <div className="aspect-square bg-gray-100 relative">
                        <img
                          src={
                            image.id.startsWith('trendyol_') && image.url.startsWith('http')
                              ? `http://localhost:8000/api/images/${image.product_id}/${image.filename}?url=${encodeURIComponent(image.url)}`
                              : image.url.startsWith('http') 
                                ? image.url 
                                : `http://localhost:8000${image.url}`
                          }
                          alt={image.product_name || image.product_id}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            console.error('Görsel yükleme hatası:', image.url)
                            // Trendyol görseli için alternatif URL dene
                            if (image.id.startsWith('trendyol_')) {
                              const altUrl = `http://localhost:8000/api/images/${image.product_id}/${image.filename}`
                              ;(e.target as HTMLImageElement).src = altUrl
                            } else {
                              (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="%23ddd"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="%23999">Görsel Yüklenemedi</text></svg>'
                            }
                          }}
                        />
                        
                        {/* Overlay */}
                        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition flex items-center justify-center gap-2">
                          <button
                            onClick={() => setPreviewImage(image.url.startsWith('http') ? image.url : `http://localhost:8000${image.url}`)}
                            className="opacity-0 group-hover:opacity-100 p-2 bg-white rounded-lg hover:bg-gray-100 transition"
                            title="Önizle"
                          >
                            <Eye className="w-5 h-5 text-gray-700" />
                          </button>
                          {!image.id.startsWith('trendyol_') && (
                            <>
                              <button
                                onClick={() => handleSetPrimary(image.id, image.product_id)}
                                className={`opacity-0 group-hover:opacity-100 p-2 bg-white rounded-lg hover:bg-gray-100 transition ${
                                  image.is_primary ? 'opacity-100' : ''
                                }`}
                                title={image.is_primary ? 'Ana görsel' : 'Ana görsel yap'}
                              >
                                {image.is_primary ? (
                                  <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
                                ) : (
                                  <StarOff className="w-5 h-5 text-gray-700" />
                                )}
                              </button>
                              <button
                                onClick={() => handleDeleteImage(image.id, image.product_id)}
                                className="opacity-0 group-hover:opacity-100 p-2 bg-red-500 rounded-lg hover:bg-red-600 transition"
                                title="Sil"
                              >
                                <Trash2 className="w-5 h-5 text-white" />
                              </button>
                            </>
                          )}
                          {image.id.startsWith('trendyol_') && (
                            <div className="opacity-0 group-hover:opacity-100 px-2 py-1 bg-blue-500 text-white text-xs rounded">
                              Trendyol
                            </div>
                          )}
                        </div>

                        {/* Ana görsel badge */}
                        {image.is_primary && (
                          <div className="absolute top-2 left-2 bg-yellow-500 text-white px-2 py-1 rounded text-xs font-semibold flex items-center">
                            <Star className="w-3 h-3 mr-1 fill-current" />
                            Ana
                          </div>
                        )}
                      </div>

                      {/* Görsel Bilgileri */}
                      <div className="p-2 bg-white">
                        <p className="text-xs text-gray-500 truncate">
                          {image.id.startsWith('trendyol_') ? 'Trendyol Görseli' : image.filename}
                        </p>
                        <p className="text-xs text-gray-400">
                          {image.size > 0 && formatFileSize(image.size)}
                          {image.width && image.height && ` • ${image.width}×${image.height}`}
                          {image.id.startsWith('trendyol_') && ' • Trendyol\'dan çekildi'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <ImageIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Ürün Seçin
              </h3>
              <p className="text-gray-600">
                Görsel yönetimi yapmak için sol taraftan bir ürün seçin
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Görsel Önizleme Modal */}
      {previewImage && (
        <div
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] p-4">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-4 right-4 text-white hover:text-gray-300 bg-black bg-opacity-50 rounded-full p-2"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={previewImage}
              alt="Önizleme"
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  )
}

