import { useState } from 'react'
import apiClient from '../config/api'
import { 
  Download, 
  Upload, 
  FileText, 
  FileSpreadsheet,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  X,
  File
} from 'lucide-react'

export default function ExportImport() {
  const [exportType, setExportType] = useState<'products' | 'orders' | 'inventory'>('products')
  const [exportFormat, setExportFormat] = useState<'csv' | 'excel'>('excel')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importType, setImportType] = useState<'prices'>('prices')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [importResults, setImportResults] = useState<any>(null)

  const handleExport = async () => {
    try {
      setLoading(true)
      setError(null)
      setSuccess(null)
      
      const response = await apiClient.get(
        `/export-import/export/${exportType}/${exportFormat}`,
        { responseType: 'blob' }
      )
      
      // Dosyayı indir
      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      
      const extension = exportFormat === 'excel' ? 'xlsx' : 'csv'
      link.download = `${exportType}_${new Date().toISOString().split('T')[0]}.${extension}`
      
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      setSuccess(`${exportType} başarıyla export edildi!`)
    } catch (err: any) {
      setError('Export işlemi başarısız: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    if (!importFile) {
      setError('Lütfen bir dosya seçin')
      return
    }

    try {
      setLoading(true)
      setError(null)
      setSuccess(null)
      setImportResults(null)

      const formData = new FormData()
      formData.append('file', importFile)

      const response = await apiClient.post(
        `/export-import/import/${importType}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      setImportResults(response.data.results)
      setSuccess(response.data.message)
      setImportFile(null)
    } catch (err: any) {
      setError('Import işlemi başarısız: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const downloadTemplate = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await apiClient.get(
        `/export-import/export/template/${importType}`,
        { responseType: 'blob' }
      )
      
      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `ornek_${importType}_import.csv`
      
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      setSuccess('Şablon dosyası indirildi!')
    } catch (err: any) {
      setError('Şablon indirilemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const getExportTypeLabel = (type: string) => {
    switch (type) {
      case 'products':
        return 'Ürünler'
      case 'orders':
        return 'Siparişler'
      case 'inventory':
        return 'Stok Bilgileri'
      default:
        return type
    }
  }

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-title">Export / import</h1>
        <p className="page-subtitle">Verileri dışa aktarın veya toplu içe aktarın</p>
      </div>

      {/* Export Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Download className="w-5 h-5 mr-2 text-orange-500" />
          Veri Export
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Export Edilecek Veri
            </label>
            <div className="grid grid-cols-3 gap-3">
              {(['products', 'orders', 'inventory'] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setExportType(type)}
                  className={`px-4 py-3 rounded-lg border-2 transition ${
                    exportType === type
                      ? 'border-orange-500 bg-orange-50 text-orange-700 font-semibold'
                      : 'border-gray-200 hover:border-gray-300 text-gray-700'
                  }`}
                >
                  {getExportTypeLabel(type)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Export Formatı
            </label>
            <div className="flex space-x-3">
              <button
                onClick={() => setExportFormat('excel')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg border-2 transition ${
                  exportFormat === 'excel'
                    ? 'border-orange-500 bg-orange-50 text-orange-700 font-semibold'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                <FileSpreadsheet className="w-4 h-4" />
                <span>Excel (.xlsx)</span>
              </button>
              <button
                onClick={() => setExportFormat('csv')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg border-2 transition ${
                  exportFormat === 'csv'
                    ? 'border-orange-500 bg-orange-50 text-orange-700 font-semibold'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>CSV</span>
              </button>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={loading}
            className="w-full px-4 py-3 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {loading ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              <Download className="w-5 h-5" />
            )}
            <span>Export Et</span>
          </button>
        </div>
      </div>

      {/* Import Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Upload className="w-5 h-5 mr-2 text-green-500" />
          Veri Import
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Import Tipi
            </label>
            <select
              value={importType}
              onChange={(e) => setImportType(e.target.value as any)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
            >
              <option value="prices">Toplu Fiyat Güncelleme</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Dosya Seç
            </label>
            <div className="flex items-center space-x-4">
              <label className="flex-1 cursor-pointer">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <div className="px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-orange-500 transition text-center">
                  {importFile ? (
                    <div className="flex items-center justify-center space-x-2 text-gray-700">
                      <File className="w-5 h-5" />
                      <span>{importFile.name}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setImportFile(null)
                        }}
                        className="ml-2 text-red-500 hover:text-red-700"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="text-gray-500">
                      <Upload className="w-6 h-6 mx-auto mb-2" />
                      <span>Dosya seçmek için tıklayın</span>
                      <p className="text-xs mt-1">CSV veya Excel (.xlsx) formatında</p>
                    </div>
                  )}
                </div>
              </label>
            </div>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={downloadTemplate}
              className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition flex items-center justify-center space-x-2"
            >
              <FileText className="w-4 h-4" />
              <span>Şablon İndir</span>
            </button>
            <button
              onClick={handleImport}
              disabled={loading || !importFile}
              className="flex-1 px-4 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="w-5 h-5 animate-spin" />
              ) : (
                <Upload className="w-5 h-5" />
              )}
              <span>Import Et</span>
            </button>
          </div>
        </div>
      </div>

      {/* Import Format Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">Import Dosya Formatı</h3>
        <div className="text-sm text-blue-800 space-y-1">
          <p><strong>Fiyat Güncelleme:</strong></p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>Kolon 1: Ürün ID (veya Barkod)</li>
            <li>Kolon 2: Yeni Fiyat</li>
            <li>İlk satır başlık olmalı: "Ürün ID", "Yeni Fiyat"</li>
            <li>CSV veya Excel (.xlsx) formatında olmalı</li>
          </ul>
        </div>
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

      {/* Import Results */}
      {importResults && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Import Sonuçları</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-2xl font-bold text-green-600">{importResults.success || 0}</p>
              <p className="text-sm text-gray-600 mt-1">Başarılı</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-2xl font-bold text-red-600">{importResults.failed || 0}</p>
              <p className="text-sm text-gray-600 mt-1">Başarısız</p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-600">
                {(importResults.success || 0) + (importResults.failed || 0)}
              </p>
              <p className="text-sm text-gray-600 mt-1">Toplam</p>
            </div>
          </div>

          {importResults.errors && importResults.errors.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold text-gray-900 mb-2">Hatalar:</h4>
              <div className="max-h-40 overflow-y-auto bg-gray-50 rounded p-3">
                {importResults.errors.slice(0, 10).map((error: string, index: number) => (
                  <p key={index} className="text-sm text-red-600 mb-1">{error}</p>
                ))}
                {importResults.errors.length > 10 && (
                  <p className="text-sm text-gray-500 mt-2">
                    ... ve {importResults.errors.length - 10} hata daha
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}




