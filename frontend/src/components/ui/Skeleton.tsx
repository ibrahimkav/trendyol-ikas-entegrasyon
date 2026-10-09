import { cn } from './utils'

interface SkeletonProps {
  className?: string
}

/** İlk yükleme placeholder'ı (kart/satır) — Phyllis'in w2a-interaction-spec.md ortak loading kuralı. */
export default function Skeleton({ className }: SkeletonProps) {
  return <div className={cn('animate-pulse rounded-md bg-app-surface-muted', className)} />
}
