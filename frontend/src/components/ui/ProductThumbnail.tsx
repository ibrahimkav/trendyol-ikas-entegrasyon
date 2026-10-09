import { useState } from 'react'
import { Package } from 'lucide-react'
import { cn } from './utils'

interface ProductThumbnailProps {
  url: string | null | undefined
  alt: string
  size?: number
  className?: string
}

/**
 * w3-image-bind-ui — url null (henüz senkron olmamış ürün) veya kırık (404/CORS) her iki durumda
 * da aynı sabit boyutlu yer tutucuya düşer, kırık resim ikonu asla görünmez, tablo hizalaması kaymaz.
 */
export default function ProductThumbnail({ url, alt, size = 40, className }: ProductThumbnailProps) {
  const [failed, setFailed] = useState(false)
  const showPlaceholder = !url || failed

  return (
    <div
      style={{ width: size, height: size }}
      className={cn(
        'flex shrink-0 items-center justify-center overflow-hidden rounded-md bg-app-surface-muted text-text-muted',
        className,
      )}
    >
      {showPlaceholder ? (
        <Package className="h-1/2 w-1/2" />
      ) : (
        <img
          src={url}
          alt={alt}
          loading="lazy"
          width={size}
          height={size}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  )
}
