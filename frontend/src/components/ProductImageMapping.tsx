import { useState, useEffect, useRef } from 'react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import { Image, Plus, Search, Edit, Trash2, Save, X, AlertCircle, Upload, FileText } from 'lucide-react'
import ConfirmDialog from './ui/ConfirmDialog'
import Toggle from './ui/Toggle'

interface ImageMapping {
  id: number
  product_code: string
  barcode?: string
  content_id?: string
  product_name?: string
  image_urls: string[]
  primary_image_url?: string
  is_active: boolean
  notes?: string
  created_at: string
  updated_at: string
}

export default function ProductImageMapping() {
  const toast = useToast()
  const [mappings, setMappings] = useState<ImageMapping[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formData, setFormData] = useState({
    product_code: '',
    barcode: '',
    content_id: '',
    product_name: '',
    image_urls: [''],
    primary_image_url: '',
    notes: ''
  })

  // Onay modal'ları (w3-confirm-dialogs: native confirm() yerine) — her akış için hedef/seçim state'i.
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null)
  const [autoSyncDialogOpen, setAutoSyncDialogOpen] = useState(false)
  const [autoSyncDownload, setAutoSyncDownload] = useState(true)
  const [excelImportFile, setExcelImportFile] = useState<File | null>(null)
  const [excelDownload, setExcelDownload] = useState(true)
  const [trendyolSyncDialogOpen, setTrendyolSyncDialogOpen] = useState(false)
  const [trendyolDownload, setTrendyolDownload] = useState(true)
  const excelFileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    fetchMappings()
  }, [])

  const fetchMappings = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get('/product-images/')
      setMappings(response.data)
    } catch (err: any) {
      setError('Görsel eşleştirmeleri yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleAddImageUrl = () => {
    setFormData({
      ...formData,
      image_urls: [...formData.image_urls, '']
    })
  }

  const handleRemoveImageUrl = (index: number) => {
    const newUrls = formData.image_urls.filter((_, i) => i !== index)
    setFormData({
      ...formData,
      image_urls: newUrls.length > 0 ? newUrls : ['']
    })
  }

  const handleImageUrlChange = (index: number, value: string) => {
    const newUrls = [...formData.image_urls]
    newUrls[index] = value
    setFormData({
      ...formData,
      image_urls: newUrls
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Boş URL'leri filtrele
    const validUrls = formData.image_urls.filter(url => url.trim() !== '')
    if (validUrls.length === 0) {
      setError('En az bir görsel URL\'si gerekli')
      return
    }

    if (!formData.product_code.trim()) {
      setError('Product Code gerekli')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const payload = {
        product_code: formData.product_code.trim(),
        barcode: formData.barcode.trim() || undefined,
        content_id: formData.content_id.trim() || undefined,
        product_name: formData.product_name.trim() || undefined,
        image_urls: validUrls,
        primary_image_url: formData.primary_image_url.trim() || validUrls[0] || undefined,
        notes: formData.notes.trim() || undefined
      }

      if (editingId) {
        await apiClient.put(`/product-images/${editingId}`, payload)
      } else {
        await apiClient.post('/product-images/', payload)
      }

      setShowAddForm(false)
      setEditingId(null)
      resetForm()
      fetchMappings()
    } catch (err: any) {
      setError('Görsel eşleştirmesi kaydedilemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (mapping: ImageMapping) => {
    setFormData({
      product_code: mapping.product_code,
      barcode: mapping.barcode || '',
      content_id: mapping.content_id || '',
      product_name: mapping.product_name || '',
      image_urls: mapping.image_urls.length > 0 ? mapping.image_urls : [''],
      primary_image_url: mapping.primary_image_url || '',
      notes: mapping.notes || ''
    })
    setEditingId(mapping.id)
    setShowAddForm(true)
  }

  const handleDeleteClick = (id: number) => {
    setDeleteTargetId(id)
  }

  const confirmDelete = async () => {
    if (deleteTargetId == null) return
    const id = deleteTargetId
    try {
      await apiClient.delete(`/product-images/${id}`)
      fetchMappings()
    } catch (err: any) {
      setError('Görsel eşleştirmesi silinemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setDeleteTargetId(null)
    }
  }

  const openAutoSyncDialog = () => {
    setAutoSyncDownload(true)
    setAutoSyncDialogOpen(true)
  }

  const confirmAutoSync = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.post('/product-images/auto-sync', null, {
        params: {
          overwrite_existing: false,
          download_images: autoSyncDownload
        }
      })

      toast({
        type: 'success',
        message: `Otomatik senkron: +${response.data.created} oluşturuldu, ${response.data.updated} güncellendi, ${response.data.skipped} atlandı.`,
      })
      fetchMappings()
    } catch (err: any) {
      setError('Otomatik senkronizasyon başarısız: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setAutoSyncDialogOpen(false)
    }
  }

  const handleExcelFileSelected = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      setError('Sadece Excel dosyaları (.xlsx, .xls) desteklenir')
      event.target.value = ''
      return
    }

    setExcelDownload(true)
    setExcelImportFile(file)
  }

  const cancelExcelImport = () => {
    setExcelImportFile(null)
    if (excelFileInputRef.current) excelFileInputRef.current.value = ''
  }

  const confirmExcelImport = async () => {
    if (!excelImportFile) return
    setLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', excelImportFile)

      const response = await apiClient.post('/product-images/import-excel', formData, {
        params: {
          download_images: excelDownload
        },
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      toast({
        type: 'success',
        message: `Excel: +${response.data.created} oluşturuldu, ${response.data.updated} güncellendi, ${response.data.error_count || 0} hata.`,
      })
      fetchMappings()
    } catch (err: any) {
      setError('Excel import başarısız: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setExcelImportFile(null)
      if (excelFileInputRef.current) excelFileInputRef.current.value = ''
    }
  }

  const openTrendyolSyncDialog = () => {
    setTrendyolDownload(true)
    setTrendyolSyncDialogOpen(true)
  }

  const confirmTrendyolSync = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.post('/product-images/sync-from-trendyol', null, {
        params: {
          download_images: trendyolDownload
        }
      })

      toast({
        type: 'success',
        message: `Trendyol senkron: +${response.data.created} oluşturuldu, ${response.data.updated} güncellendi, ${response.data.error_count || 0} hata.`,
      })
      fetchMappings()
    } catch (err: any) {
      setError('Trendyol senkronizasyon başarısız: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setTrendyolSyncDialogOpen(false)
    }
  }

  const resetForm = () => {
    setFormData({
      product_code: '',
      barcode: '',
      content_id: '',
      product_name: '',
      image_urls: [''],
      primary_image_url: '',
      notes: ''
    })
  }

  const filteredMappings = mappings.filter(mapping => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      mapping.product_code.toLowerCase().includes(query) ||
      (mapping.barcode && mapping.barcode.toLowerCase().includes(query)) ||
      (mapping.content_id && mapping.content_id.toLowerCase().includes(query)) ||
      (mapping.product_name && mapping.product_name.toLowerCase().includes(query))
    )
  })

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-orange-500 p-3 rounded-lg">
                <Image className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="page-title text-xl sm:text-2xl">Ürün görsel eşleştirmeleri</h1>
                <p className="page-subtitle text-sm">Product code / barkod ile görsel URL eşlemesi</p>
              </div>
            </div>
            <div className="flex items-center space-x-2 flex-wrap gap-2">
              <button
                onClick={openTrendyolSyncDialog}
                disabled={loading}
                className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Upload className="w-5 h-5" />
                <span>Trendyol'dan Çek</span>
              </button>
              <label className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition flex items-center space-x-2 cursor-pointer disabled:opacity-50">
                <FileText className="w-5 h-5" />
                <span>Excel'den İçe Aktar</span>
                <input
                  ref={excelFileInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleExcelFileSelected}
                  className="hidden"
                  disabled={loading}
                />
              </label>
              <button
                onClick={openAutoSyncDialog}
                disabled={loading}
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Upload className="w-5 h-5" />
                <span>Siparişlerden Çek</span>
              </button>
              <button
                onClick={() => {
                  resetForm()
                  setEditingId(null)
                  setShowAddForm(true)
                }}
                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition flex items-center space-x-2"
              >
                <Plus className="w-5 h-5" />
                <span>Yeni Eşleştirme</span>
              </button>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-6">
          <div className="flex items-center space-x-2">
            <Search className="w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Product Code, Barcode, Content ID veya Ürün Adı ile ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
            />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Add/Edit Form */}
        {showAddForm && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                {editingId ? 'Eşleştirmeyi Düzenle' : 'Yeni Eşleştirme Ekle'}
              </h2>
              <button
                onClick={() => {
                  setShowAddForm(false)
                  setEditingId(null)
                  resetForm()
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Product Code <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.product_code}
                    onChange={(e) => setFormData({ ...formData, product_code: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                    required
                    disabled={!!editingId}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Barcode
                  </label>
                  <input
                    type="text"
                    value={formData.barcode}
                    onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Content ID
                  </label>
                  <input
                    type="text"
                    value={formData.content_id}
                    onChange={(e) => setFormData({ ...formData, content_id: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Ürün Adı
                  </label>
                  <input
                    type="text"
                    value={formData.product_name}
                    onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Görsel URL'leri <span className="text-red-500">*</span>
                </label>
                {formData.image_urls.map((url, index) => (
                  <div key={index} className="flex items-center space-x-2 mb-2">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => handleImageUrlChange(index, e.target.value)}
                      placeholder="https://cdn.dsmcdn.com/..."
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                      required={index === 0}
                    />
                    {formData.image_urls.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveImageUrl(index)}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={handleAddImageUrl}
                  className="mt-2 px-4 py-2 text-orange-500 border border-orange-500 rounded-lg hover:bg-orange-50 transition flex items-center space-x-2"
                >
                  <Plus className="w-4 h-4" />
                  <span>Görsel URL Ekle</span>
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Ana Görsel URL (opsiyonel - boş bırakılırsa ilk görsel kullanılır)
                </label>
                <input
                  type="url"
                  value={formData.primary_image_url}
                  onChange={(e) => setFormData({ ...formData, primary_image_url: e.target.value })}
                  placeholder="https://cdn.dsmcdn.com/..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Notlar
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  placeholder="Ek notlar..."
                />
              </div>

              <div className="flex items-center space-x-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition disabled:opacity-50 flex items-center space-x-2"
                >
                  <Save className="w-5 h-5" />
                  <span>{loading ? 'Kaydediliyor...' : 'Kaydet'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false)
                    setEditingId(null)
                    resetForm()
                  }}
                  className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
                >
                  İptal
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Mappings List */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Eşleştirmeler ({filteredMappings.length})
          </h2>

          {loading && !mappings.length ? (
            <div className="text-center py-8 text-gray-500">Yükleniyor...</div>
          ) : filteredMappings.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              {searchQuery ? 'Arama sonucu bulunamadı' : 'Henüz görsel eşleştirmesi yok'}
            </div>
          ) : (
            <div className="space-y-4">
              {filteredMappings.map((mapping) => (
                <div
                  key={mapping.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {mapping.product_name || mapping.product_code}
                        </h3>
                        {mapping.is_active ? (
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">Aktif</span>
                        ) : (
                          <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded">Pasif</span>
                        )}
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm text-gray-600 mb-3">
                        <div>
                          <span className="font-medium">Product Code:</span> {mapping.product_code}
                        </div>
                        {mapping.barcode && (
                          <div>
                            <span className="font-medium">Barcode:</span> {mapping.barcode}
                          </div>
                        )}
                        {mapping.content_id && (
                          <div>
                            <span className="font-medium">Content ID:</span> {mapping.content_id}
                          </div>
                        )}
                      </div>

                      <div className="mb-3">
                        <span className="text-sm font-medium text-gray-700">Görseller ({mapping.image_urls.length}):</span>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {mapping.image_urls.map((url, idx) => (
                            <div key={idx} className="relative group">
                              <img
                                src={url}
                                alt={`Görsel ${idx + 1}`}
                                className="w-20 h-20 object-cover rounded border border-gray-200"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="80" height="80"%3E%3Crect fill="%23ddd" width="80" height="80"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em" font-size="10"%3EGörsel Yok%3C/text%3E%3C/svg%3E'
                                }}
                              />
                              {url === mapping.primary_image_url && (
                                <div className="absolute top-0 right-0 bg-orange-500 text-white text-xs px-1 rounded">Ana</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {mapping.notes && (
                        <div className="text-sm text-gray-600 mb-2">
                          <span className="font-medium">Notlar:</span> {mapping.notes}
                        </div>
                      )}

                      <div className="text-xs text-gray-500">
                        Oluşturulma: {new Date(mapping.created_at).toLocaleString('tr-TR')} • 
                        Güncelleme: {new Date(mapping.updated_at).toLocaleString('tr-TR')}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 ml-4">
                      <button
                        onClick={() => handleEdit(mapping)}
                        className="p-2 text-blue-500 hover:bg-blue-50 rounded-lg transition"
                        title="Düzenle"
                      >
                        <Edit className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDeleteClick(mapping.id)}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition"
                        title="Sil"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={deleteTargetId !== null}
        title="Görsel eşleştirmesini sil"
        description="Bu görsel eşleştirmesini silmek istediğinizden emin misiniz?"
        confirmLabel="Sil"
        confirmVariant="danger"
        onCancel={() => setDeleteTargetId(null)}
        onConfirm={confirmDelete}
      />

      <ConfirmDialog
        open={autoSyncDialogOpen}
        title="Siparişlerden otomatik eşleştirme"
        description="Siparişlerden otomatik olarak görsel eşleştirmeleri oluşturulacak. Mevcut eşleştirmeler güncellenmeyecek."
        confirmLabel="Devam Et"
        onCancel={() => setAutoSyncDialogOpen(false)}
        onConfirm={confirmAutoSync}
        loading={loading}
      >
        <Toggle
          label="Görselleri fiziksel olarak da indirip kaydet (önerilen)"
          checked={autoSyncDownload}
          onChange={setAutoSyncDownload}
          disabled={loading}
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={excelImportFile !== null}
        title="Excel'den içe aktar"
        description={excelImportFile ? `"${excelImportFile.name}" dosyasından görsel eşleştirmeleri içe aktarılacak.` : undefined}
        confirmLabel="İçe Aktar"
        onCancel={cancelExcelImport}
        onConfirm={confirmExcelImport}
        loading={loading}
      >
        <Toggle
          label="Görselleri fiziksel olarak da indirip kaydet (önerilen)"
          checked={excelDownload}
          onChange={setExcelDownload}
          disabled={loading}
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={trendyolSyncDialogOpen}
        title="Trendyol'dan ürünleri çek"
        description="Trendyol API'den tüm ürünler çekilecek ve görselleri veritabanına kaydedilecek. Bu işlem biraz zaman alabilir."
        confirmLabel="Devam Et"
        onCancel={() => setTrendyolSyncDialogOpen(false)}
        onConfirm={confirmTrendyolSync}
        loading={loading}
      >
        <Toggle
          label="Görselleri fiziksel olarak da indirip kaydet (önerilen)"
          checked={trendyolDownload}
          onChange={setTrendyolDownload}
          disabled={loading}
        />
      </ConfirmDialog>
    </div>
  )
}

