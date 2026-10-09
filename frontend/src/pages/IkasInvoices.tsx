import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { AlertTriangle, FileSpreadsheet, Info, RefreshCw, Trash2, Upload, X } from 'lucide-react'
import { useToast } from '../context/ToastContext'
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  ErrorBanner,
  Input,
  PageHeader,
  SegmentedControl,
  Skeleton,
  formatCurrency,
  type BadgeTone,
  type DataTableColumn,
} from '../components/ui'
import {
  deleteIkasOrder,
  fetchIkasOrder,
  fetchIkasOrders,
  fetchInvoiceSettings,
  importIkasFile,
  saveInvoiceSettings,
  updateIkasOrder,
  type Billing,
  type IkasOrderDetail,
  type IkasOrderStatus,
  type IkasOrderSummary,
  type IkasStatusFilter,
  type ImportResult,
  type InvoiceSettings,
  type StatusCounts,
} from '../lib/ikasInvoiceApi'

/**
 * ikas Faturaları `/ikas-invoices` — ikas'tan dışa aktarılan sipariş dosyası (XLSX/CSV)
 * yüklenir, her sipariş için fatura taslağı (KDV ayrıştırılmış) gösterilir, eksik fatura
 * bilgileri elle tamamlanır. Fatura kesme (Trendyol E-Faturam bağlantısı) 2. aşamada.
 */

const STATUS_META: Record<IkasOrderStatus, { label: string; tone: BadgeTone }> = {
  ready: { label: 'Faturaya hazır', tone: 'success' },
  needs_info: { label: 'Eksik bilgi', tone: 'warning' },
  invoiced: { label: 'Faturalandı', tone: 'info' },
  error: { label: 'Hata', tone: 'danger' },
}

const BILLING_FORM: { key: keyof Billing; label: string; hint?: string }[] = [
  { key: 'full_name', label: 'Ad Soyad' },
  { key: 'identity_number', label: 'TC Kimlik No', hint: 'Bireysel fatura — 11 hane' },
  { key: 'company_name', label: 'Firma Ünvanı', hint: 'Doluysa kurumsal fatura kesilir' },
  { key: 'tax_number', label: 'Vergi No (VKN)', hint: 'Kurumsal — 10 hane' },
  { key: 'tax_office', label: 'Vergi Dairesi' },
  { key: 'email', label: 'E-posta' },
  { key: 'phone', label: 'Telefon' },
  { key: 'address', label: 'Adres' },
  { key: 'district', label: 'İlçe' },
  { key: 'city', label: 'İl' },
]

const FIELD_LABELS: Record<string, string> = {
  order_number: 'Sipariş No',
  product_name: 'Ürün Adı',
}

export default function IkasInvoices() {
  const toast = useToast()
  const fileInput = useRef<HTMLInputElement>(null)
  const [filter, setFilter] = useState<IkasStatusFilter>('all')
  const [items, setItems] = useState<IkasOrderSummary[]>([])
  const [counts, setCounts] = useState<StatusCounts>({ all: 0, ready: 0, needs_info: 0, invoiced: 0, error: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [settings, setSettings] = useState<InvoiceSettings | null>(null)
  const [vatForm, setVatForm] = useState({ product: '10', shipping: '20' })
  const [savingVat, setSavingVat] = useState(false)
  const [detail, setDetail] = useState<IkasOrderDetail | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchIkasOrders(filter)
      .then((res) => {
        setItems(res.items)
        setCounts(res.counts)
      })
      .catch((err) => setError(err?.userMessage || 'Siparişler yüklenemedi.'))
      .finally(() => setLoading(false))
  }, [filter])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    fetchInvoiceSettings()
      .then((s) => {
        setSettings(s)
        setVatForm({ product: String(s.product_vat_rate), shipping: String(s.shipping_vat_rate) })
      })
      .catch(() => undefined)
  }, [])

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      const result = await importIkasFile(file)
      setImportResult(result)
      toast({ type: 'success', message: `${result.orders_in_file} sipariş içe aktarıldı (${result.created} yeni, ${result.updated} güncellendi).` })
      load()
    } catch (err: any) {
      const detailMsg = err?.response?.data?.detail
      toast({ type: 'error', message: typeof detailMsg === 'object' ? detailMsg.message : err?.userMessage || 'Dosya yüklenemedi.' })
    } finally {
      setUploading(false)
    }
  }

  async function handleSaveVat() {
    const product = Number(vatForm.product.replace(',', '.'))
    const shipping = Number(vatForm.shipping.replace(',', '.'))
    if (!Number.isFinite(product) || !Number.isFinite(shipping) || product < 0 || shipping < 0 || product > 100 || shipping > 100) {
      toast({ type: 'error', message: 'KDV oranları 0–100 arasında olmalı.' })
      return
    }
    setSavingVat(true)
    try {
      setSettings(await saveInvoiceSettings({ product_vat_rate: product, shipping_vat_rate: shipping }))
      toast({ type: 'success', message: 'KDV oranları kaydedildi.' })
      load()
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Kaydedilemedi.' })
    } finally {
      setSavingVat(false)
    }
  }

  async function openDetail(orderNumber: string) {
    try {
      setDetail(await fetchIkasOrder(orderNumber))
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Sipariş açılamadı.' })
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteIkasOrder(deleteTarget)
      toast({ type: 'success', message: `${deleteTarget} silindi.` })
      setDeleteTarget(null)
      load()
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Silinemedi.' })
    } finally {
      setDeleting(false)
    }
  }

  const columns: DataTableColumn<IkasOrderSummary>[] = [
    {
      key: 'order',
      header: 'Sipariş',
      accessor: (r) => (
        <div>
          <p className="font-medium text-text-primary">{r.order_number}</p>
          <p className="text-xs text-text-muted">{r.order_date || '—'}</p>
        </div>
      ),
      sortValue: (r) => r.order_number,
    },
    {
      key: 'customer',
      header: 'Müşteri',
      accessor: (r) => (
        <div>
          <p className="text-text-primary">{r.customer || <span className="text-danger">İsim yok</span>}</p>
          <p className="text-xs text-text-muted">
            {r.buyer_type === 'kurumsal' ? 'Kurumsal' : 'Bireysel'}
            {r.city ? ` · ${r.city}` : ''}
            {r.edited ? ' · elle düzeltildi' : ''}
          </p>
        </div>
      ),
      sortValue: (r) => r.customer,
    },
    { key: 'gross', header: 'Tutar (KDV dahil)', align: 'right', accessor: (r) => formatCurrency(r.gross_total), sortValue: (r) => r.gross_total },
    { key: 'vat', header: 'KDV', align: 'right', accessor: (r) => formatCurrency(r.vat_total), sortValue: (r) => r.vat_total },
    {
      key: 'status',
      header: 'Durum',
      accessor: (r) => (
        <div className="flex flex-col items-start gap-1">
          <Badge tone={STATUS_META[r.status].tone}>{STATUS_META[r.status].label}</Badge>
          {r.errors[0] && <span className="text-xs text-danger">{r.errors[0]}{r.errors.length > 1 ? ` (+${r.errors.length - 1})` : ''}</span>}
          {!r.errors.length && r.warnings[0] && <span className="text-xs text-warning">{r.warnings[0]}</span>}
        </div>
      ),
      sortValue: (r) => r.status,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      accessor: (r) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="outline" onClick={() => openDetail(r.order_number)}>
            {r.status === 'needs_info' ? 'Tamamla' : 'Detay'}
          </Button>
          {r.status !== 'invoiced' && (
            <Button size="sm" variant="ghost" aria-label="Sil" onClick={() => setDeleteTarget(r.order_number)}>
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="ikas Faturaları"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>
              Yenile
            </Button>
            <Button leftIcon={<Upload className="h-4 w-4" />} onClick={() => fileInput.current?.click()} disabled={uploading}>
              {uploading ? 'Yükleniyor...' : 'ikas Dosyası Yükle'}
            </Button>
            <input ref={fileInput} type="file" accept=".xlsx,.csv" className="hidden" onChange={handleFile} />
          </div>
        }
      />

      <div className="flex items-start gap-2 rounded-lg border border-info bg-info-soft px-4 py-3 text-sm text-info">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          ikas panelinde <b>Siparişler → Dışa Aktar</b> ile siparişleri XLSX veya CSV olarak indirip buraya yükleyin. Aynı
          dosyayı tekrar yüklemek güvenlidir: siparişler güncellenir, elle düzelttiğiniz bilgiler korunur.
          {settings && !settings.efaturam_connected && (
            <> Fatura kesme, Trendyol E-Faturam bağlantısı kurulunca açılacak — şimdilik taslakları kontrol edebilirsiniz.</>
          )}
        </div>
      </div>

      {importResult && <ImportSummary result={importResult} onClose={() => setImportResult(null)} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(
            [
              ['Toplam', counts.all, 'text-text-primary'],
              ['Faturaya hazır', counts.ready, 'text-success'],
              ['Eksik bilgi', counts.needs_info, counts.needs_info ? 'text-warning' : 'text-text-primary'],
              ['Faturalandı', counts.invoiced, 'text-text-primary'],
            ] as const
          ).map(([label, value, tone]) => (
            <div key={label} className="rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
              <p className="text-caption uppercase tracking-wide text-text-secondary">{label}</p>
              <p className={`mt-1 text-xl font-bold tabular-nums ${tone}`}>{value}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
          <div className="w-28">
            <Input id="vat-product" label="Ürün KDV %" inputMode="decimal" value={vatForm.product} onChange={(e) => setVatForm((f) => ({ ...f, product: e.target.value }))} />
          </div>
          <div className="w-28">
            <Input id="vat-shipping" label="Kargo KDV %" inputMode="decimal" value={vatForm.shipping} onChange={(e) => setVatForm((f) => ({ ...f, shipping: e.target.value }))} />
          </div>
          <Button variant="outline" onClick={handleSaveVat} disabled={savingVat}>
            {savingVat ? 'Kaydediliyor...' : 'Kaydet'}
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={items}
          rowKey={(r) => r.order_number}
          pageSize={50}
          filterSlot={
            <SegmentedControl<IkasStatusFilter>
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: `Tümü (${counts.all})` },
                { value: 'ready', label: `Hazır (${counts.ready})` },
                { value: 'needs_info', label: `Eksik (${counts.needs_info})` },
                { value: 'invoiced', label: `Faturalandı (${counts.invoiced})` },
              ]}
            />
          }
          emptyMessage={counts.all === 0 ? 'Henüz sipariş yok — ikas dosyası yükleyin.' : 'Bu filtrede sipariş yok.'}
        />
      )}

      {detail && (
        <OrderDetailDrawer
          detail={detail}
          onClose={() => setDetail(null)}
          onSaved={(updated) => {
            setDetail(updated)
            load()
          }}
        />
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Siparişi sil"
        description={`${deleteTarget} listeden silinsin mi? Dosyayı tekrar yüklerseniz geri gelir.`}
        confirmLabel="Sil"
        confirmVariant="danger"
        loading={deleting}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </div>
  )
}

function ImportSummary({ result, onClose }: { result: ImportResult; onClose: () => void }) {
  const missing = result.missing_fields.filter((f) => f !== 'order_number')
  return (
    <div className="rounded-lg border border-app-border bg-app-surface p-4 shadow-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-brand" />
          <p className="font-medium text-text-primary">
            {result.rows_in_file} satırdan {result.orders_in_file} sipariş okundu — {result.created} yeni, {result.updated} güncellendi
            {result.skipped_invoiced ? `, ${result.skipped_invoiced} faturalanmış sipariş atlandı` : ''}
          </p>
        </div>
        <button type="button" onClick={onClose} className="text-text-muted hover:text-text-primary" aria-label="Kapat">
          <X className="h-4 w-4" />
        </button>
      </div>
      {missing.length > 0 && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-danger">
          <AlertTriangle className="h-4 w-4" />
          Dosyada bulunamayan zorunlu kolon: {missing.map((f) => FIELD_LABELS[f] ?? f).join(', ')}
        </p>
      )}
      {result.ignored_columns.length > 0 && (
        <p className="mt-2 text-xs text-text-muted">
          Kullanılmayan kolonlar: {result.ignored_columns.join(', ')}
        </p>
      )}
    </div>
  )
}

function OrderDetailDrawer({
  detail,
  onClose,
  onSaved,
}: {
  detail: IkasOrderDetail
  onClose: () => void
  onSaved: (d: IkasOrderDetail) => void
}) {
  const toast = useToast()
  const { draft } = detail
  const locked = detail.status === 'invoiced'
  const [form, setForm] = useState<Billing>(draft.billing)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setForm(draft.billing)
  }, [draft.billing])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function save() {
    // Sadece değişen alanlar gönderilir — değişmeyenler dosyadaki değerde kalır
    const changed: Partial<Billing> = {}
    for (const { key } of BILLING_FORM) {
      if ((form[key] ?? '') !== (draft.billing[key] ?? '')) changed[key] = form[key] ?? ''
    }
    if (!Object.keys(changed).length) {
      toast({ type: 'info', message: 'Değişiklik yok.' })
      return
    }
    setSaving(true)
    try {
      await updateIkasOrder(detail.order_number, changed)
      onSaved(await fetchIkasOrder(detail.order_number))
      toast({ type: 'success', message: 'Fatura bilgileri kaydedildi.' })
    } catch (err: any) {
      toast({ type: 'error', message: err?.userMessage || 'Kaydedilemedi.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Sipariş ${detail.order_number}`}
        className="h-full w-full max-w-2xl overflow-y-auto bg-app-surface p-6 shadow-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Sipariş {detail.order_number}</h2>
            <p className="text-sm text-text-secondary">
              {detail.order_date || 'Tarih yok'} · {draft.buyer_type === 'kurumsal' ? 'Kurumsal' : 'Bireysel'} fatura ·{' '}
              {draft.buyer_type === 'kurumsal' ? 'VKN' : 'TCKN'} {draft.tax_id || '—'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={STATUS_META[detail.status].tone}>{STATUS_META[detail.status].label}</Badge>
            <button type="button" onClick={onClose} className="text-text-muted hover:text-text-primary" aria-label="Kapat">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {(draft.errors.length > 0 || draft.warnings.length > 0) && (
          <ul className="mt-4 flex flex-col gap-1 rounded-md border border-app-border bg-app-surface-muted p-3 text-sm">
            {draft.errors.map((e) => (
              <li key={e} className="text-danger">• {e}</li>
            ))}
            {draft.warnings.map((w) => (
              <li key={w} className="text-warning">• {w}</li>
            ))}
          </ul>
        )}

        <h3 className="mt-6 text-sm font-semibold text-text-primary">Fatura Bilgileri</h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {BILLING_FORM.map(({ key, label, hint }) => (
            <div key={key} className={key === 'address' ? 'sm:col-span-2' : undefined}>
              <Input
                id={`billing-${key}`}
                label={label + (detail.overrides[key] ? ' (düzeltildi)' : '')}
                hint={hint}
                value={form[key] ?? ''}
                disabled={locked}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        {!locked && (
          <div className="mt-3 flex justify-end">
            <Button onClick={save} disabled={saving}>
              {saving ? 'Kaydediliyor...' : 'Bilgileri Kaydet'}
            </Button>
          </div>
        )}

        <h3 className="mt-6 text-sm font-semibold text-text-primary">Fatura Taslağı</h3>
        <div className="mt-3 overflow-x-auto rounded-md border border-app-border">
          <table className="w-full text-sm">
            <thead className="bg-app-surface-muted text-xs text-text-secondary">
              <tr>
                <th className="px-3 py-2 text-left">Ürün</th>
                <th className="px-3 py-2 text-right">Adet</th>
                <th className="px-3 py-2 text-right">KDV</th>
                <th className="px-3 py-2 text-right">Matrah</th>
                <th className="px-3 py-2 text-right">Toplam</th>
              </tr>
            </thead>
            <tbody>
              {draft.lines.map((l, i) => (
                <tr key={i} className="border-t border-app-border">
                  <td className="px-3 py-2">
                    <p className="text-text-primary">{l.name}</p>
                    {(l.barcode || l.sku) && <p className="text-xs text-text-muted">{l.barcode || l.sku}</p>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{l.quantity}</td>
                  <td className="px-3 py-2 text-right tabular-nums">%{l.vat_rate}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(l.net_amount)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(l.gross_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="mt-3 ml-auto grid w-full max-w-xs grid-cols-2 gap-y-1 text-sm">
          <dt className="text-text-secondary">Matrah</dt>
          <dd className="text-right tabular-nums">{formatCurrency(draft.totals.net)}</dd>
          {draft.totals.vat_breakdown.map((b) => (
            <div key={b.rate} className="contents">
              <dt className="text-text-secondary">KDV %{b.rate}</dt>
              <dd className="text-right tabular-nums">{formatCurrency(b.vat)}</dd>
            </div>
          ))}
          {draft.totals.discount_applied > 0 && (
            <>
              <dt className="text-text-secondary">Dağıtılan indirim</dt>
              <dd className="text-right tabular-nums">-{formatCurrency(draft.totals.discount_applied)}</dd>
            </>
          )}
          <dt className="font-semibold text-text-primary">Genel Toplam</dt>
          <dd className="text-right font-semibold tabular-nums">{formatCurrency(draft.totals.gross)}</dd>
        </dl>

        <div className="mt-6 flex items-center justify-end gap-2 border-t border-app-border pt-4">
          <span className="text-xs text-text-muted">E-Faturam bağlantısı kurulunca aktif olacak</span>
          <Button disabled>Fatura Kes</Button>
        </div>
      </div>
    </div>
  )
}
