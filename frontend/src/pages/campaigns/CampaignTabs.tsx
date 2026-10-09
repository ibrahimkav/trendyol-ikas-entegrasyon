import { NavLink } from 'react-router-dom'
import { cn } from '../../components/ui'

const TABS = [
  { to: '/campaign/build-your-campaign', label: 'Kendi Kampanyanı Oluştur' },
  { to: '/campaign/offers', label: 'Avantajlı Teklifler' },
  { to: '/campaign/basket-campaigns', label: 'Sepet Kampanyaları' },
]

/** Kampanya×3 alt-sayfaları arasında ortak sekme gezinmesi. */
export default function CampaignTabs() {
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-app-border">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          className={({ isActive }) =>
            cn(
              'border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              isActive ? 'border-brand text-brand' : 'border-transparent text-text-secondary hover:text-text-primary',
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  )
}
