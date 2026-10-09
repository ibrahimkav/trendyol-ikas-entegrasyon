import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { LayoutGrid, LogOut, MonitorSmartphone, Settings as SettingsIcon } from 'lucide-react'
import { operationalNav, otherToolsGroups, sidebarNav, type NavEntry } from './melontikNav'
import { useAuth } from '../context/AuthContext'

/**
 * melontik icon-rail sidebar: varsayılan 72px, sadece ikon; hover'da o item
 * için etiketli flyout açılır (grup item'larda alt-link listesi).
 * Kaynak: hive/research/melontik-screens.md + hive/agents/ryan-mttzjxj7/design-system.md
 */
export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { logout } = useAuth()
  const [openId, setOpenId] = useState<string | null>(null)

  const isActive = (path: string) => location.pathname === path
  const groupIsActive = (entry: Extract<NavEntry, { kind: 'group' }>) =>
    entry.children.some((c) => isActive(c.path))
  const otherToolsActive = otherToolsGroups.some((g) => g.items.some((i) => isActive(i.path)))

  return (
    <aside className="flex w-[72px] shrink-0 flex-col border-r border-app-border bg-app-surface">
      <Link
        to="/dashboard"
        className="flex h-16 items-center justify-center border-b border-app-border outline-none"
        aria-label="Anasayfa"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-lg font-bold text-white">
          %
        </span>
      </Link>

      <nav className="flex flex-1 flex-col items-center gap-1 overflow-y-auto py-3">
        {sidebarNav.map((entry) => {
          const Icon = entry.icon
          const active = entry.kind === 'leaf' ? isActive(entry.path) : groupIsActive(entry)
          const open = openId === entry.id

          return (
            <div
              key={entry.id}
              className="relative w-full px-2"
              onMouseEnter={() => setOpenId(entry.id)}
              onMouseLeave={() => setOpenId(null)}
            >
              {entry.kind === 'leaf' ? (
                <Link
                  to={entry.path}
                  className={`relative flex h-11 w-full items-center justify-center rounded-md transition-colors ${
                    active ? 'bg-brand-soft text-brand' : 'text-text-secondary hover:bg-app-surface-muted hover:text-text-primary'
                  }`}
                >
                  {active && <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-full bg-brand" />}
                  <Icon className="h-5 w-5" />
                </Link>
              ) : (
                <button
                  type="button"
                  className={`relative flex h-11 w-full items-center justify-center rounded-md transition-colors ${
                    active ? 'bg-brand-soft text-brand' : 'text-text-secondary hover:bg-app-surface-muted hover:text-text-primary'
                  }`}
                  aria-haspopup="menu"
                  aria-expanded={open}
                >
                  {active && <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-full bg-brand" />}
                  <Icon className="h-5 w-5" />
                </button>
              )}

              {open && (
                <div className="absolute left-full top-0 z-50 ml-1 min-w-[15rem] rounded-md border border-app-border bg-app-surface py-1.5 shadow-elevated">
                  <p className="px-3 pb-1.5 pt-1 text-caption uppercase tracking-wide text-text-muted">{entry.label}</p>
                  {entry.kind === 'leaf' ? (
                    <Link
                      to={entry.path}
                      className={`block px-3 py-2 text-sm ${active ? 'text-brand' : 'text-text-primary hover:bg-app-surface-muted'}`}
                    >
                      {entry.label}
                    </Link>
                  ) : (
                    entry.children.map((child) => (
                      <Link
                        key={child.path}
                        to={child.path}
                        className={`block px-3 py-2 text-sm ${
                          isActive(child.path) ? 'text-brand' : 'text-text-primary hover:bg-app-surface-muted'
                        }`}
                      >
                        {child.label}
                      </Link>
                    ))
                  )}
                </div>
              )}
            </div>
          )
        })}
      </nav>

      {/* İnsan kararı: Barkod + Sipariş Okut günlük operasyon için ana sidebar'a taşındı
          (Phyllis'in keep-hidden kararı bu iki sayfa için override edildi). melontik'in kendi
          sırasını bozmamak için ayrı, küçük bir bölüm olarak ayraçla eklendi. */}
      <div className="flex w-full flex-col items-center gap-1 border-t border-app-border px-2 py-2">
        {operationalNav.map((entry) => {
          const Icon = entry.icon
          const active = isActive(entry.path)
          const open = openId === entry.id
          return (
            <div
              key={entry.id}
              className="relative w-full"
              onMouseEnter={() => setOpenId(entry.id)}
              onMouseLeave={() => setOpenId(null)}
            >
              <Link
                to={entry.path}
                className={`relative flex h-11 w-full items-center justify-center rounded-md transition-colors ${
                  active ? 'bg-brand-soft text-brand' : 'text-text-secondary hover:bg-app-surface-muted hover:text-text-primary'
                }`}
              >
                {active && <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-full bg-brand" />}
                <Icon className="h-5 w-5" />
              </Link>
              {open && (
                <div className="absolute left-full top-0 z-50 ml-1 min-w-[15rem] rounded-md border border-app-border bg-app-surface py-1.5 shadow-elevated">
                  <p className="px-3 pb-1.5 pt-1 text-caption uppercase tracking-wide text-text-muted">{entry.label}</p>
                  <Link
                    to={entry.path}
                    className={`block px-3 py-2 text-sm ${active ? 'text-brand' : 'text-text-primary hover:bg-app-surface-muted'}`}
                  >
                    {entry.label}
                  </Link>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* "Diğer Araçlar" — Phyllis w1-ux-disposition.md §3'ten kalan 15 KEEP-HIDDEN trendyol sayfası
          (Barkod + Sipariş Okut insan kararıyla ana sidebar'a taşındı, bkz. yukarısı). Bilinçli
          olarak coral aileden AYRIK (nötr gri) tutuluyor ki kullanıcı melontik-klon ekranlarla trendyol-native araçları
          ayırt edebilsin. */}
      <div
        className="relative w-full border-t border-app-border px-2 py-2"
        onMouseEnter={() => setOpenId('__other-tools')}
        onMouseLeave={() => setOpenId(null)}
      >
        <button
          type="button"
          className={`relative flex h-11 w-full items-center justify-center rounded-md transition-colors ${
            otherToolsActive
              ? 'bg-app-surface-muted text-text-primary'
              : 'text-text-muted hover:bg-app-surface-muted hover:text-text-secondary'
          }`}
          aria-haspopup="menu"
          aria-expanded={openId === '__other-tools'}
          aria-label="Diğer Araçlar"
        >
          <LayoutGrid className="h-5 w-5" />
        </button>

        {openId === '__other-tools' && (
          <div className="absolute bottom-0 left-full z-50 ml-1 max-h-[80vh] min-w-[16rem] overflow-y-auto rounded-md border border-app-border bg-app-surface py-1.5 shadow-elevated">
            <p className="px-3 pb-1.5 pt-1 text-caption uppercase tracking-wide text-text-muted">
              Diğer Araçlar <span className="normal-case text-text-muted/70">(trendyol native)</span>
            </p>
            {otherToolsGroups.map((group) => (
              <div key={group.label} className="border-t border-app-border/60 first:border-t-0">
                <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {group.label}
                </p>
                {group.items.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`block px-3 py-1.5 text-sm ${
                      isActive(item.path) ? 'text-text-primary font-medium' : 'text-text-secondary hover:bg-app-surface-muted'
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        className="relative w-full border-t border-app-border px-2 py-3"
        onMouseEnter={() => setOpenId('__account')}
        onMouseLeave={() => setOpenId(null)}
      >
        <button
          type="button"
          className="flex h-10 w-full items-center justify-center rounded-full bg-app-surface-muted text-sm font-semibold text-text-primary"
          aria-haspopup="menu"
          aria-expanded={openId === '__account'}
        >
          D
        </button>
        {openId === '__account' && (
          <div className="absolute bottom-0 left-full z-50 ml-1 min-w-[13rem] rounded-md border border-app-border bg-app-surface py-1.5 shadow-elevated">
            <Link to="/settings" className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-primary hover:bg-app-surface-muted">
              <SettingsIcon className="h-4 w-4 text-text-secondary" /> Ayarlar
            </Link>
            <Link to="/old-dashboard" className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-primary hover:bg-app-surface-muted">
              <MonitorSmartphone className="h-4 w-4 text-text-secondary" /> Basit Dashboard
            </Link>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/login', { replace: true })
              }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-text-primary hover:bg-app-surface-muted"
            >
              <LogOut className="h-4 w-4" /> Çıkış
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
