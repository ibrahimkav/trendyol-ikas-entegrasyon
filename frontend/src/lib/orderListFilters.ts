/** Saf fonksiyonlar — liste filtreleri ve test için. */

export function filterOrdersBySearchAndStatus<T extends { order_id: unknown; status: string }>(
  rows: T[],
  searchQuery: string,
  statusFilter: string
): T[] {
  let list = rows
  const q = searchQuery.trim().toLowerCase()
  if (q) {
    list = list.filter((o) => String(o.order_id).toLowerCase().includes(q))
  }
  if (statusFilter !== 'all') {
    list = list.filter((o) => o.status === statusFilter)
  }
  return list
}

export function uniqueOrderStatuses(rows: { status: string }[]): string[] {
  return Array.from(new Set(rows.map((r) => String(r.status || '')).filter(Boolean))).sort((a, b) =>
    a.localeCompare(b, 'tr')
  )
}
