import { useMemo, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronUp, ChevronsUpDown, Maximize2, Minimize2 } from 'lucide-react'
import { cn } from './utils'
import SegmentedControl from './SegmentedControl'

export interface DataTableColumn<T> {
  key: string
  header: string
  accessor: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  /** Verilince kolon sıralanabilir olur; sıralama anahtarını döndürür. */
  sortValue?: (row: T) => string | number
}

type Density = 'compact' | 'comfortable'
type FontScale = 'sm' | 'base' | 'lg'

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  data: T[]
  rowKey: (row: T) => string
  pageSize?: number
  /** Toolbar'ın soluna yerleşen "Filtrele" butonu/paneli tetikleyicisi gibi bir slot. */
  filterSlot?: ReactNode
  emptyMessage?: string
  className?: string
  /** Satır bazlı ek sınıf (ör. flagged satırı vurgulamak için). */
  rowClassName?: (row: T) => string | undefined
}

const fontSizeClasses: Record<FontScale, string> = {
  sm: 'text-xs',
  base: 'text-sm',
  lg: 'text-base',
}

/**
 * Raporlar / Canlı Performans / Kâr Marjı Listesi'ndeki ortak veri tablosu kabuğu:
 * sıralanabilir başlıklar, yoğunluk (Sık/Geniş) toggle, font A-/A+, tam ekran, sayfalama.
 */
export default function DataTable<T>({
  columns,
  data,
  rowKey,
  pageSize = 10,
  filterSlot,
  emptyMessage = 'Kayıt bulunamadı.',
  className,
  rowClassName,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null)
  const [page, setPage] = useState(1)
  const [density, setDensity] = useState<Density>('comfortable')
  const [fontScale, setFontScale] = useState<FontScale>('base')
  const [fullscreen, setFullscreen] = useState(false)

  const sortedData = useMemo(() => {
    if (!sort) return data
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sortValue) return data
    const sortValue = col.sortValue
    const copy = [...data]
    copy.sort((a, b) => {
      const av = sortValue(a)
      const bv = sortValue(b)
      if (av === bv) return 0
      const result = av > bv ? 1 : -1
      return sort.dir === 'asc' ? result : -result
    })
    return copy
  }, [data, sort, columns])

  const totalPages = Math.max(1, Math.ceil(sortedData.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const pageData = sortedData.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const rowPadding = density === 'compact' ? 'py-2' : 'py-3.5'

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: 'asc' }
      if (prev.dir === 'asc') return { key, dir: 'desc' }
      return null
    })
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-app-border bg-app-surface shadow-card',
        fullscreen && 'fixed inset-4 z-50 overflow-auto',
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-border p-4">
        <div className="flex items-center gap-2">{filterSlot}</div>
        <div className="flex items-center gap-2">
          <SegmentedControl
            options={[
              { value: 'comfortable', label: 'Geniş' },
              { value: 'compact', label: 'Sık' },
            ]}
            value={density}
            onChange={setDensity}
          />
          <div className="inline-flex items-center rounded-md border border-app-border">
            <button
              type="button"
              onClick={() => setFontScale((s) => (s === 'lg' ? 'base' : 'sm'))}
              className="px-2 py-1 text-xs font-semibold text-text-secondary hover:bg-app-surface-muted"
              aria-label="Yazı boyutunu küçült"
            >
              A-
            </button>
            <button
              type="button"
              onClick={() => setFontScale((s) => (s === 'sm' ? 'base' : 'lg'))}
              className="border-l border-app-border px-2 py-1 text-xs font-semibold text-text-secondary hover:bg-app-surface-muted"
              aria-label="Yazı boyutunu büyüt"
            >
              A+
            </button>
          </div>
          <button
            type="button"
            onClick={() => setFullscreen((f) => !f)}
            className="rounded-md border border-app-border p-1.5 text-text-secondary hover:bg-app-surface-muted"
            aria-label={fullscreen ? 'Tam ekrandan çık' : 'Tam ekran'}
          >
            {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className={cn('w-full border-collapse', fontSizeClasses[fontScale])}>
          <thead>
            <tr className="bg-app-surface-muted">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => col.sortValue && toggleSort(col.key)}
                  className={cn(
                    'select-none whitespace-nowrap px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-text-secondary',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center',
                    col.sortValue && 'cursor-pointer hover:text-text-primary',
                  )}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortValue &&
                      (sort?.key === col.key ? (
                        sort.dir === 'asc' ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                      ))}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-text-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              pageData.map((row) => (
                <tr key={rowKey(row)} className={cn('border-t border-app-border hover:bg-app-surface-muted', rowClassName?.(row))}>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'px-4 text-text-primary',
                        rowPadding,
                        col.align === 'right' && 'text-right tabular-nums',
                        col.align === 'center' && 'text-center',
                      )}
                    >
                      {col.accessor(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-app-border px-4 py-3 text-xs text-text-secondary">
        <span>
          Toplam kayıt: <strong className="text-text-primary">{sortedData.length}</strong>
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-md border border-app-border px-2 py-1 disabled:opacity-40"
          >
            Önceki
          </button>
          <span>
            Sayfa {currentPage} / {totalPages}
          </span>
          <button
            type="button"
            disabled={currentPage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="rounded-md border border-app-border px-2 py-1 disabled:opacity-40"
          >
            Sonraki
          </button>
        </div>
      </div>
    </div>
  )
}
