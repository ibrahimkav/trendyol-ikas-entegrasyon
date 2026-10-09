# Trendyol AI Satıcı Asistanı 🚀

Trendyol satıcıları için yapay zeka destekli kapsamlı satış yönetim uygulaması.

## 🎯 Özellikler

### 1. Akıllı Barkod Sistemi
- **Problem**: Kargo barkodlarında ürün bilgisi yok, fazla siparişte ürünleri ayırt etmek zor
- **Çözüm**: Sipariş içindeki ürün sayısı ve detayları barkoda entegre edilir
- QR/Barkod oluşturma ve okuma
- Sipariş-ürün eşleştirme

### 2. AI Destekli Fiyat Önerisi
- Piyasa fiyat analizi (Trendyol, rakipler)
- Altın oran ve psikolojik fiyatlandırma
- Rekabet analizi
- Kâr optimizasyonu

### 3. Genişletilebilir Modüller
- Sipariş yönetimi
- Stok takibi
- Raporlama ve analitik
- Otomatik fiyat güncelleme

## 🚀 Hızlı Başlangıç

### Windows'ta Tek Tıkla Başlatma

1. **`start.bat`** dosyasına çift tıklayın
2. Script otomatik olarak:
   - Python ve Node.js kontrolü yapar
   - Gerekli bağımlılıkları yükler
   - Backend ve Frontend'i başlatır

**Detaylı kurulum için:** [KURULUM.md](KURULUM.md) dosyasına bakın.

## 🛠️ Teknoloji Stack

- **Frontend**: React + TypeScript + Tailwind CSS
- **Backend**: Python (FastAPI)
- **AI/ML**: Groq API (ücretsiz), Hugging Face (ücretsiz), OpenAI (opsiyonel)
- **Barkod**: qrcode, barcode libraries
- **Database**: SQLite (geliştirme) / PostgreSQL (production)

## 📦 Gereksinimler

- **Python 3.8+** - https://www.python.org/downloads/
- **Node.js 16+** - https://nodejs.org/

## 🎨 Özellikler

- ✅ Otomatik Barkod Sistemi
- ✅ AI Fiyat Önerisi (Altın Oran, Psikolojik Fiyatlandırma)
- ✅ Dashboard ve İstatistikler
- ✅ Bildirim Sistemi (Sesli, PWA)
- ✅ Kargo Takip
- ✅ Müşteri Yönetimi
- ✅ Mağaza Performansı
- ✅ Modern ve Responsive Tasarım

## 🤖 Groq API (Ücretsiz AI)

Bu uygulama **Groq API** kullanarak ücretsiz ve hızlı AI destekli fiyat önerileri sunar.

- ✅ **Tamamen ücretsiz**
- ✅ **Çok hızlı** (saniyede 500+ token)
- ✅ **Kolay kurulum** (2 dakika)

**Kurulum:**
1. https://console.groq.com/ adresinden ücretsiz API key alın
2. `backend/.env` dosyasına `GROQ_API_KEY=your_key` ekleyin

Detaylı kurulum: [backend/AI_SETUP.md](backend/AI_SETUP.md)

**Not:** Groq API olmadan da uygulama çalışır (kural tabanlı öneri sistemi devreye girer)

## 📝 Kullanım

1. **Ücretsiz AI Kurulumu** (Önerilen: Groq API)
   - https://console.groq.com/ adresinden ücretsiz API key alın
   - `.env` dosyasına `GROQ_API_KEY=your_key` ekleyin
   - Detaylı kurulum: [AI_SETUP.md](backend/AI_SETUP.md)

2. Trendyol API bilgilerinizi `backend/.env` dosyasına ekleyin

3. Uygulamayı başlatın:
   ```bash
   # Windows'ta:
   start.bat
   
   # Veya manuel:
   # Backend
   cd backend
   py -m uvicorn main:app --reload
   
   # Frontend (yeni terminal)
   cd frontend
   npm run dev
   ```

4. Tarayıcınızda **http://localhost:3000** adresini açın

## 📄 Lisans

MIT

## 🔧 Sorun Giderme

Sorun yaşarsanız [KURULUM.md](KURULUM.md) dosyasındaki "Sorun Giderme" bölümüne bakın.
