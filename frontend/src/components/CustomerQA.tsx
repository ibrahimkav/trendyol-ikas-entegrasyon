import { useState, useEffect } from 'react'
import apiClient from '../config/api'
import {
  MessageSquare, Send, Bot, User, RefreshCw, AlertCircle, CheckCircle, X,
  ThumbsUp, ThumbsDown, Pencil, Brain, ChevronDown, ChevronUp, Save, BookOpen
} from 'lucide-react'

interface QAPair {
  id: string
  question: string
  answer: string
  customer_id?: string
  order_id?: string
  created_at: string
  status: 'pending' | 'answered'
}

interface SimilarQuestion {
  question: string
  answer: string
  similarity?: number
}

interface AISuggestion {
  suggested_answer: string
  confidence: number
  reasoning: string
  answer_source?: 'learned' | 'learned+template' | 'template' | 'generic'
  category?: string | null
  similar_questions?: SimilarQuestion[]
}

interface LearningStats {
  total_count: number
  answered_count: number
  pending_count: number
  learning_pool_size: number
  accepted_count: number
  edited_count: number
  rejected_count: number
  avg_confidence: number
  acceptance_rate?: number
}

const SOURCE_LABELS: Record<string, string> = {
  learned: 'Öğrenilmiş cevap',
  'learned+template': 'Öğrenilmiş + şablon',
  template: 'Kategori şablonu',
  generic: 'Genel şablon',
}

const CATEGORY_LABELS: Record<string, string> = {
  kargo: 'Kargo',
  iade: 'İade',
  ödeme: 'Ödeme',
  ürün: 'Ürün',
  kampanya: 'Kampanya',
}

export default function CustomerQA() {
  const [qaList, setQaList] = useState<QAPair[]>([])
  const [selectedQA, setSelectedQA] = useState<QAPair | null>(null)
  const [answer, setAnswer] = useState('')
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null)
  const [loading, setLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newQuestion, setNewQuestion] = useState('')
  const [newCustomerId, setNewCustomerId] = useState('')
  const [newOrderId, setNewOrderId] = useState('')
  const [learningStats, setLearningStats] = useState<LearningStats | null>(null)
  const [showTemplates, setShowTemplates] = useState(false)
  const [templates, setTemplates] = useState<Record<string, string>>({})
  const [templateCategories, setTemplateCategories] = useState<string[]>([])
  const [templatesSaving, setTemplatesSaving] = useState(false)

  useEffect(() => {
    fetchQAHistory()
    fetchLearningStats()
    fetchTemplates()
  }, [])

  const fetchQAHistory = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.get('/customer-qa/')
      setQaList(response.data.qa_list || [])
    } catch (err: any) {
      setError('Soru-cevap geçmişi yüklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchLearningStats = async () => {
    try {
      const response = await apiClient.get('/customer-qa/stats/learning')
      setLearningStats(response.data)
    } catch {
      // İstatistikler kritik değil, sessizce geç
    }
  }

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/customer-qa/templates')
      setTemplates(response.data.templates || {})
      setTemplateCategories(response.data.categories || [])
    } catch {
      // Şablonlar kritik değil
    }
  }

  const saveTemplates = async () => {
    try {
      setTemplatesSaving(true)
      setError(null)
      await apiClient.put('/customer-qa/templates', { templates })
      setError(null)
      await fetchTemplates()
    } catch (err: any) {
      setError('Şablonlar kaydedilemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setTemplatesSaving(false)
    }
  }

  const getAISuggestion = async (question: string, qaId: string) => {
    try {
      setAiLoading(true)
      setError(null)
      const response = await apiClient.post('/customer-qa/ai-suggest', {
        question: question,
        qa_id: qaId
      })
      setAiSuggestion(response.data)
      setAnswer(response.data.suggested_answer || '')
    } catch (err: any) {
      setError('AI önerisi alınamadı: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAiLoading(false)
    }
  }

  const handleSelectQA = (qa: QAPair) => {
    setSelectedQA(qa)
    setAnswer('')
    setAiSuggestion(null)
    if (qa.status === 'pending') {
      getAISuggestion(qa.question, qa.id)
    }
  }

  const clearSelection = () => {
    setSelectedQA(null)
    setAnswer('')
    setAiSuggestion(null)
  }

  const submitFeedback = async (feedback: 'accepted' | 'edited' | 'rejected', finalAnswer?: string) => {
    if (!selectedQA) return

    try {
      setFeedbackLoading(true)
      setError(null)
      await apiClient.post(`/customer-qa/${selectedQA.id}/feedback`, {
        feedback,
        final_answer: finalAnswer,
      })
      await fetchQAHistory()
      await fetchLearningStats()
      clearSelection()
    } catch (err: any) {
      setError('Feedback gönderilemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setFeedbackLoading(false)
    }
  }

  const handleAcceptSuggestion = () => {
    if (!aiSuggestion) return
    submitFeedback('accepted', aiSuggestion.suggested_answer)
  }

  const handleRejectSuggestion = () => {
    submitFeedback('rejected')
    setAiSuggestion(null)
    setAnswer('')
  }

  const handleSubmitAnswer = async () => {
    if (!selectedQA || !answer.trim()) {
      setError('Lütfen bir cevap yazın')
      return
    }

    // AI önerisi varsa feedback döngüsü üzerinden gönder
    if (aiSuggestion) {
      const isEdited = answer.trim() !== aiSuggestion.suggested_answer.trim()
      await submitFeedback(isEdited ? 'edited' : 'accepted', answer.trim())
      return
    }

    try {
      setLoading(true)
      setError(null)
      await apiClient.post(`/customer-qa/${selectedQA.id}/answer`, {
        answer: answer
      })
      await fetchQAHistory()
      await fetchLearningStats()
      clearSelection()
    } catch (err: any) {
      setError('Cevap gönderilemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleAddQuestion = async () => {
    if (!newQuestion.trim()) {
      setError('Lütfen bir soru yazın')
      return
    }

    try {
      setLoading(true)
      setError(null)
      await apiClient.post('/customer-qa/', {
        question: newQuestion,
        customer_id: newCustomerId || undefined,
        order_id: newOrderId || undefined
      })
      await fetchQAHistory()
      setNewQuestion('')
      setNewCustomerId('')
      setNewOrderId('')
    } catch (err: any) {
      setError('Soru eklenemedi: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const topSimilarity = aiSuggestion?.similar_questions?.[0]?.similarity
  const answerSource = aiSuggestion?.answer_source
  const isAnswerEdited = aiSuggestion && answer.trim() !== aiSuggestion.suggested_answer.trim()

  return (
    <div className="space-y-6">
      <div className="page-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">Müşteri soru-cevap</h1>
          <p className="page-subtitle">Yerel AI ile soruları yanıtlayın, öğrenme havuzunu büyütün</p>
        </div>
        <button
          onClick={() => { fetchQAHistory(); fetchLearningStats() }}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Yenile</span>
        </button>
      </div>

      {/* Öğrenme istatistikleri paneli */}
      {learningStats && (
        <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-5 h-5 text-indigo-600" />
            <h3 className="font-semibold text-indigo-900">Yerel AI Öğrenme Durumu</h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <StatCard label="Havuz" value={learningStats.learning_pool_size} />
            <StatCard label="Bekleyen" value={learningStats.pending_count} color="yellow" />
            <StatCard label="Kabul" value={learningStats.accepted_count} color="green" />
            <StatCard label="Düzenlenen" value={learningStats.edited_count} color="blue" />
            <StatCard label="Reddedilen" value={learningStats.rejected_count} color="red" />
            <StatCard
              label="Kabul oranı"
              value={`%${learningStats.acceptance_rate ?? 0}`}
              color="indigo"
            />
            <StatCard
              label="Ort. güven"
              value={`%${Math.round(learningStats.avg_confidence * 100)}`}
              color="purple"
            />
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-red-900">Hata</h3>
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <button onClick={() => setError(null)}>
            <X className="w-4 h-4 text-red-600" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sol taraf: Soru listesi */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Soru Listesi</h2>

          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Yeni Soru Ekle</h3>
            <textarea
              value={newQuestion}
              onChange={(e) => setNewQuestion(e.target.value)}
              placeholder="Müşteri sorusunu yazın..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent mb-2"
              rows={3}
            />
            <div className="grid grid-cols-2 gap-2 mb-2">
              <input
                type="text"
                value={newCustomerId}
                onChange={(e) => setNewCustomerId(e.target.value)}
                placeholder="Müşteri ID (opsiyonel)"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent text-sm"
              />
              <input
                type="text"
                value={newOrderId}
                onChange={(e) => setNewOrderId(e.target.value)}
                placeholder="Sipariş ID (opsiyonel)"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent text-sm"
              />
            </div>
            <button
              onClick={handleAddQuestion}
              disabled={loading || !newQuestion.trim()}
              className="w-full px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50"
            >
              Soru Ekle
            </button>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {loading && qaList.length === 0 ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-trendyol-primary"></div>
                <p className="mt-4 text-gray-600">Yükleniyor...</p>
              </div>
            ) : qaList.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <MessageSquare className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                <p>Henüz soru yok</p>
              </div>
            ) : (
              qaList.map((qa) => (
                <div
                  key={qa.id}
                  onClick={() => handleSelectQA(qa)}
                  className={`p-4 border rounded-lg cursor-pointer transition ${
                    selectedQA?.id === qa.id
                      ? 'border-trendyol-primary bg-trendyol-primary/5'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <User className="w-4 h-4 text-gray-500" />
                        <p className="text-sm font-medium text-gray-900">{qa.question}</p>
                      </div>
                      {qa.answer && (
                        <div className="flex items-center space-x-2 mt-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <p className="text-sm text-gray-600">{qa.answer.substring(0, 100)}...</p>
                        </div>
                      )}
                      {qa.status === 'pending' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800 mt-2">
                          Bekliyor
                        </span>
                      )}
                    </div>
                    {qa.status === 'pending' && (
                      <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Sağ taraf: Cevap yazma ve AI önerisi */}
        <div className="bg-white rounded-lg shadow-md p-6">
          {selectedQA ? (
            <>
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Cevap Yaz</h2>

              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <User className="w-5 h-5 text-gray-500" />
                  <p className="font-medium text-gray-900">Soru:</p>
                </div>
                <p className="text-gray-700">{selectedQA.question}</p>
                {selectedQA.customer_id && (
                  <p className="text-xs text-gray-500 mt-2">Müşteri ID: {selectedQA.customer_id}</p>
                )}
                {selectedQA.order_id && (
                  <p className="text-xs text-gray-500">Sipariş ID: {selectedQA.order_id}</p>
                )}
              </div>

              {/* AI Önerisi */}
              {aiLoading ? (
                <div className="mb-4 p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Bot className="w-5 h-5 text-blue-500 animate-pulse" />
                    <p className="text-sm text-blue-700">Yerel AI önerisi hazırlanıyor...</p>
                  </div>
                </div>
              ) : aiSuggestion ? (
                <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Bot className="w-5 h-5 text-blue-500" />
                      <p className="font-semibold text-blue-900">Yerel AI Önerisi</p>
                      <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                        %{Math.round(aiSuggestion.confidence * 100)} güven
                      </span>
                      {answerSource && (
                        <span className="text-xs px-2 py-1 bg-indigo-100 text-indigo-700 rounded">
                          {SOURCE_LABELS[answerSource] || answerSource}
                        </span>
                      )}
                      {aiSuggestion.category && (
                        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                          {CATEGORY_LABELS[aiSuggestion.category] || aiSuggestion.category}
                        </span>
                      )}
                    </div>
                  </div>

                  {topSimilarity !== undefined && topSimilarity > 0 && (
                    <p className="text-sm text-indigo-700 font-medium mb-2">
                      %{Math.round(topSimilarity * 100)} benzer geçmiş cevaptan öğrendim
                    </p>
                  )}

                  <p className="text-sm text-gray-700 mb-2 whitespace-pre-wrap">{aiSuggestion.suggested_answer}</p>

                  {aiSuggestion.reasoning && (
                    <p className="text-xs text-gray-600 italic mb-3">{aiSuggestion.reasoning}</p>
                  )}

                  {aiSuggestion.similar_questions && aiSuggestion.similar_questions.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-blue-200">
                      <p className="text-xs font-semibold text-blue-900 mb-2">Benzer Geçmiş Sorular:</p>
                      {aiSuggestion.similar_questions.slice(0, 2).map((sq, idx) => (
                        <div key={idx} className="text-xs text-gray-600 mb-1">
                          <p className="font-medium">
                            S: {sq.question}
                            {sq.similarity !== undefined && (
                              <span className="ml-1 text-indigo-600">(%{Math.round(sq.similarity * 100)})</span>
                            )}
                          </p>
                          <p className="ml-2">C: {sq.answer.substring(0, 80)}{sq.answer.length > 80 ? '...' : ''}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Feedback butonları */}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      onClick={handleAcceptSuggestion}
                      disabled={feedbackLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition disabled:opacity-50"
                    >
                      <ThumbsUp className="w-4 h-4" />
                      Kabul Et
                    </button>
                    <button
                      onClick={handleRejectSuggestion}
                      disabled={feedbackLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-100 text-red-700 text-sm rounded-lg hover:bg-red-200 transition disabled:opacity-50"
                    >
                      <ThumbsDown className="w-4 h-4" />
                      Reddet
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {aiSuggestion ? 'Cevabı düzenleyebilirsiniz:' : 'Cevabınız:'}
                </label>
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Cevabınızı yazın..."
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent"
                  rows={6}
                />
                {isAnswerEdited && (
                  <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                    <Pencil className="w-3 h-3" />
                    AI önerisinden farklı — gönderildiğinde "düzenlenmiş" olarak öğrenilecek
                  </p>
                )}
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={handleSubmitAnswer}
                  disabled={loading || feedbackLoading || !answer.trim()}
                  className="flex-1 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  <Send className="w-4 h-4" />
                  <span>
                    {aiSuggestion
                      ? isAnswerEdited ? 'Düzenlenmiş Olarak Gönder' : 'Kabul Et ve Gönder'
                      : 'Cevabı Gönder'}
                  </span>
                </button>
                <button
                  onClick={clearSelection}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
                >
                  İptal
                </button>
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-400" />
              <p>Yanıtlamak için bir soru seçin</p>
            </div>
          )}
        </div>
      </div>

      {/* Cevap şablonu yönetimi */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={() => setShowTemplates(!showTemplates)}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition"
        >
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-gray-600" />
            <span className="font-semibold text-gray-900">Cevap Şablonları</span>
            <span className="text-xs text-gray-500">(kargo / iade / ödeme / ürün / kampanya)</span>
          </div>
          {showTemplates ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>

        {showTemplates && (
          <div className="p-4 border-t border-gray-100 space-y-4">
            <p className="text-sm text-gray-600">
              AI, benzer geçmiş cevap bulamadığında bu şablonları kullanır. Değişiklikler anında geçerli olur.
            </p>
            {templateCategories.map((cat) => (
              <div key={cat}>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {CATEGORY_LABELS[cat] || cat}
                </label>
                <textarea
                  value={templates[cat] || ''}
                  onChange={(e) => setTemplates((prev) => ({ ...prev, [cat]: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-trendyol-primary focus:border-transparent text-sm"
                />
              </div>
            ))}
            <button
              onClick={saveTemplates}
              disabled={templatesSaving}
              className="flex items-center gap-2 px-4 py-2 bg-trendyol-primary text-white rounded-lg hover:bg-trendyol-secondary transition disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{templatesSaving ? 'Kaydediliyor...' : 'Şablonları Kaydet'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  color = 'gray',
}: {
  label: string
  value: string | number
  color?: 'gray' | 'yellow' | 'green' | 'blue' | 'red' | 'indigo' | 'purple'
}) {
  const colors = {
    gray: 'bg-white text-gray-900',
    yellow: 'bg-yellow-50 text-yellow-800',
    green: 'bg-green-50 text-green-800',
    blue: 'bg-blue-50 text-blue-800',
    red: 'bg-red-50 text-red-800',
    indigo: 'bg-indigo-50 text-indigo-800',
    purple: 'bg-purple-50 text-purple-800',
  }
  return (
    <div className={`rounded-lg p-3 text-center ${colors[color]}`}>
      <p className="text-lg font-bold">{value}</p>
      <p className="text-xs opacity-75">{label}</p>
    </div>
  )
}
