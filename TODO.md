# 📋 Geliştirme To-Do Listesi

> Oluşturma: 27.08.2026 | Son Güncelleme: 28.08.2026
> Hedefler: (1) melontik.com tarzı pazaryeri finansal analiz sistemi, (2) geçmiş soru-cevaplardan öğrenen AI
> **KARAR:** AI tamamen YEREL çalışır (dış API yok: Groq kaldırıldı, RAG + TF-IDF yerel motor)

---

## ✅ 0. Kritik Önce: Ortam Sorunlarını Düzelt — TAMAMLANDI

- [x] **Python venv bozuktu** → Python 3.12.10 kuruldu (winget), venv yeniden oluşturuldu
- [x] Tüm bağımlılıklar kuruldu (fastapi, groq, scikit-learn 1.9.0, sqlalchemy 2.0.52, pandas...)
- [x] `groq` 1.7.0'a yükseltildi (eski 0.4.1 yeni httpx ile uyumsuzdu — diğer modüller için)
- [x] Sunucu canlı test edildi: `/api/health` ✅

---

## ✅ Bölüm B: Geçmiş Cevaplardan Öğrenen YEREL AI — ÇEKİRDEK TAMAMLANDI

**Yapılan mimari değişiklik:** Groq API **tamamen kaldırıldı**. AI artık tamamen
yerel çalışıyor: TF-IDF anlamsal benzerlik + onaylı cevap havuzu + kategori şablonları.
Dış bağımlılık yok, internet gerekmez, maliyet yok.

### B1. Kalıcı Veritabanına Taşıma ✅
- [x] `QARecord` modeli eklendi (`database/models.py` → qa_records tablosu)
- [x] `database/qa_repository.py` oluşturuldu (SQLite + ghost-mode in-memory fallback)
- [x] `customer_qa.py` in-memory listeden temizlendi, tüm endpoint'ler DB'ye taşındı
- [x] Eski boş qa_records tablosu migrate edildi (legacy şema düşürüldü)
- [x] Sunucu yeniden başlasa da veriler korunuyor

### B2. Anlamsal Benzerlik ✅
- [x] `utils/qa_learning.py` → `QALearningEngine` (TF-IDF char_wb 2-4 gram + cosine)
- [x] Türkçe için karakter bazlı vektörleştirme (kelime kökünden bağımsız eşleşme)
- [x] Benzerlik eşiği 0.30 (altı = yeni soru tipi), kelime-bazlı fallback mevcut
- [x] Test: "Kargim kac gunde ulasir?" ↔ "Kargom ne zaman gelir?" = %45.7 benzerlik yakaladı

### B3. Yerel Öğrenme Döngüsü (Feedback Loop) ✅
- [x] `generate_local_answer()` — 3 kademeli yerel AI:
      1) benzerlik ≥ %55 → onaylı geçmiş cevap önerilir (öğrenilmiş)
      2) benzerlik ≥ %30 → geçmiş cevap + kategori şablonu tamamlaması
      3) benzerlik yok → kategori şablonu (kargo/iade/ödeme/ürün/kampanya) veya genel şablon
- [x] `POST /{qa_id}/feedback` → accepted / edited / rejected
      (accepted+edited → öğrenme havuzuna girer, rejected → girmez)
- [x] `GET /stats/learning` → öğrenme istatistikleri (havuz boyutu, kabul oranı, ortalama güven)
- [x] Manuel cevap vermek de havuza girer (AI satıcının cevaplarından öğrenir)
- [x] Canlı API testi: farklı kelimelerle sorulan soruya öğrenilmiş cevap döndü (%63 benzerlik, güven 0.84) ✅

### B4. Frontend (CustomerQA.tsx) ✅
- [x] AI öneri kartına "Kabul Et / Düzenle / Reddet" butonları (feedback endpoint'e bağla)
- [x] Öneri gösterirken "%X benzer geçmiş cevaptan öğrendim" bilgisi (reasoning + answer_source)
- [x] Öğrenme istatistikleri mini paneli (/stats/learning)
- [x] Cevap şablonu yönetimi (kargo/iade/ödeme/ürün/kampanya metinleri düzenlenebilir olsun)

### B5. Opsiyonel İyileştirmeler
- [ ] Soru kategorilendirme UI'da filtre olarak (kategoriler backend'de hazır)
- [ ] Toplu AI cevaplama (onaya düşen tüm sorular için sırayla öneri üret)
- [ ] Kelime kökü/kısaltma sözlüğü (benzerlik kalitesini artırmak için)

---

## 📊 Bölüm A: Melontik Tarzı Finansal Analiz Sistemi — BAŞLANMADI

**Mevcut durum:** `backend/routers/financial.py` içinde temel modül var:
`/summary`, `/revenue-breakdown`, `/expenses` (CRUD), `/commission-calculator`.

### A1. Sipariş Bazlı Kâr/Zarar Analizi (En önemli eksik)
- [ ] Her sipariş için: satış tutarı − ürün maliyeti − Trendyol komisyonu
      − kargo − reklam − diğer giderler = net kâr hesabı
- [ ] `financial.py`'ye `GET /order-profitability` endpoint'i ekle
- [ ] Ürün bazlı kâr marjı listesi (en kârlı / en zararlı ürünler)
- [ ] Sipariş tablosuna `product_cost` (maliyet) alanı ekle → `database/models.py`

### A2. Gider Yönetimi Genişletme
- [ ] Gider kategorileri (reklam, kargo, ambalaj, komisyon, iade, diğer)
- [ ] Reklam maliyeti girişi (Trendyol reklam paneli verileri manuel/CSV)
- [ ] Periyodik giderler (aylık sabit giderler)

### A3. Dönemsel Karşılaştırma & Trend
- [ ] Ay/ay, hafta/hafta ciro ve kâr karşılaştırması (`GET /period-comparison`)
- [ ] Trendyol komisyon oranı kategori bazlı doğru hesaplama
- [ ] Aylık finansal özet raporu (PDF/Excel export — `export_import.py` altyapısı var)

### A4. Finansal Dashboard (Frontend)
- [ ] `FinancialManagement.tsx` melontik tarzı yenile: net kâr kartı, gider dağılımı
      pasta grafiği, kâr trendi çizgi grafiği, dönem seçici
- [ ] Sipariş bazlı kâr/zarar tablosu (filtrelenebilir, sıralanabilir)
- [ ] "Kâr marjı düşük" uyarıları → mevcut bildirim sistemine bağla

---

## 🔧 Teknik Notlar

- **AI mimarisi (final):** Yerel RAG — geçmiş onaylı cevaplar TF-IDF ile
  vektörize edilir, yeni soruya en benzerleri bulunur ve cevabı önerilir.
  Model eğitimi yok, dış API yok, Groq key gerekmez. scikit-learn ile çalışır.
- **"Öğrenme"** = her onaylanan/düzenlenen cevap havuza girer → AI giderek zenginleşir.
- Veritabanı: SQLite `qa_records` tablosu (12 kolon), SQLAlchemy ile.

## 🎯 Önerilen Sıralama (güncel)
1. ~~Ortam düzeltme~~ ✅
2. ~~B1 Kalıcılık~~ ✅ | ~~B2 Benzerlik~~ ✅ | ~~B3 Yerel öğrenme döngüsü~~ ✅
3. ~~B4 (Frontend: feedback butonları + öğrenme paneli)~~ ✅
4. **→ SIRADAKİ: A1 (sipariş kâr analizi) → A4 (dashboard) → A2, A3**

