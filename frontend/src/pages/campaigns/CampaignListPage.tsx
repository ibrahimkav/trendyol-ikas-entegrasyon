import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useToast } from '../../context/ToastContext'
import {
  PageHeader,
  Badge,
  Button,
  DataTable,
  ProfitBadge,
  formatCurrency,
  type DataTableColumn,
} from '../../components/ui'
import CampaignTabs from './CampaignTabs'

// Avantajlı Teklifler + Sepet Kampanyaları ortak liste kabuğu. Bunlar Trendyol'un DAVET ettiği
// kampanyalar (satıcının kendi CRUD kampanyaları değil) → gerçek veri kaynağı henüz YOK. w2c-pam
// kâr-etkisi endpoint'i gelene kadar örnek (mock) satırlarla + isFallback banner ile gösteriliyor
// (god: guess-with-fallback). Kolon/kart düzeni ground-truth'ta yoktu (Jim orta güven).
export interface CampaignRow {
  id: string
  name: string
  discountLabel: string
  dateRange: string
  currentProfit: number
  campaignProfit: number
  campaignMarginPct: number
}

interface CampaignListPageProps {
  title: string
  breadcrumbLabel: string
  emptyMessage: string
  mockRows: CampaignRow[]
}

export default function CampaignListPage({ title, breadcrumbLabel, emptyMessage, mockRows }: CampaignListPageProps) {
  const toast = useToast()
  // Not: gerçek liste endpoint'i olmadığından doğrudan mock kullanıyoruz (isFallback hep true).
  const [rows] = useState<CampaignRow[]>(mockRows)

  function handleJoin(row: CampaignRow) {
    toast({ type: 'info', message: `"${row.name}" kampanyasına katılma backend entegrasyonu henüz eklenmedi (TODO).` })
  }

  const columns: DataTableColumn<CampaignRow>[] = [
    { key: 'name', header: 'Kampanya', accessor: (r) => <span className="font-medium text-text-primary">{r.name}</span>, sortValue: (r) => r.name },
    { key: 'discount', header: 'İndirim', accessor: (r) => r.discountLabel },
    { key: 'dates', header: 'Tarih', accessor: (r) => r.dateRange },
    { key: 'current', header: 'Mevcut Kâr', align: 'right', accessor: (r) => formatCurrency(r.currentProfit), sortValue: (r) => r.currentProfit },
    {
      key: 'campaign',
      header: 'Katılırsan Tahmini Kâr',
      align: 'right',
      accessor: (r) => <ProfitBadge amount={r.campaignProfit} percent={r.campaignMarginPct} />,
      sortValue: (r) => r.campaignProfit,
    },
    {
      key: 'action',
      header: '',
      align: 'right',
      accessor: (r) => (
        <Button size="sm" variant="primary" onClick={() => handleJoin(r)}>
          Katıl
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={title} breadcrumbs={[{ label: 'Kampanya' }, { label: breadcrumbLabel }]} />
      <CampaignTabs />

      <div className="flex items-center gap-2 rounded-lg border border-warning bg-warning-soft px-4 py-3 text-sm text-warning">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        Trendyol davetli kampanya verisi ve kâr-etkisi hesabı backend'e henüz bağlı değil — örnek (mock) veri gösteriliyor.
      </div>

      <DataTable columns={columns} data={rows} rowKey={(r) => r.id} pageSize={20} emptyMessage={emptyMessage} filterSlot={<Badge tone="neutral">örnek veri</Badge>} />
    </div>
  )
}
