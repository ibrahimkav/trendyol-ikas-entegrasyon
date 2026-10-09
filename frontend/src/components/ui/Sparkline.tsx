interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  strokeWidth?: number
  variant?: 'line' | 'bar'
  className?: string
}

/** Dashboard'daki 6 KPI kartının altındaki mini grafik gibi bağımsız, kütüphanesiz SVG sparkline. */
export default function Sparkline({
  data,
  width = 96,
  height = 32,
  color = '#FF6B4A',
  strokeWidth = 2,
  variant = 'line',
  className,
}: SparklineProps) {
  if (data.length === 0) return null

  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1

  if (variant === 'bar') {
    const barWidth = width / data.length
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden="true">
        {data.map((value, i) => {
          const barHeight = ((value - min) / range) * (height - 2) + 2
          return (
            <rect
              key={i}
              x={i * barWidth + barWidth * 0.15}
              y={height - barHeight}
              width={barWidth * 0.7}
              height={barHeight}
              rx={1}
              fill={color}
              opacity={0.85}
            />
          )
        })}
      </svg>
    )
  }

  const points = data.map((value, i) => {
    const x = (i / (data.length - 1 || 1)) * width
    const y = height - ((value - min) / range) * (height - 4) - 2
    return `${x},${y}`
  })

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden="true">
      <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
