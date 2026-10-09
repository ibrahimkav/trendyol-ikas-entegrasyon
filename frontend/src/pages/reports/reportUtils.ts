/** Rapor sayfaları için varsayılan tarih aralığı: son 30 gün (bugün dahil), ISO yyyy-mm-dd. */
export function defaultReportRange(): { startDate: string; endDate: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 29)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  return { startDate: iso(start), endDate: iso(end) }
}
