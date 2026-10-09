# Trendyol AI Satıcı Asistanı - Kurulum ve Kullanım

## 🚀 Hızlı Başlangıç

### Windows'ta Tek Tıkla Başlatma

1. **`start.bat`** dosyasına çift tıklayın
2. Script otomatik olarak:
   - Python ve Node.js kontrolü yapar
   - Gerekli bağımlılıkları yükler
   - Backend ve Frontend'i başlatır

### Gereksinimler

Projeyi çalıştırmak için aşağıdaki yazılımların kurulu olması gerekir:

1. **Python 3.8+**
   - İndirme: https://www.python.org/downloads/
   - Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin

2. **Node.js 16+**
   - İndirme: https://nodejs.org/
   - LTS versiyonu önerilir

### İlk Kurulum

İlk kez çalıştırdığınızda script otomatik olarak:
- Python virtual environment oluşturur
- Backend bağımlılıklarını yükler (`pip install`)
- Frontend bağımlılıklarını yükler (`npm install`)
- `.env` dosyası oluşturur (varsa `env.example`'dan)

**Not:** İlk kurulum 5-10 dakika sürebilir.

### Yapılandırma

1. `backend/.env` dosyasını açın
2. Trendyol API bilgilerinizi girin:
   ```
   TRENDYOL_API_KEY=your_api_key
   TRENDYOL_API_SECRET=your_api_secret
   TRENDYOL_SUPPLIER_ID=your_supplier_id
   ```

### Kullanım

1. **`start.bat`** dosyasına çift tıklayın
2. Backend ve Frontend yeni pencerelerde açılacak
3. Tarayıcınızda **http://localhost:3000** adresini açın

### Durdurma

- Backend penceresinde **Ctrl+C** yapın
- Frontend penceresinde **Ctrl+C** yapın
- Veya pencereleri kapatın

## 📁 Proje Yapısı

```
trendyol/
├── backend/          # Python FastAPI backend
│   ├── .env         # API anahtarları (oluşturmanız gerekir)
│   ├── main.py      # Ana uygulama
│   └── routers/     # API route'ları
├── frontend/         # React frontend
│   ├── src/         # Kaynak kodlar
│   └── package.json # Frontend bağımlılıkları
├── start.bat        # Windows başlatma scripti
├── start.ps1        # PowerShell başlatma scripti
└── KURULUM.md       # Bu dosya
```

## 🔧 Manuel Kurulum

Eğer script çalışmazsa, manuel olarak:

### Backend
```bash
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
py -m uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## ❓ Sorun Giderme

### Python bulunamadı
- Python'u PATH'e ekleyin
- Veya `py` launcher kullanın (Windows'ta genelde kurulu gelir)

### Node.js bulunamadı
- Node.js'i PATH'e ekleyin
- Terminal'i yeniden başlatın

### Port zaten kullanımda
- 3000 veya 8000 portunu kullanan uygulamayı kapatın
- Veya `vite.config.ts` ve `main.py` dosyalarında portu değiştirin

### Bağımlılıklar yüklenmiyor
- İnternet bağlantınızı kontrol edin
- Firewall/antivirus yazılımınızı kontrol edin
- Manuel olarak `pip install -r requirements.txt` ve `npm install` çalıştırın

## 📞 Destek

Sorun yaşarsanız:
1. Hata mesajını not edin
2. `backend/.env` dosyasının doğru yapılandırıldığından emin olun
3. Python ve Node.js versiyonlarını kontrol edin

## 🎯 Özellikler

- ✅ Otomatik Barkod Sistemi
- ✅ AI Fiyat Önerisi
- ✅ Dashboard ve İstatistikler
- ✅ Bildirim Sistemi
- ✅ Kargo Takip
- ✅ Müşteri Yönetimi
- ✅ Mağaza Performansı

