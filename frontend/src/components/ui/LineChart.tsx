import { cn } from './utils'

export interface LineChartPoint {
  label: string
  value: number
}

interface LineChartProps {
  data: LineChartPoint[]
  height?: number
  color?: string
  showArea?: boolean
  formatValue?: (value: number) => string
  className?: string
}

/** "Kâr Performansı" zaman serisi grafiği gibi bağımsız SVG çizgi grafik. */
export default function LineChart({ data, height = 220, color = '#FF6B4A', showArea = true, formatValue, className }: LineChartProps) {
  if (data.length === 0) {
    return (
      <div className={cn('flex items-center justify-center text-sm text-text-muted', className)} style={{ height }}>
        Veri yok
      </div>
    )
  }

  const width = 600 // viewBox genişliği; svg width=100% ile konteynere göre esner
  const values = data.map((d) => d.value)
  const max = Math.max(...values)
  const min = Math.min(0, ...values)
  const range = max - min || 1
  const stepX = width / (data.length - 1 || 1)

  const points = data.map((d, i) => ({
    x: i * stepX,
    y: height - ((d.value - min) / range) * (height - 16) - 8,
  }))

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  const lastPoint = points[points.length - 1]
  const firstPoint = points[0]
  const areaPath = `${linePath} L${lastPoint.x},${height} L${firstPoint.x},${height} Z`

  return (
    <div className={className}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        {showArea && <path d={areaPath} fill={color} opacity={0.12} />}
        <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={2.5} fill={color} />
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-text-muted">
        <span>{data[0]?.label}</span>
        <span>{data[data.length - 1]?.label}</span>
      </div>
      {formatValue && <p className="mt-1 text-right text-xs text-text-secondary">Son: {formatValue(values[values.length - 1])}</p>}
    </div>
  )
}
