/**
 * TR biçimleri — hive/agents/phyllis-mttzizd9/w2a-interaction-spec.md "Ortak kurallar":
 * para birimi ₺X.XXX,XX / yüzde %X,XX (virgüllü, tam sayıya yuvarlanmaz).
 */
export function formatCurrencyTRY(value: number): string {
  return `₺${value.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatPercent(value: number): string {
  return `%${value.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
