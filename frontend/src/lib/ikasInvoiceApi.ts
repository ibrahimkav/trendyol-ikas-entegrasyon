import apiClient from '../config/api'

/**
 * ikas Fatura API — backend/routers/invoices.py. ikas Start paketinde API olmadığı için
 * siparişler ikas'tan dışa aktarılan Excel/CSV ile gelir. Fatura kesme (E-Faturam
 * bağlantısı) 2. aşamada; şimdilik içe aktarma + fatura taslağı + eksik bilgi düzeltme.
 */

export type IkasOrderStatus = 'ready' | 'needs_info' | 'invoiced' | 'error'
export type IkasStatusFilter = 'all' | IkasOrderStatus

export interface IkasOrderSummary {
  order_number: string
  order_date: string | null
  customer: string
  buyer_type: 'bireysel' | 'kurumsal'
  city: string
  gross_total: number
  vat_total: number
  status: IkasOrderStatus
  errors: string[]
  warnings: string[]
  edited: boolean
  invoice_number: string | null
  invoice_error: string | null
}

export interface Billing {
  full_name: string
  company_name: string
  identity_number: string
  tax_number: string
  tax_office: string
  email: string
  phone: string
  address: string
  district: string
  city: string
  postal_code: string
  country: string
}

export interface InvoiceLine {
  name: string
  sku: string
  barcode: string
  quantity: number
  vat_rate: number
  unit_price_net: number
  net_amount: number
  vat_amount: number
  gross_amount: number
}

export interface InvoiceDraft {
  buyer_type: 'bireysel' | 'kurumsal'
  tax_id: string
  billing: Billing
  currency: string
  lines: InvoiceLine[]
  totals: {
    net: number
    vat: number
    gross: number
    vat_breakdown: { rate: number; net: number; vat: number }[]
    order_total_in_file: number | null
    discount_applied: number
  }
  errors: string[]
  warnings: string[]
  ready: boolean
}

export interface IkasOrderDetail extends IkasOrderSummary {
  draft: InvoiceDraft
  overrides: Partial<Billing>
}

export interface ImportResult {
  orders_in_file: number
  rows_in_file: number
  created: number
  updated: number
  skipped_invoiced: number
  recognized_columns: Record<string, string>
  ignored_columns: string[]
  missing_fields: string[]
}

export interface InvoiceSettings {
  product_vat_rate: number
  shipping_vat_rate: number
  efaturam_connected: boolean
}

export type StatusCounts = Record<IkasStatusFilter, number>

export async function importIkasFile(file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiClient.post<ImportResult>('/invoices/ikas/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return res.data
}

export async function fetchIkasOrders(
  status: IkasStatusFilter,
  q?: string,
): Promise<{ items: IkasOrderSummary[]; counts: StatusCounts }> {
  const res = await apiClient.get('/invoices/ikas/orders', { params: { status, q: q || undefined } })
  return res.data
}

export async function fetchIkasOrder(orderNumber: string): Promise<IkasOrderDetail> {
  const res = await apiClient.get<IkasOrderDetail>(`/invoices/ikas/orders/${encodeURIComponent(orderNumber)}`)
  return res.data
}

export async function updateIkasOrder(orderNumber: string, body: Partial<Billing>): Promise<IkasOrderSummary> {
  const res = await apiClient.patch<IkasOrderSummary>(
    `/invoices/ikas/orders/${encodeURIComponent(orderNumber)}`,
    body,
  )
  return res.data
}

export async function deleteIkasOrder(orderNumber: string): Promise<void> {
  await apiClient.delete(`/invoices/ikas/orders/${encodeURIComponent(orderNumber)}`)
}

export async function fetchInvoiceSettings(): Promise<InvoiceSettings> {
  const res = await apiClient.get<InvoiceSettings>('/invoices/settings')
  return res.data
}

export async function saveInvoiceSettings(body: {
  product_vat_rate: number
  shipping_vat_rate: number
}): Promise<InvoiceSettings> {
  const res = await apiClient.put<InvoiceSettings>('/invoices/settings', body)
  return res.data
}
