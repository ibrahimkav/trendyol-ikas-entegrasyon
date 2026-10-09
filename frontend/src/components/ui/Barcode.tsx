import { useMemo } from 'react'
import { code128Bars } from '../../lib/code128'

interface BarcodeProps {
  /** Kodlanacak değer (ör. order_id). Client-side Code128-B olarak çizilir. */
  value: string
  /** Bar yüksekliği (px). Varsayılan 48. */
  height?: number
  /** Alt yazı olarak değeri göster. Varsayılan true. */
  showValue?: boolean
  className?: string
}

/**
 * Bağımlılıksız, taranabilir Code128 lineer barkod (SVG). lib/code128.ts vendored kodlayıcıyı
 * kullanır. Kargo barkodu için: her kartta gerçek barkod gösterir (barcode_image boş gelse bile).
 */
export default function Barcode({ value, height = 48, showValue = true, className }: BarcodeProps) {
  const { modules, bars } = useMemo(() => code128Bars(value), [value])
  const QUIET = 10 // sessiz bölge (modül) — tarayıcı okuması için gerekli
  const totalWidth = modules + QUIET * 2

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${totalWidth} ${height}`}
        width="100%"
        height={height}
        preserveAspectRatio="none"
        shapeRendering="crispEdges"
        role="img"
        aria-label={`Barkod ${value}`}
      >
        <rect x={0} y={0} width={totalWidth} height={height} fill="#ffffff" />
        {bars.map((bar, i) => (
          <rect key={i} x={bar.x + QUIET} y={0} width={bar.width} height={height} fill="#000000" />
        ))}
      </svg>
      {showValue && (
        <p className="mt-1 text-center font-mono text-xs tracking-wider text-text-secondary">{value}</p>
      )}
    </div>
  )
}
