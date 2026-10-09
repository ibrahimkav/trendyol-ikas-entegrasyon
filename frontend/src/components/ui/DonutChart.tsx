import { cn } from './utils'

export interface DonutSegment {
  label: string
  value: number
  color: string
}

interface DonutChartProps {
  segments: DonutSegment[]
  size?: number
  strokeWidth?: number
  centerLabel?: string
  centerValue?: string
  className?: string
}

/** "Masraf Kalemleri" donut'u gibi bağımsız SVG halka grafik (kütüphane bağımlılığı yok). */
export default function DonutChart({ segments, size = 160, strokeWidth = 22, centerLabel, centerValue, className }: DonutChartProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className={cn('relative', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#F3F4F6" strokeWidth={strokeWidth} />
        {total > 0 &&
          segments.map((seg, i) => {
            const fraction = seg.value / total
            const dash = fraction * circumference
            const el = (
              <circle
                key={i}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={seg.color}
                strokeWidth={strokeWidth}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
              />
            )
            offset += dash
            return el
          })}
      </svg>
      {(centerLabel || centerValue) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {centerValue && <span className="text-lg font-semibold text-text-primary">{centerValue}</span>}
          {centerLabel && <span className="text-xs text-text-secondary">{centerLabel}</span>}
        </div>
      )}
    </div>
  )
}

interface DonutLegendProps {
  segments: DonutSegment[]
  formatValue?: (value: number) => string
}

/** Donut altındaki renkli-nokta + etiket + değer legend grid'i. */
export function DonutLegend({ segments, formatValue }: DonutLegendProps) {
  return (
    <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {segments.map((seg) => (
        <li key={seg.label} className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2 text-text-secondary">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: seg.color }} />
            {seg.label}
          </span>
          <span className="font-medium tabular-nums text-text-primary">{formatValue ? formatValue(seg.value) : seg.value}</span>
        </li>
      ))}
    </ul>
  )
}
