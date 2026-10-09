# components/ui — melontik klon bileşen kütüphanesi

Kaynak: `hive/agents/ryan-mttzjxj7/design-system.md` + `hive/research/melontik-screens.md`.
Token'lar zaten `frontend/tailwind.config.js`'te (Oscar, `w1-frontend-shell`) — burada
sadece o token'ları kullanan bileşenler var, tailwind.config.js'e ayrıca dokunulmadı.

Sayfa montajı/routing bu kütüphanenin kapsamı DIŞINDA — sadece bileşenler.

## İçe aktarma

```tsx
import { Button, KpiCard, DataTable, ProfitBadge } from '../ui'
// veya tek tek: import Button from '../ui/Button'
```

## Bileşenler

| Bileşen | Melontik karşılığı | Not |
|---|---|---|
| `Button` | Fiyat Oluştur / Pin Kodu Al (primary), Temizle (secondary=maroon dolu) | variant: primary/secondary/outline/ghost/danger, size: sm/md/lg |
| `Badge`, `ProfitBadge` | "₺882,5 Kâr (%64.5)" rozeti | ProfitBadge işaret (+/-) ile tone'u otomatik seçer, ok ikonuyla çift kodlu |
| `KpiCard` | Dashboard'daki 6 KPI kartı | `sparkline` slotuna `<Sparkline />` verilir |
| `ColoredKpiCard` | Canlı Performans'taki 4 renkli kart | tone: success/info/warning/brand/neutral + `tooltip` |
| `Sparkline` | KPI kartı altındaki mini grafik | kütüphanesiz SVG, `variant="line"\|"bar"` |
| `DonutChart`, `DonutLegend` | "Masraf Kalemleri" donut'u | kütüphanesiz SVG halka + legend grid |
| `LineChart` | "Kâr Performansı" zaman serisi | kütüphanesiz SVG çizgi grafik |
| `ChartContainer` | Grafik kartı kabuğu | `action` = sağ üst filtre/segmented control, `legend` = alt açıklama |
| `SegmentedControl` | "Yoğunluk: 3 Kolon / 4 Kolon" | genel amaçlı 2+ seçenekli toggle |
| `DataTable` | Raporlar / Canlı Performans tabloları | sıralama, Sık/Geniş yoğunluk, A-/A+ font, tam ekran, sayfalama dahili |
| `FilterPanel`, `FilterToggle`, `FilterRange` | "Ürünleri Filtreleyin" sol panel | `onClear` verilirse "Filtreleri Temizle" (maroon) butonu çıkar |
| `Input`, `Select`, `RadioGroup`, `Toggle`/`Switch` | Form alanları, KDV radio grubu | native form elemanları, label/error/hint destekli |
| `DateRangePicker` | "Tarih Aralığı" seçici | native `input[type=date]`, ek kütüphane yok |
| `PageHeader` | Sayfa başlığı + breadcrumb + aksiyon | breadcrumb `onClick` alır, routing'e bağlı değil (react-router'a bağlamak çağıran sayfanın işi) |

## Tasarım notları

- Grafikler (Sparkline/DonutChart/LineChart) bilinçli olarak **kütüphanesiz** — projede
  recharts/chart.js vb. yoktu, mevcut `Dashboard.tsx` da conic-gradient ile elle donut
  çiziyordu. Bir chart kütüphanesi eklemek istenirse (örn. büyük veri setleri, animasyon,
  tooltip ihtiyacı çıkarsa) bu sarmalayıcıların iç implementasyonu değiştirilebilir —
  dışa açılan prop arayüzü aynı kalabilir.
- `tsc` ile derleme doğrulandı (`npm run build`).
- Bazı sınıf adları (`text-text-secondary`, `bg-secondary` vb.) tailwind.config.js'teki
  `text.*` (gri metin) ile `secondary.*` (maroon marka rengi) token gruplarının farklı
  isimlendirilmesinden geliyor — kasıtlı, `Badge`'in `secondary` tonu bu yüzden `maroon`
  olarak adlandırıldı (BadgeTone: 'brand'|'maroon'|'success'|'danger'|'warning'|'info'|'neutral').
