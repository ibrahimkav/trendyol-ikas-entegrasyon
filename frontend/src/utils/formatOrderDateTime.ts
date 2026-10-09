/** Sipariş geliş / oluşturulma zamanı: gün.ay.yıl saat:dakika (tr-TR) */
export function formatOrderDateTime(value: string | number | Date | undefined | null): string {
  if (value == null) return '—'
  if (typeof value === 'string' && value.trim() === '') return '—'
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return typeof value === 'string' ? value : '—'
  return d.toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
