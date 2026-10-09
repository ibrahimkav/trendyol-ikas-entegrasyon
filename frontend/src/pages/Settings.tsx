import { useEffect, useState, type FormEvent } from 'react'
import { CheckCircle2, Link2Off, Loader2 } from 'lucide-react'
import { Button, Input, PageHeader } from '../components/ui'
import { useToast } from '../context/ToastContext'
import {
  connectCredential,
  disconnectCredential,
  fetchCredentials,
  fetchThresholds,
  resetThreshold,
  saveThreshold,
  type Platform,
  type StoreCredential,
  type ThresholdField,
  type Thresholds,
} from '../lib/settingsApi'

/**
 * Ayarlar `/settings` — melontik-screens.md §5: sol alt-sekme + sağ form.
 * Trendyol/Hepsiburada API sekmeleri Pam'in store-connect endpoint'lerine bağlı (gerçek).
 * Diğer sekmeler backend'de henüz karşılığı olmadığı için "yakında" placeholder (Wave2c).
 */

type TabId =
  | 'account'
  | 'trendyol'
  | 'hepsiburada'
  | 'thresholds'
  | 'general'
  | 'cargo'
  | 'operation'
  | 'profit-list'
  | 'margin-coloring'
  | 'email-notif'
  | 'bulk'

const TABS: { id: TabId; label: string; ready?: boolean }[] = [
  { id: 'account', label: 'Hesap Ayarları' },
  { id: 'trendyol', label: 'Trendyol API Bilgileri', ready: true },
  { id: 'hepsiburada', label: 'Hepsiburada API Bilgileri', ready: true },
  { id: 'thresholds', label: 'Uyarı Eşikleri', ready: true },
  { id: 'general', label: 'Genel Ayarlar' },
  { id: 'cargo', label: 'Kargo Ayarları' },
  { id: 'operation', label: 'Operasyon Ayarları' },
  { id: 'profit-list', label: 'Ürün Kârlılık Listesi' },
  { id: 'margin-coloring', label: 'Kâr Marjı Renklendirme' },
  { id: 'email-notif', label: 'Eposta Bildirim Ayarları' },
  { id: 'bulk', label: 'Toplu İşlemler' },
]

export default function Settings() {
  const [tab, setTab] = useState<TabId>('trendyol')
  const [credentials, setCredentials] = useState<StoreCredential[]>([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const loadCredentials = async () => {
    setLoading(true)
    try {
      setCredentials(await fetchCredentials())
    } catch {
      // no-active-store veya ağ hatası — form yine de gösterilir, kaydedince tekrar denenir
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCredentials()
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Ayarlar" />
      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="flex shrink-0 flex-col gap-1 lg:w-64">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-2 text-left text-sm transition-colors ${
                tab === t.id ? 'bg-brand-soft font-medium text-brand' : 'text-text-secondary hover:bg-app-surface-muted'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0 flex-1">
          {tab === 'trendyol' && (
            <CredentialForm
              platform="trendyol"
              needsSupplierId
              credential={credentials.find((c) => c.platform === 'trendyol')}
              loading={loading}
              onSaved={loadCredentials}
              toast={toast}
            />
          )}
          {tab === 'hepsiburada' && (
            <CredentialForm
              platform="hepsiburada"
              credential={credentials.find((c) => c.platform === 'hepsiburada')}
              loading={loading}
              onSaved={loadCredentials}
              toast={toast}
            />
          )}
          {tab === 'thresholds' && <ThresholdsSettings />}
          {tab !== 'trendyol' && tab !== 'hepsiburada' && tab !== 'thresholds' && (
            <div className="rounded-lg border border-app-border bg-app-surface p-10 text-center text-sm text-text-muted shadow-card">
              Bu ayar bölümü yakında eklenecek.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function CredentialForm({
  platform,
  needsSupplierId,
  credential,
  loading,
  onSaved,
  toast,
}: {
  platform: Platform
  needsSupplierId?: boolean
  credential?: StoreCredential
  loading: boolean
  onSaved: () => void
  toast: ReturnType<typeof useToast>
}) {
  const [supplierId, setSupplierId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const platformLabel = platform === 'trendyol' ? 'Trendyol' : 'Hepsiburada'
  const connected = credential?.is_connected

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (needsSupplierId && !supplierId.trim()) {
      setError('Satıcı ID (Supplier ID) zorunludur.')
      return
    }
    setSaving(true)
    try {
      await connectCredential({
        platform,
        supplier_id: needsSupplierId ? supplierId.trim() : undefined,
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim(),
      })
      toast({ type: 'success', message: `${platformLabel} API bilgileri kaydedildi.` })
      setApiKey('')
      setApiSecret('')
      onSaved()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Kaydedilemedi, bilgileri kontrol edip tekrar deneyin.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDisconnect() {
    setSaving(true)
    try {
      await disconnectCredential(platform)
      toast({ type: 'success', message: `${platformLabel} bağlantısı kaldırıldı.` })
      onSaved()
    } catch {
      toast({ type: 'error', message: 'Bağlantı kaldırılamadı.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-app-border bg-app-surface p-6 shadow-card">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-text-primary">{platformLabel} API Bilgileri</h2>
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-text-muted" />
        ) : connected ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-xs font-medium text-success">
            <CheckCircle2 className="h-3.5 w-3.5" /> Bağlı
          </span>
        ) : (
          <span className="rounded-full bg-app-surface-muted px-2.5 py-1 text-xs font-medium text-text-secondary">Bağlı değil</span>
        )}
      </div>

      {connected && (
        <div className="mb-4 rounded-md bg-app-surface-muted px-3 py-2 text-xs text-text-secondary">
          Kayıtlı anahtar: <strong className="tabular-nums text-text-primary">{credential?.api_key_preview}</strong>
          {credential?.supplier_id && <> · Satıcı ID: {credential.supplier_id}</>}
        </div>
      )}

      <p className="mb-4 text-sm text-text-secondary">
        {platformLabel} entegrasyon anahtarlarınızı girin. Gerçek satış/kâr verisi bu bağlantı üzerinden akar. Anahtarlarınız
        şifreli saklanır ve bir daha ham olarak gösterilmez.
      </p>

      <form onSubmit={handleSubmit} className="flex max-w-md flex-col gap-4">
        {needsSupplierId && (
          <Input label="Satıcı ID (Supplier ID)" value={supplierId} onChange={(e) => setSupplierId(e.target.value)} placeholder="123456" />
        )}
        <Input
          label="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={connected ? 'Değiştirmek için yeni anahtar girin' : 'API anahtarınız'}
          autoComplete="off"
        />
        <Input
          label="API Secret"
          type="password"
          value={apiSecret}
          onChange={(e) => setApiSecret(e.target.value)}
          placeholder={connected ? 'Değiştirmek için yeni secret girin' : 'API secret'}
          autoComplete="off"
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving || !apiKey || !apiSecret}>
            {saving ? 'Kaydediliyor…' : connected ? 'Güncelle' : 'Bağla'}
          </Button>
          {connected && (
            <Button type="button" variant="outline" leftIcon={<Link2Off className="h-4 w-4" />} onClick={handleDisconnect} disabled={saving}>
              Bağlantıyı Kaldır
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}

// w3-thresholds-ui — hive/docs/thresholds-spec.md: teknik alan adları (low_stock_sales_ratio vb.)
// asla ekranda gösterilmez, satıcı dilinde açıklanır. low_stock_sales_ratio backend'de 0.01-1.0
// arası ORAN olarak saklanır ama burada yüzde (1-100) olarak gösterilir/girilir (toDisplay/toStored).
type ThresholdFieldDef = {
  field: ThresholdField
  label: string
  unit: string
  displayMin: number
  displayMax: number
  /** hive/docs/thresholds-spec.md § "Ayarlanabilir hale getirilenler" tablosundaki varsayılan (display birimde). */
  defaultDisplay: number
  toDisplay: (stored: number) => number
  toStored: (display: number) => number
  helpText: string
  effectText: string
  boundsText: string
}

const THRESHOLD_FIELD_DEFS: ThresholdFieldDef[] = [
  {
    field: 'margin_warning_threshold',
    label: 'Düşük kâr marjı uyarı eşiği',
    unit: '%',
    displayMin: 0,
    displayMax: 100,
    defaultDisplay: 15,
    toDisplay: (v) => v,
    toStored: (v) => v,
    helpText:
      'Kâr marjı bu yüzdenin altına düşen ürünler Kâr Marjı Listesi\'nde "düşük marj" olarak işaretlenir.',
    effectText: 'Kâr Marjı Listesi\'ndeki düşük-marj işaretleri bu eşiğe göre güncellenecek.',
    boundsText: 'Kâr marjı eşiği %0 ile %100 arasında olmalı.',
  },
  {
    field: 'low_stock_floor',
    label: 'Minimum stok tabanı',
    unit: 'adet',
    displayMin: 0,
    displayMax: 1000,
    defaultDisplay: 5,
    toDisplay: (v) => v,
    toStored: (v) => v,
    helpText:
      'Satış hızından bağımsız olarak, stoğu bu adedin altına düşen her ürün Envanter ekranında "az stok" uyarısı alır.',
    effectText: 'Envanter ekranındaki az-stok uyarıları bu tabana göre güncellenecek.',
    boundsText: 'Stok tabanı 0 ile 1000 adet arasında olmalı.',
  },
  {
    field: 'low_stock_sales_ratio',
    label: 'Satış hızına göre ek stok payı',
    unit: '%',
    displayMin: 1,
    displayMax: 100,
    defaultDisplay: 15,
    toDisplay: (v) => Math.round(v * 10000) / 100,
    toStored: (v) => v / 100,
    helpText:
      'Çok satan ürünlerde taban tek başına yetersiz kalabilir — az-stok eşiği, ürünün satış adedinin bu yüzdesi kadar da olabilir (taban ile bu ikisinden BÜYÜK olan uygulanır).',
    effectText: 'Envanter ekranındaki az-stok uyarıları bu orana göre güncellenecek.',
    boundsText: 'Bu oran %1 ile %100 arasında olmalı.',
  },
]

function ThresholdsSettings() {
  const [data, setData] = useState<Thresholds | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  async function load() {
    setLoading(true)
    setLoadError(false)
    try {
      setData(await fetchThresholds())
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return <div className="h-48 animate-pulse rounded-lg border border-app-border bg-app-surface-muted" />
  }
  if (loadError || !data) {
    return (
      <div className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
        Uyarı eşikleri yüklenemedi. Sayfayı yenileyip tekrar deneyin.
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-app-border bg-app-surface p-6 shadow-card">
      <h2 className="mb-1 text-base font-semibold text-text-primary">Uyarı Eşikleri</h2>
      <p className="mb-4 text-sm text-text-secondary">
        Kâr marjı ve stok uyarılarının ne zaman tetikleneceğini kendi işinize göre ayarlayın. Ayarlamadığınız
        değerler varsayılan olarak kalır ve mağazanızda geçerli olur.
      </p>
      <div>
        {THRESHOLD_FIELD_DEFS.map((def) => (
          <ThresholdFieldRow
            key={def.field}
            def={def}
            current={data[def.field]}
            isCustomized={data.is_customized[def.field]}
            onSaved={setData}
          />
        ))}
      </div>
    </div>
  )
}

function ThresholdFieldRow({
  def,
  current,
  isCustomized,
  onSaved,
}: {
  def: ThresholdFieldDef
  current: number
  isCustomized: boolean
  onSaved: (t: Thresholds) => void
}) {
  const [value, setValue] = useState(String(def.toDisplay(current)))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedMsg, setSavedMsg] = useState<string | null>(null)

  useEffect(() => {
    // Sadece input değerini senkronize et — error/savedMsg'i TEMİZLEME: persist() başarılı olunca
    // current de değişir, bu effect tekrar çalışır, ama az önce set edilen başarı mesajını hemen
    // silmemeli (aksi halde kullanıcı 'Kaydedildi' mesajını hiç göremez).
    setValue(String(def.toDisplay(current)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current])

  function parseInput(): number | null {
    const num = Number(value.replace(',', '.'))
    if (!Number.isFinite(num)) return null
    return num
  }

  async function run(action: () => Promise<Thresholds>, successMsg: string) {
    setError(null)
    setSavedMsg(null)
    setSaving(true)
    try {
      const updated = await action()
      onSaved(updated)
      setSavedMsg(successMsg)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 404) {
        setError('Bu ayar henüz hazır değil — backend ekibi çalışıyor, birazdan tekrar deneyin.')
      } else if (status === 400 || status === 422) {
        setError(def.boundsText)
      } else {
        setError('Kaydedilemedi, tekrar deneyin.')
      }
    } finally {
      setSaving(false)
    }
  }

  function handleSave() {
    const num = parseInput()
    if (num == null) {
      setError('Geçerli bir sayı girin.')
      return
    }
    if (num < def.displayMin || num > def.displayMax) {
      setError(def.boundsText)
      return
    }
    run(() => saveThreshold(def.field, def.toStored(num)), 'Kaydedildi. ' + def.effectText)
  }

  function handleReset() {
    run(() => resetThreshold(def.field), 'Varsayılana döndürüldü. ' + def.effectText)
  }

  return (
    <div className="border-b border-app-border py-4 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-text-primary">{def.label}</span>
        {isCustomized ? (
          <span className="flex items-center gap-1.5">
            <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-medium text-brand">
              Sizin ayarınız: {def.toDisplay(current)}
              {def.unit}
            </span>
            <span className="text-[11px] text-text-muted">
              (varsayılan: {def.defaultDisplay}
              {def.unit})
            </span>
          </span>
        ) : (
          <span className="rounded-full bg-app-surface-muted px-2.5 py-0.5 text-xs text-text-secondary">
            Varsayılan: {def.toDisplay(current)}
            {def.unit}
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-text-secondary">{def.helpText}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Input
          type="number"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setError(null)
            setSavedMsg(null)
          }}
          className="h-9 w-28"
        />
        <span className="text-sm text-text-secondary">{def.unit}</span>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Kaydet'}
        </Button>
        {isCustomized && (
          <Button size="sm" variant="outline" onClick={handleReset} disabled={saving}>
            Varsayılana dön
          </Button>
        )}
      </div>
      <p className="mt-1 text-[11px] text-text-muted">{def.boundsText}</p>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
      {savedMsg && <p className="mt-1 text-xs text-success">{savedMsg}</p>}
    </div>
  )
}
