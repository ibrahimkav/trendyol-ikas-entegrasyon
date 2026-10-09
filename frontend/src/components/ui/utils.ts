/** Basit classNames birleştirici — falsy değerleri eler, ek bağımlılık gerektirmez. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}

/**
 * tr-TR para birimi formatlayıcı, ör. formatCurrency(70092.24) -> "₺70.092,24".
 * Phyllis'in w2a-interaction-spec.md'sindeki ortak kural: her zaman 2 ondalık basamak.
 */
export function formatCurrency(amount: number, currency = '₺'): string {
  return `${currency}${amount.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/** tr-TR yüzde formatlayıcı, ör. formatPercent(34.68) -> "%34,68" (spec: virgüllü, tam sayıya yuvarlanmaz). */
export function formatPercent(value: number): string {
  return `%${value.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
