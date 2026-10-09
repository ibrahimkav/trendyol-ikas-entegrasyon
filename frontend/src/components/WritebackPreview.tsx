import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight, Loader2 } from 'lucide-react'
import apiClient from '../config/api'
import { Button, DataTable, Input, Select, formatCurrency, type DataTableColumn } from './ui'

/**
 * w3-writeback-preview-ui — hive/docs/price-writeback-spec.md: Dilim 1 (SADECE PROVA).
 * GET /api/pricing/writeback-preview salt okuma — hiçbir fiyat Trendyol'a veya yerel DB'ye
 * yazılmaz. Dilim 2 (gerçek tek-ürün yazma) bu bileşende YOK — ayrı bir kart olarak gelecek.
 * Bu yüzden burada 'uygula/güncelle/gönder' türü bir buton KASITLI olarak yok.
 */

type TargetMode = 'percent' | 'amount'

const targetModeOptions = [
  { value: 'percent', label: 'Kâr Oranı %' },
  { value: 'amount', label: 'Kâr Tutarı ₺' },
]

type WritebackPreviewItem = {
  product_id: string
  product_name: string
  current_price: number
  suggested_price: number
  diff: number
  diff_percent: number
  reason: string
}

type WritebackSkipped = {
  product_id: string
  reason: string
}

type WritebackPreviewResponse = {
  preview: WritebackPreviewItem[]
  count: number
  skipped: WritebackSkipped[]
  skipped_count: number
}

export default function WritebackPreview() {
  const [targetMode, setTargetMode] = useState<TargetMode | ''>('')
  const [targetValue, setTargetValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<WritebackPreviewResponse | null>(null)

  async function handlePreview() {
    setError(null)
    if (!targetMode) {
      setError('Önce hedef türünü seçin (Kâr Oranı % veya Kâr Tutarı ₺).')
      return
    }
    const value = Number(targetValue.replace(',', '.'))
    if (!Number.isFinite(value)) {
      setError('Geçerli bir sayı girin.')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const res = await apiClient.get<WritebackPreviewResponse>('/pricing/writeback-preview', {
        params: { target_mode: targetMode, target_value: value },
      })
      setData(res.data)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 404) {
        setError('Bu önizleme henüz hazır değil — backend ekibi çalışıyor, birazdan tekrar deneyin.')
      } else if (status === 409) {
        setError('Mağaza bağlantısı şu an çözülemiyor. Ayarlar\'dan Trendyol bağlantınızı kontrol edin.')
      } else {
        setError('Önizleme alınamadı. Tekrar deneyin.')
      }
    } finally {
      setLoading(false)
    }
  }

  const columns: DataTableColumn<WritebackPreviewItem>[] = [
    {
      key: 'product_name',
      header: 'Ürün',
      accessor: (p) => (
        <div>
          <p className="font-medium text-text-primary">{p.product_name}</p>
          <p className="text-xs text-text-muted">{p.product_id}</p>
        </div>
      ),
      sortValue: (p) => p.product_name,
    },
    { key: 'current_price', header: 'Mevcut Fiyat', align: 'right', accessor: (p) => formatCurrency(p.current_price), sortValue: (p) => p.current_price },
    {
      key: 'suggested_price',
      header: 'Önerilen Fiyat',
      align: 'right',
      accessor: (p) => formatCurrency(p.suggested_price),
      sortValue: (p) => p.suggested_price,
    },
    {
      key: 'diff',
      header: 'Fark',
      align: 'right',
      accessor: (p) => {
        const isIncrease = p.diff >= 0
        const Icon = isIncrease ? ArrowUpRight : ArrowDownRight
        return (
          <span className={`inline-flex items-center gap-1 ${isIncrease ? 'text-success' : 'text-danger'}`}>
            <Icon className="h-3.5 w-3.5" />
            {formatCurrency(Math.abs(p.diff))} ({Math.abs(p.diff_percent).toFixed(1)}%)
          </span>
        )
      },
      sortValue: (p) => p.diff,
    },
    { key: 'reason', header: 'Gerekçe', accessor: (p) => <span className="text-xs text-text-secondary">{p.reason}</span> },
  ]

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-app-border bg-app-surface p-5 shadow-card">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Fiyat Önizleme</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Hedef kâra göre önerilen fiyatları toplu olarak görün. <strong>Bu sadece bir önizlemedir —
          hiçbir fiyat Trendyol'a veya veritabanına yazılmaz.</strong> Gerçek fiyat güncelleme, ayrı ve
          onay gerektiren bir adım olarak ileride eklenecek.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select
          options={targetModeOptions}
          value={targetMode}
          onChange={(e) => setTargetMode(e.target.value as TargetMode)}
          placeholder="Hedef Türü Seç"
        />
        <Input
          value={targetValue}
          onChange={(e) => setTargetValue(e.target.value)}
          placeholder="Değer"
          className="w-28"
        />
        <Button size="sm" onClick={handlePreview} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Önizle'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">{error}</div>
      )}

      {data && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-text-secondary">
            <strong className="text-text-primary">{data.count}</strong> ürün için öneri hesaplandı
            {data.skipped_count > 0 && (
              <>
                {' '}
                · <strong className="text-text-primary">{data.skipped_count}</strong> ürün atlandı (aşağıda nedenleriyle)
              </>
            )}
            .
          </p>

          {data.count > 0 && (
            <DataTable columns={columns} data={data.preview} rowKey={(p) => p.product_id} pageSize={20} />
          )}

          {data.count === 0 && data.skipped_count === 0 && (
            <div className="rounded-lg border border-app-border bg-app-surface-muted p-8 text-center text-sm text-text-muted">
              Uygun ürün bulunamadı.
            </div>
          )}

          {data.skipped_count > 0 && (
            <div className="rounded-lg border border-app-border bg-app-surface-muted p-3">
              <p className="mb-2 text-sm font-medium text-text-primary">Atlanan ürünler ({data.skipped_count})</p>
              <div className="max-h-48 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-text-muted">
                      <th className="py-1 pr-2">Ürün</th>
                      <th className="py-1">Neden atlandı</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.skipped.map((s, i) => (
                      <tr key={i} className="border-t border-app-border">
                        <td className="py-1 pr-2 font-mono">{s.product_id}</td>
                        <td className="py-1 text-text-secondary">{s.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
