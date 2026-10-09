# Groq API Kurulum Rehberi 🤖

Bu uygulama **Groq API** kullanarak ücretsiz ve hızlı AI destekli fiyat önerileri sunar.

## 🚀 Groq API Nedir?

Groq, ücretsiz ve çok hızlı bir AI servisidir:
- ✅ **Tamamen ücretsiz**
- ✅ **Çok hızlı** (saniyede 500+ token)
- ✅ **Kolay kurulum**
- ✅ **Güvenilir**

## 📝 Kurulum Adımları

### 1. Groq Hesabı Oluşturun
1. https://console.groq.com/ adresine gidin
2. "Sign Up" ile ücretsiz hesap oluşturun
3. E-posta doğrulamasını tamamlayın

### 2. API Key Oluşturun
1. Groq Console'da **API Keys** bölümüne gidin
2. **Create API Key** butonuna tıklayın
3. Key'inizi kopyalayın (bir daha gösterilmeyecek!)

### 3. .env Dosyasına Ekleyin
`backend/.env` dosyasını oluşturun (veya `env.example`'ı `.env` olarak kopyalayın):

```env
GROQ_API_KEY=gsk_your_key_here
```

**Önemli**: `.env` dosyasını git'e commit etmeyin! (zaten .gitignore'da)

## 🎯 Kullanılabilir Modeller

Uygulama şu anda `llama-3.1-8b-instant` modelini kullanıyor. İsterseniz `backend/routers/pricing.py` dosyasında değiştirebilirsiniz:

- `llama-3.1-8b-instant` - Hızlı, önerilen (şu anki)
- `mixtral-8x7b-32768` - Daha güçlü, biraz daha yavaş
- `llama-3.1-70b-versatile` - En güçlü, daha yavaş

## ✅ Test Etme

1. Backend'i başlatın:
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m uvicorn main:app --reload
   ```

2. Test endpoint'ini çağırın:
   ```bash
   curl http://localhost:8000/api/pricing/test
   ```

3. Veya frontend'den Fiyat Önerisi sayfasını kullanın

## ❓ Sorun Giderme

### "Groq paketi yüklü değil" hatası
```bash
pip install groq
```

### "API key gerekli" hatası
- `.env` dosyasının `backend/` klasöründe olduğundan emin olun
- API key'in doğru kopyalandığından emin olun
- Groq Console'da API key'in aktif olduğunu kontrol edin

### "Rate limit" hatası
- Groq ücretsiz tier'da günlük limit var
- Birkaç dakika bekleyip tekrar deneyin
- Uygulama otomatik olarak kural tabanlı öneriye geçer

### API çalışmıyor
- İnternet bağlantınızı kontrol edin
- Groq servis durumunu kontrol edin: https://status.groq.com/
- Uygulama AI olmadan da çalışır (fallback sistemi)

## 📊 Fallback Sistemi

Eğer Groq API çalışmazsa veya API key yoksa, uygulama otomatik olarak **kural tabanlı öneri** sistemine geçer. Bu sistem:
- Altın oran hesaplamaları yapar
- Psikolojik fiyatlandırma önerir
- Rekabet analizi yapar
- Temel fiyat önerileri sunar

**Yani uygulama her zaman çalışır!** 🎉

## 🔒 Güvenlik

- API key'inizi asla paylaşmayın
- `.env` dosyasını git'e commit etmeyin
- Production'da environment variable olarak kullanın

## 📝 Notlar

- Groq API tamamen ücretsizdir
- Rate limit'ler var ama günlük kullanım için yeterlidir
- API key'inizi düzenli olarak rotate edin (güvenlik için)

---

**Sorularınız mı var?** Groq dokümantasyonu: https://console.groq.com/docs
