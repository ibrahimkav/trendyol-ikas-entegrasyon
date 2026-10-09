# ROADMAP.md — Trendyol AI Satıcı Asistanı → SaaS Dönüşüm Yol Haritası

> Oluşturma: 08.09.2026
> Kaynaklar: (1) tam kod tabanı denetimi (bkz. aşağıdaki "Kod Tabanı Denetimi" bölümü), (2) referans ürün analizi — melontik.com (demo hesap), (3) mevcut `TODO.md`
> Kapsam kararları (kullanıcı talimatı): **barkod tarafında yalnızca temizlik yapılacak, yeni aksiyon alınmayacak**; frontend'de **ölçülü** düzenleme yapılacak; proje **SaaS ürünü** olarak ele alınacak; sonunda **yayına** hazır hale getirilmesi hedefleniyor.

---

## 0. Yönetici Özeti

Mevcut uygulama zaten geniş bir özellik yüzeyine sahip (25 backend router, 26 frontend route: sipariş, stok, barkod, kampanya, iade, SEO, müşteri segmentasyonu, yerel AI destekli müşteri soru-cevap...). Eksik olan şey yeni modül sayısı değil, **üç temel şey**:

1. **Güven** — açıkta kalmış canlı API anahtarları, gerçek olmayan (varsayılan %40) ürün maliyeti, kod ile dokümantasyon arasında çelişen AI mimarisi.
2. **Finansal derinlik** — Melontik'in çekirdek değeri olan "gerçek kâr" hesabı bizde de var ama iskelet halinde; kargo/komisyon gerçek veriye değil sabit varsayımlara dayanıyor.
3. **SaaS iskeleti** — şu an **hiç kullanıcı/oturum/kimlik doğrulama katmanı yok**. Tek mağaza, tek kullanıcı varsayımıyla yazılmış. SaaS olarak yayınlamadan önce bu zorunlu.

Roadmap bu üçünü önceliklendirip, Melontik'ten öğrenilen özellikleri (kârlılık dashboard'u, ters fiyat motoru, hakediş kontrolü, promosyon kârlılık filtresi, pazar zekası) kademeli olarak ekleyecek şekilde kurgulanmıştır.

---

## Faz 0 — Acil: Güvenlik & Temizlik (1 gün, kod değişikliği yok denecek kadar az)

### 0.1 Kritik güvenlik açığı — HEMEN
- `backend/env.example` (nokta**sız**) dosyasında **gerçek, canlı** Trendyol API key/secret/supplier ID ve Groq API key duruyor — `.env` ile birebir aynı.
- `.gitignore` yalnızca `.env` dosya adını hariç tutuyor, `env.example`'ı değil. Proje `git init` edilip commit atıldığı an bu anahtarlar depoya girer.
- **Aksiyon:** `env.example` içeriğini placeholder değerlerle değiştir (zaten var olan `.env.example` ile aynı formatta) veya dosyayı tamamen sil (`.env.example` zaten aynı işi görüyor). `backend/AI_SETUP.md:26` şu an kullanıcıyı yanlışlıkla `env.example`'a yönlendiriyor, `.env.example`'a çevrilmeli.
- **Öneri:** Bu anahtarlar bir noktada açık bir dosyada durduğu için, gerçek Trendyol/Groq API anahtarlarını rotasyona sokmak (yenilemek) ihtiyaten mantıklı.

### 0.2 Güvenle silinebilir dosyalar (gereksiz)
| Dosya | Neden |
|---|---|
| `backend/backend_error.log`, `backend/backend_output.log`, `backend/uvicorn_test.log` | 0 byte, boş eski log |
| `backend/uvicorn_test.log`'un yanındaki `uvicorn_test_err.log` | sadece normal başlangıç banner'ı, hata değil |
| `test-redir.log` (kök) | PowerShell redirect denemesinden kalma, uygulamayla ilgisi yok |
| `frontend/frontend.log` | elle çalıştırılmış `vite dev`'den kalma 1000+ satır stdout dökümü |
| `frontend/src/App.test.tsx`, `frontend/src/App.simple.tsx` | hiçbir yerden import edilmiyor, iskeletten kalma |
| `frontend/src/components/BarcodeGenerator.tsx` | kullanılmıyor, yerini `AutoBarcodeGenerator.tsx` almış (barkod alanında **tek** dokunuş bu olacak: kullanılmayan dosyayı silmek — yeni özellik eklenmeyecek) |
| `backend/test_size_advisor.py` | manuel debug scripti, test suite'e bağlı değil |
| `package-lock.json` (kök) | boş stub, karşılığında kök `package.json` bile yok |
| `frontend/dist/` | build çıktısı, zaten `.gitignore`'da — istenirse silinip yeniden build edilebilir |

### 0.3 Karar gereken maddeler (şüpheli — silmeden önce onay)
| Konu | Soru |
|---|---|
| `backend/requirements.txt` vs `requirements-fix.txt` | `-fix` dosyası eski/terk edilmiş `groq==0.4.1` pin'ini içeriyor (TODO.md'ye göre bu sürüm sorunluydu). Hiçbir start scripti bunu kullanmıyorsa silinecek. |
| `backend/frontend/` + `backend/node_modules` + `backend/package.json` | İçinde sadece `jszip` var, gerçek bir frontend kopyası değil. Python backend'in JS paketine ihtiyacı olmaz — muhtemelen yanlış dizinde `npm install` çalıştırılmış. Backend hiçbir yerden node/jszip çağırmıyor → silinmeye aday. |
| `start.bat` / `start-fixed.bat` / `start.ps1` / `test-start.bat` | Dokümantasyon (README/KURULUM) sadece `start.bat`'ı anlatıyor. Diğer üçü ya eski deneme ya da tanı scripti. Tek bir kanonik launcher'a indirilmeli. |
| `Ürünleriniz_31.12.2025-20.02.xlsx` (kök) | Gerçek bir Trendyol ürün verisi, kod tarafından kullanılmıyor. Kişisel veri — repoda durmamalı, silinsin ya da `.gitignore`'a alınan bir `data/` klasörüne taşınsın. |
| `backend/notifications.db` ayrı, `backend/trendyol_data.db` ayrı | İkisi de gerçek ve kullanılıyor ama aralarında FK/transaction bütünlüğü yok. Şimdilik bug değil, mimari not — Faz 1'de tek şemaya toplanması değerlendirilebilir. |

### 0.4 Dokümantasyon/kod çelişkisi (düzeltme kararı gerekiyor)
`TODO.md` "AI tamamen YEREL çalışır, Groq kaldırıldı" diyor ama gerçekte Groq hâlâ 3 yerde canlı: `routers/pricing.py`, `routers/seo_optimization.py`, `routers/notifications.py` (üçü de anahtar yoksa rule-based fallback'e düşüyor, çökme riski yok). Sadece Müşteri Soru-Cevap modülü gerçekten yerel TF-IDF motoruna taşınmış. **Karar:** ya TODO.md güncellensin ("kısmi geçiş" olarak), ya da kalan 3 modül de yerel motora taşınsın (Faz 1'e alındı, bkz. 1.4).

---

## Faz 1 — Mimari Sağlamlaştırma (SaaS'ın önkoşulu)

### 1.1 Kimlik doğrulama & çoklu mağaza (multi-tenant) — **en kritik eksik**
Şu an uygulamada login/oturum/kullanıcı modeli yok; tek Trendyol mağazası `.env`'den okunuyor. SaaS olabilmek için:
- Kullanıcı hesabı + JWT/oturum tabanlı auth
- Her kullanıcının kendi Trendyol API kimliklerini (key/secret/supplier id) güvenli şekilde (şifrelenmiş) kaydedebildiği bir "Mağaza Bağlama" akışı — Melontik'in "Mağazanızı Bağlayın (1 dakika)" adımına benzer
- Veritabanı şemasına `tenant_id`/`user_id` eklenmesi (mevcut 18 tabloya dokunan büyük bir migration)

### 1.2 Gerçek ürün maliyeti
`financial.py`'deki kâr hesapları şu an ürün maliyetini **gelirin sabit %40'ı** olarak varsayıyor (`unit_cost = unit_price * 0.40`). Bu gerçek veri değil, tahmindir. Melontik'in yaptığı gibi kullanıcının her ürüne gerçek maliyet girmesi gerekiyor:
- `Product` modeline `cost_price` alanı (kısmen zaten olabilir, kontrol edilecek)
- Ürün listesinde toplu/tekli maliyet girişi UI'ı
- Maliyet girilmemiş ürünler için görsel uyarı ("kâr hesabı tahmini" etiketi)

### 1.3 Gerçek komisyon tarifesi
Şu an yalnızca 7 kategori için sabit oran var (`elektronik: %12` vb.). Trendyol'un onlarca kategoride değişen komisyon tarifesi var. Kullanıcının kendi kategori komisyon oranlarını girebildiği/güncelleyebildiği bir tablo (Melontik'in "Ürün Komisyon Tarifesi" sayfasına benzer) — Faz 2 ile birleşebilir.

### 1.4 AI mimarisi tutarlılığı
Faz 0.4'teki karara göre: pricing/SEO/notifications modüllerini de yerel motora taşı ya da TODO.md'yi güncelle. Bu kullanıcı tercihine bağlı — roadmap'te açık soru olarak bırakıldı.

---

## Faz 2 — Finansal Çekirdek (Melontik-ilhamlı, mevcut altyapı genişletiliyor)

Zaten var olan `financial.py` (`/summary`, `/order-profitability`, `/product-profitability`, `/revenue-breakdown`, `/commission-calculator`) gerçek maliyet/komisyon verisiyle (Faz 1.2/1.3) beslenince, üstüne şunlar eklenecek:

- **Kategori kârlılık raporu** (Melontik: "Kategori Kârlılık Analizi") — mevcut `revenue-breakdown`'ı kâr bazlı genişlet
- **İade zarar analizi** (Melontik: "İade Zarar Analizi") — mevcut `returns.py` ile `financial.py`'yi birleştiren yeni rapor
- **Reklam kârlılık analizi** — reklam harcaması girişi + ROAS hesabı
- **Katalog geneli "Kâr Marjı Listesi"** — `product-profitability` endpoint'i zaten bunun temeli, frontend'de tek ekran liste/filtre haline getirilecek
- **`FinancialManagement.tsx`** yeniden tasarım: net kâr kartı, gider dağılım grafiği, dönem seçici, kâr trendi çizgisi (TODO.md A4 ile aynı, buraya konsolide edildi)

---

## Faz 3 — Fiyatlandırma & Promosyon Araçları

### 3.1 Ters fiyat hesaplama motoru
Melontik'in "Ürün Fiyatlandırma" sayfası: maliyet + hedef kâr oranı + kargo + **desi** + KDV + kategori komisyonu girilince satış fiyatını otomatik hesaplıyor. Bizim mevcut `PricingAssistant.tsx` piyasa/rakip fiyat odaklı — bu, onu **tamamlayan** farklı bir araç (maliyet-odaklı, "hedef kâra göre fiyat kaçta kalmalı" sorusuna cevap verir). `pricing.py`'ye yeni bir `/reverse-pricing` endpoint'i.

### 3.2 Promosyon/kampanya kârlılık filtresi
Melontik'in en çarpıcı özelliği: Trendyol'un komisyon tarifesi/flaş teklif/kampanya tekliflerini indirip, hedef kâr marjına göre "kabul et / reddet" diye otomatik filtreliyor. Bizim `campaigns.py` router'ı zaten var — üzerine kârlılık filtresi eklenebilir (uzun vadeli, Trendyol'un teklif export formatına bağlı, önce veri formatı araştırılmalı).

---

## Faz 4 — Hakediş Kontrolü & Uyarı Sistemi

- **Hakediş/ödeme mutabakatı**: Trendyol'un fazla kestiği kargo faturası / eksik ödediği komisyonu yakalayan bir mutabakat raporu (Melontik'in en güçlü "güven" özelliği — "₺1.284 fazla kesilen kargo faturası" gibi somut bulgular). Bunun için Trendyol hakediş/ödeme API'sinin (varsa) veya elle yüklenen hakediş dökümünün mevcut sipariş verisiyle karşılaştırılması gerekiyor — önce Trendyol API'sinde böyle bir endpoint olup olmadığı araştırılmalı.
- **Kritik kâr marjı uyarıları**: mevcut `notifications.py` sistemine "bu ürün zararına satılıyor" tipi uyarı ekle (Faz 1.2 gerçek maliyet verisi şart koşuyor).

---

## Faz 5 — Pazar Zekası (opsiyonel, uzun vadeli)

Melontik'in en yeni/premium modülü: rakip mağaza takibi, ürün takibi, reklam radarı. Bizim `competitor_analysis.py` router'ı zaten var — kapsamı ne kadar karşılıyor kontrol edilip, gerekirse genişletilebilir. **Öncelik düşük** — önce Faz 1-4 tamamlanmalı, bu bir "genişleme" fazı.

---

## Faz 6 — Barkod: Sadece Temizlik

Kullanıcı talimatı gereği bu alanda **yeni özellik/aksiyon alınmayacak**. Tek yapılacak: Faz 0.2'de listelenen ölü `BarcodeGenerator.tsx` dosyasının silinmesi. `AutoBarcodeGenerator.tsx`, `OrderScanner.tsx` ve ilgili backend router (`barcode.py`, 140KB) olduğu gibi korunacak.

---

## Faz 7 — Frontend Düzenlemeleri (ölçülü)

Kapsamlı bir yeniden yazım değil, hedefli iyileştirmeler:
- Navigasyon: 26 route tek seviyeli bir menüde — Melontik'teki gibi mantıksal gruplama (Dashboard / Finansal Raporlar / Fiyatlandırma / Operasyon / Ayarlar) düşünülebilir (`layout/navConfig.ts`)
- `FinancialManagement.tsx` yeniden tasarımı (Faz 2 ile birlikte)
- Ölü dosyaların (`App.test.tsx`, `App.simple.tsx`) temizlenmesi (Faz 0)
- Tutarlı boş-durum/yükleniyor/hata bileşenleri (Melontik'te net görülen "Demo modu yükleniyor", "Data Bulunamadı" gibi durumlar bizde de standardize edilebilir)
- Ayarlar sayfası eksik — Faz 1.1 (mağaza bağlama) ile birlikte eklenmeli

---

## Faz 8 — SaaS Ürünleştirme & Yayın Hazırlığı

Melontik'in ticarileşme modelinden öğrenilenler:
- **Kullanım bazlı paketleme**: aylık sipariş hacmine göre otomatik paket ataması (Starter/Business/Enterprise benzeri), yıllık ödemede indirim
- **Güvenli ödeme altyapısı**: iyzico benzeri bir Türkiye ödeme sağlayıcısı entegrasyonu
- **Otomatik e-fatura**: KolayBi veya benzeri
- **KVKK uyumluluk**: veri işleme/saklama politikası, kullanıcı onayları
- **2FA / güvenli giriş**: Faz 1.1 auth katımıyla birlikte
- **Yayın öncesi checklist**: Faz 0 güvenlik maddelerinin kapatılmış olması zorunlu ön koşul

---

## Önerilen Sıralama

1. **Faz 0** (bugün — güvenlik + temizlik, düşük risk)
2. **Faz 1.1 + 1.2** (auth + gerçek maliyet — SaaS'ın ve doğru kâr hesabının önkoşulu)
3. **Faz 2** (finansal çekirdek — Melontik'in asıl değeri, mevcut altyapı zaten %60 hazır)
4. **Faz 1.3 + Faz 3.1** (komisyon tarifesi + ters fiyat motoru)
5. **Faz 7** (frontend düzenlemeleri, Faz 2 ile paralel yürüyebilir)
6. **Faz 4** (hakediş kontrolü — Trendyol API'de veri var mı önce araştırılmalı)
7. **Faz 8** (SaaS ürünleştirme — yayına en yakın adım)
8. **Faz 3.2 / Faz 5** (kampanya filtresi, pazar zekâsı — genişleme, en son)

---

## Açık Sorular (kullanıcıya)

- Faz 0.3'teki şüpheli dosyalar (özellikle `backend/frontend/`, `requirements-fix.txt`, birden fazla `start*.bat`) için silme onayı verilecek mi, yoksa tek tek mi karar verilecek?
- Faz 0.4: Groq tamamen mi kaldırılsın (tam yerel AI), yoksa mevcut hibrit (yerelde yoksa Groq'a düş) hâliyle mi devam edilsin?
- Faz 4 (hakediş kontrolü) için Trendyol API'sinde hakediş/ödeme dökümü endpoint'i mevcut mu — araştırma yapılsın mı?
- SaaS ödeme sağlayıcısı için tercih var mı (iyzico, PayTR, Stripe vb.) yoksa Faz 8'e kadar ertelensin mi?

---

## Ek: Kod Tabanı Denetimi — Özet Tablo

Ayrıntılı denetim raporu bu roadmap'in temelini oluşturdu. Öne çıkan sayılar:
- Backend: 25 router, 18 SQLAlchemy tablo, 2 ayrı SQLite dosyası (`trendyol_data.db`, `notifications.db`)
- Frontend: 26 route, 30 component, hiçbiri "core" dışında yetim değil (BarcodeGenerator.tsx hariç)
- 1 kritik güvenlik bulgusu (açık API anahtarları), 1 mimari tutarsızlık (Groq/TODO çelişkisi), 11 güvenle silinebilir dosya, 6 karar bekleyen dosya grubu
