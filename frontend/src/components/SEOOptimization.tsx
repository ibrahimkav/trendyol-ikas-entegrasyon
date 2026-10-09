import { useState } from 'react'
import apiClient from '../config/api'
import { 
  Search, 
  CheckCircle, 
  Lightbulb,
  Target,
  BarChart3,
  Sparkles,
  RefreshCw
} from 'lucide-react'

interface SEORecommendation {
  type: string
  priority: string
  current_value?: string
  recommended_value: string
  reason: string
  impact_score: number
}

interface SEOAnalysis {
  product_id: string
  product_name: string
  seo_score: number
  recommendations: SEORecommendation[]
  keyword_suggestions: string[]
  competitor_analysis?: {
    category: string
    avg_title_length: number
    avg_description_length: number
    common_keywords: string[]
  }
  created_at: string
}

interface OptimizedProduct {
  product_id: string
  optimized_title: string
  optimized_description: string
  suggested_keywords: string[]
  seo_score: number
  improvements: string[]
  created_at: string
}

export default function SEOOptimization() {
  const [productId, setProductId] = useState('')
  const [productName, setProductName] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [category, setCategory] = useState('')
  const [keywords, setKeywords] = useState<string[]>([])
  const [keywordInput, setKeywordInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<SEOAnalysis | null>(null)
  const [optimized, setOptimized] = useState<OptimizedProduct | null>(null)
  const [error, setError] = useState<string | null>(null)

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      setKeywords([...keywords, keywordInput.trim()])
      setKeywordInput('')
    }
  }

  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword))
  }

  const handleAnalyze = async () => {
    if (!productName.trim()) {
      setError('Ürün adı gereklidir')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.post('/seo/analyze', {
        product_id: productId || 'temp',
        product_name: productName,
        product_description: productDescription || undefined,
        category: category || undefined,
        current_keywords: keywords.length > 0 ? keywords : undefined
      })
      setAnalysis(response.data)
    } catch (err: any) {
      setError('SEO analizi yapılamadı: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleOptimize = async () => {
    if (!productName.trim()) {
      setError('Ürün adı gereklidir')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.post('/seo/optimize', {
        product_id: productId || 'temp',
        product_name: productName,
        product_description: productDescription || undefined,
        category: category || undefined,
        target_audience: undefined
      })
      setOptimized(response.data)
    } catch (err: any) {
      setError('Ürün optimizasyonu yapılamadı: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getScoreBgColor = (score: number) => {
    if (score >= 80) return 'bg-green-100'
    if (score >= 60) return 'bg-yellow-100'
    return 'bg-red-100'
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="page-header mb-8">
          <h1 className="page-title">SEO ve ürün optimizasyonu</h1>
          <p className="page-subtitle">AI destekli SEO önerileri ve ürün optimizasyonu</p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-500" />
            Ürün Bilgileri
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ürün ID (Opsiyonel)
              </label>
              <input
                type="text"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Ürün ID"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ürün Adı <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Ürün adını girin"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                {productName.length} / 60 karakter (Önerilen: 30-60)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ürün Açıklaması
              </label>
              <textarea
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                rows={4}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Ürün açıklamasını girin"
              />
              <p className="text-xs text-gray-500 mt-1">
                {productDescription.length} / 300 karakter (Önerilen: 120-300)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Kategori
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Kategori (örn: Giyim, Elektronik)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Anahtar Kelimeler
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addKeyword()}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                  placeholder="Anahtar kelime ekle"
                />
                <button
                  onClick={addKeyword}
                  className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
                >
                  Ekle
                </button>
              </div>
              {keywords.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {keywords.map((keyword, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm"
                    >
                      {keyword}
                      <button
                        onClick={() => removeKeyword(keyword)}
                        className="hover:text-orange-600"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleAnalyze}
                disabled={loading || !productName.trim()}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Search className="w-5 h-5" />
                )}
                SEO Analizi Yap
              </button>
              <button
                onClick={handleOptimize}
                disabled={loading || !productName.trim()}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Sparkles className="w-5 h-5" />
                )}
                Ürünü Optimize Et
              </button>
            </div>
          </div>
        </div>

        {/* SEO Analizi Sonuçları */}
        {analysis && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-orange-500" />
              SEO Analizi Sonuçları
            </h2>

            {/* SEO Skoru */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">SEO Skoru</span>
                <span className={`text-2xl font-bold ${getScoreColor(analysis.seo_score)}`}>
                  {analysis.seo_score.toFixed(1)} / 100
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className={`h-3 rounded-full ${getScoreBgColor(analysis.seo_score)}`}
                  style={{ width: `${analysis.seo_score}%` }}
                />
              </div>
            </div>

            {/* Öneriler */}
            {analysis.recommendations.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Lightbulb className="w-5 h-5 text-yellow-500" />
                  Öneriler ({analysis.recommendations.length})
                </h3>
                <div className="space-y-3">
                  {analysis.recommendations.map((rec, idx) => (
                    <div
                      key={idx}
                      className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getPriorityColor(rec.priority)}`}>
                            {rec.priority === 'high' ? 'Yüksek' : rec.priority === 'medium' ? 'Orta' : 'Düşük'}
                          </span>
                          <span className="text-sm font-medium text-gray-700 capitalize">
                            {rec.type}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-gray-600">
                          Etki: {rec.impact_score.toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{rec.reason}</p>
                      {rec.current_value && (
                        <div className="mb-2">
                          <p className="text-xs text-gray-500 mb-1">Mevcut:</p>
                          <p className="text-sm bg-gray-50 p-2 rounded">{rec.current_value}</p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Önerilen:</p>
                        <p className="text-sm bg-orange-50 p-2 rounded text-orange-900">
                          {rec.recommended_value}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Anahtar Kelime Önerileri */}
            {analysis.keyword_suggestions.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3">Anahtar Kelime Önerileri</h3>
                <div className="flex flex-wrap gap-2">
                  {analysis.keyword_suggestions.map((keyword, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Rakip Analizi */}
            {analysis.competitor_analysis && (
              <div>
                <h3 className="text-lg font-semibold mb-3">Rakip Analizi</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500 mb-1">Ortalama Başlık</p>
                    <p className="text-lg font-semibold">
                      {analysis.competitor_analysis.avg_title_length} karakter
                    </p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500 mb-1">Ortalama Açıklama</p>
                    <p className="text-lg font-semibold">
                      {analysis.competitor_analysis.avg_description_length} karakter
                    </p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500 mb-1">Kategori</p>
                    <p className="text-lg font-semibold">{analysis.competitor_analysis.category}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Optimize Edilmiş Ürün */}
        {optimized && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              Optimize Edilmiş Ürün
            </h2>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Yeni SEO Skoru</span>
                <span className={`text-2xl font-bold ${getScoreColor(optimized.seo_score)}`}>
                  {optimized.seo_score.toFixed(1)} / 100
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className={`h-3 rounded-full ${getScoreBgColor(optimized.seo_score)}`}
                  style={{ width: `${optimized.seo_score}%` }}
                />
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Optimize Edilmiş Başlık
                </label>
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-900">{optimized.optimized_title}</p>
                  <p className="text-xs text-green-700 mt-1">
                    {optimized.optimized_title.length} karakter
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Optimize Edilmiş Açıklama
                </label>
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-900">{optimized.optimized_description}</p>
                  <p className="text-xs text-green-700 mt-1">
                    {optimized.optimized_description.length} karakter
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Önerilen Anahtar Kelimeler
                </label>
                <div className="flex flex-wrap gap-2">
                  {optimized.suggested_keywords.map((keyword, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>

              {optimized.improvements.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Yapılan İyileştirmeler
                  </label>
                  <ul className="list-disc list-inside space-y-1">
                    {optimized.improvements.map((improvement, idx) => (
                      <li key={idx} className="text-sm text-gray-700">{improvement}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}




