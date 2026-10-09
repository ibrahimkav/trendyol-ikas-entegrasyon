import { Link, useLocation } from 'react-router-dom'
import { Bell, HelpCircle } from 'lucide-react'
import BackendStatus from '../components/BackendStatus'
import NotificationBadge from '../components/NotificationBadge'
import { pageTitles } from './melontikNav'

/**
 * melontik topbar: sayfa başlığı + "Nasıl Yapılır?" (genel) + bildirim + avatar.
 * Tarih aralığı / "PDF olarak indir" burada YOK — ground-truth'ta bunlar sadece Dashboard'a
 * özel (hive/research/melontik-screens.md), o yüzden sayfa kendi PageHeader'ında ekliyor
 * (bkz. components/Dashboard.tsx) — burada tekrarlamak çift buton üretiyordu, kaldırıldı.
 */
export default function Topbar() {
  const location = useLocation()
  const title = pageTitles[location.pathname] ?? 'Trendyol AI'

  return (
    <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-app-border bg-app-surface px-6">
      <h1 className="truncate text-lg font-semibold text-text-primary">{title}</h1>

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="hidden items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-app-surface-muted hover:text-text-primary sm:flex"
        >
          <HelpCircle className="h-4 w-4" />
          Nasıl Yapılır?
        </button>

        <div className="mx-1 h-6 w-px bg-app-border" />

        <BackendStatus />
        <Link
          to="/notifications"
          className="relative rounded-md p-2 text-text-secondary transition-colors hover:bg-app-surface-muted hover:text-text-primary"
          aria-label="Bildirimler"
        >
          <Bell className="h-5 w-5" />
          <NotificationBadge className="right-0.5 top-0.5" />
        </Link>

        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
          D
        </span>
      </div>
    </header>
  )
}
