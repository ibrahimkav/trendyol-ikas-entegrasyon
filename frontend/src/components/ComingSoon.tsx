import { Sparkles } from 'lucide-react'

type ComingSoonProps = {
  title: string
}

/**
 * melontik sidebar'ında yer alan ama sayfa gövdesi henüz kurulmamış rotalar
 * için geçici yer tutucu (Wave 2'de gerçek sayfayla değiştirilecek).
 */
export default function ComingSoon({ title }: ComingSoonProps) {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">Bu sayfanın içeriği Wave 2'de eklenecek.</p>
      </div>
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-app-border bg-app-surface p-16 text-center shadow-card">
        <Sparkles className="h-8 w-8 text-brand" />
        <p className="text-sm text-text-secondary">{title} sayfası yakında burada olacak.</p>
      </div>
    </div>
  )
}
