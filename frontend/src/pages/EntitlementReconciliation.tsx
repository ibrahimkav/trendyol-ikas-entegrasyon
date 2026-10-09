import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw, Info } from 'lucide-react'
import apiClient from '../config/api'
import { useToast } from '../context/ToastContext'
import {
  PageHeader,
  Badge,
  Button,
  DataTable,
  DateRangePicker,
  Skeleton,
  ErrorBanner,
  formatCurrency,
  type DataTableColumn,
} from '../components/ui'

// Gerçek endpoint (Pam, Wave3): GET /api/financial/reconciliation?only_flagged=false
// Mağaza Trendyol'a bağlıysa Settlements'tan GERÇEK komisyon çekilir → actual_commission +
// commission_diff dolar, tolerans aşan farklar flagged=true ("hatalı kesinti adayı"). Üst-seviye:
// settlement_available + flagged_count. Satır durumları: reconciled / awaiting_settlement /
// settlement_pending. actual_cargo hâlâ null (OtherFinancials/Cargo-Invoice ayrı iterasyon, Jim).
// İtiraz OTOMATİK gönderilemez (Trendyol API'de endpoint yok) → export/rapor.
// DEV NOTU: dev'de gerçek Trendyol anahtarı yok → settlement_available=false (awaiting) yolu canlı
// görülür; flagged/gerçek-veri yolu mock/enjekte yanıtla doğrulanır (Pam de öyle yaptı).
interface ReconItem {
  order_number: string
  order_id: string
  barcode: string | null
  product_name: string
  desi: number | null
  expected_commission: number
  expected_cargo: number
  actual_commission: number | null
  actual_cargo: number | null
  commission_diff: number | null
  cargo_diff: number | null
  flagged: boolean
  status: string // 'reconciled' | 'awaiting_settlement' | 'settlement_pending'
}

const STATUS_META: Record<string, { label: string; tone: 'success' | 'neutral' | 'info' }> = {
  reconciled: { label: 'Uyumlu', tone: 'success' },
  awaiting_settlement: { label: 'Settlement bekleniyor', tone: 'info' },
  settlement_pending: { label: 'Mağaza bağlı değil', tone: 'neutral' },
}

function diffCell(diff: number | null) {
  if (diff === null) {
    return <Badge tone="neutral">Bekleniyor</Badge>
  }
  if (Math.abs(diff) < 0.005) {
    return <span className="text-text-secondary">{formatCurrency(0)}</span>
  }
  // Fazla kesinti (gerçek > beklenen) = satıcı aleyhine = kırmızı
  const tone = diff > 0 ? 'text-danger' : 'text-success'
  return <span className={`font-medium ${tone}`}>{diff > 0 ? '+' : ''}{formatCurrency(diff)}</span>
}

const rangeDefault = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 14) // API 15-günlük pencere kısıtı (Jim/Pam)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  return { startDate: iso(start), endDate: iso(end) }
}

export default function EntitlementReconciliation() {
  const toast = useToast()
  const [items, setItems] = useState<ReconItem[]>([])
  const [note, setNote] = useState<string | null>(null)
  const [settlementAvailable, setSettlementAvailable] = useState(false)
  const [flaggedCountApi, setFlaggedCountApi] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState(rangeDefault())

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    apiClient
      .get('/financial/reconciliation', {
        params: { only_flagged: false, start_date: dateRange.startDate, end_date: dateRange.endDate },
      })
      .then((res) => {
        setItems(res.data?.items ?? [])
        setNote(res.data?._note ?? null)
        setSettlementAvailable(Boolean(res.data?.settlement_available))
        setFlaggedCountApi(typeof res.data?.flagged_count === 'number' ? res.data.flagged_count : null)
      })
      .catch((err) => setError(err?.userMessage || 'Veriler yüklenemedi. Lütfen tekrar deneyin.'))
      .finally(() => setLoading(false))
  }, [dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const summary = useMemo(() => {
    let totalOvercharge = 0
    let clientFlagged = 0
    let totalExpected = 0
    for (const it of items) {
      totalExpected += (it.expected_commission || 0) + (it.expected_cargo || 0)
      if (it.flagged) clientFlagged += 1
      const cd = it.commission_diff ?? 0
      const gd = it.cargo_diff ?? 0
      if (cd > 0) totalOvercharge += cd
      if (gd > 0) totalOvercharge += gd
    }
    // flagged_count backend'den gelirse onu kullan, yoksa satırlardan türet.
    const flaggedCount = flaggedCountApi ?? clientFlagged
    return { totalOvercharge, flaggedCount, totalExpected }
  }, [items, flaggedCountApi])

  function handleDispute(item: ReconItem) {
    // Trendyol API'de otomatik itiraz endpoint'i yok (Jim) → rapor/export. Backend yazma da yok.
    toast({ type: 'info', message: `${item.order_number} için itiraz çıktısı özelliği yakında (TODO — otomatik itiraz Trendyol API'de yok, export olarak gelecek).` })
  }

  const columns: DataTableColumn<ReconItem>[] = [
    {
      key: 'order',
      header: 'Sipariş / Ürün',
      accessor: (r) => (
        <div>
          <p className="font-medium text-text-primary">{r.order_number}</p>
          <p className="text-xs text-text-muted">{r.product_name}{r.barcode ? ` · ${r.barcode}` : ''}</p>
        </div>
      ),
      sortValue: (r) => r.order_number,
    },
    { key: 'desi', header: 'Desi', align: 'right', accessor: (r) => (r.desi != null ? r.desi : '—'), sortValue: (r) => r.desi ?? 0 },
    { key: 'exp_comm', header: 'Beklenen Kom.', align: 'right', accessor: (r) => formatCurrency(r.expected_commission), sortValue: (r) => r.expected_commission },
    { key: 'act_comm', header: 'Gerçekleşen Kom.', align: 'right', accessor: (r) => (r.actual_commission != null ? formatCurrency(r.actual_commission) : <Badge tone="neutral">Bekleniyor</Badge>) },
    { key: 'comm_diff', header: 'Fark (Kom.)', align: 'right', accessor: (r) => diffCell(r.commission_diff) },
    { key: 'exp_cargo', header: 'Beklenen Kargo', align: 'right', accessor: (r) => formatCurrency(r.expected_cargo), sortValue: (r) => r.expected_cargo },
    { key: 'act_cargo', header: 'Gerçekleşen Kargo', align: 'right', accessor: (r) => (r.actual_cargo != null ? formatCurrency(r.actual_cargo) : <Badge tone="neutral">Bekleniyor</Badge>) },
    { key: 'cargo_diff', header: 'Fark (Kargo)', align: 'right', accessor: (r) => diffCell(r.cargo_diff) },
    {
      key: 'status',
      header: 'Durum',
      accessor: (r) => {
        if (r.flagged) return <Badge tone="danger">Fazla kesinti</Badge>
        const meta = STATUS_META[r.status] ?? { label: r.status, tone: 'neutral' as const }
        return <Badge tone={meta.tone}>{meta.label}</Badge>
      },
    },
    {
      key: 'action',
      header: '',
      align: 'right',
      accessor: (r) => (
        <Button size="sm" variant="outline" disabled={!r.flagged} onClick={() => handleDispute(r)}>
          İtiraz Aç
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hakediş & Desi Kontrolü"
        actions={
          <div className="flex items-center gap-2">
            <DateRangePicker startDate={dateRange.startDate} endDate={dateRange.endDate} onChange={setDateRange} />
            <Button variant="outline" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={fetchData}>
              Verileri Yenile
            </Button>
          </div>
        }
      />

      {/* Özet KPI şeridi */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
          <p className="text-caption uppercase tracking-wide text-text-secondary">Toplam Fazla Kesinti</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-danger">{formatCurrency(summary.totalOvercharge)}</p>
        </div>
        <div className="rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
          <p className="text-caption uppercase tracking-wide text-text-secondary">Hatalı Kesinti Adayı</p>
          <p className={`mt-1 text-xl font-bold tabular-nums ${summary.flaggedCount > 0 ? 'text-danger' : 'text-text-primary'}`}>
            {summary.flaggedCount}
          </p>
        </div>
        <div className="rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
          <p className="text-caption uppercase tracking-wide text-text-secondary">Toplam Beklenen Kesinti</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-text-primary">{formatCurrency(summary.totalExpected)}</p>
        </div>
      </div>

      {!settlementAvailable && !error && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-info bg-info-soft px-4 py-3 text-sm text-info">
          <Info className="h-4 w-4 shrink-0" />
          Gerçekleşen (settlement) verisi yok — mağaza Trendyol'a bağlı değil ya da bu dönemde settlement kesilmemiş. Şu an tahmini taraf gösteriliyor; gerçek komisyon farkları (hatalı kesinti tespiti) Ayarlar → Trendyol API'den mağaza bağlanınca dolar.
        </div>
      )}

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={items}
          rowKey={(r) => `${r.order_id}-${r.barcode ?? ''}`}
          pageSize={50}
          emptyMessage="Seçili dönemde mutabakat kaydı bulunamadı."
          rowClassName={(r) => (r.flagged ? 'bg-danger-soft/60' : undefined)}
        />
      )}

      {note && <p className="text-xs text-text-muted">{note}</p>}
    </div>
  )
}
