# Database Sistemi

## Genel Bakış

Bu proje, performanslı bir local database sistemi kullanır. Veriler SQLite database'de saklanır ve arka planda Trendyol API'den otomatik olarak senkronize edilir.

## Özellikler

- ✅ **SQLite Database**: Local, hızlı, kurulum gerektirmez
- ✅ **Otomatik Senkronizasyon**: Arka planda 30 dakikada bir veriler güncellenir
- ✅ **Cache Sistemi**: Veriler database'den okunur, API çağrıları minimize edilir
- ✅ **Fallback Mekanizması**: Database yoksa API'den çeker
- ✅ **Async Operations**: Performanslı async database işlemleri

## Database Yapısı

### Tablolar

1. **products**: Ürün bilgileri ve güncel fiyatlar
2. **orders**: Sipariş bilgileri
3. **order_lines**: Sipariş satırları (ürünler)
4. **competitor_prices**: Rakip fiyat bilgileri
5. **sync_logs**: Senkronizasyon logları
6. **cache_metadata**: Cache metadata

## Kullanım

### İlk Kurulum

Database otomatik olarak başlatılır. Backend başlatıldığında:
1. Database dosyası oluşturulur (`trendyol_data.db`)
2. Tablolar oluşturulur
3. İlk senkronizasyon başlatılır
4. Arka plan senkronizasyonu başlar (30 dakikada bir)

### Manuel Senkronizasyon

```bash
# Tüm verileri senkronize et
POST /api/sync/all

# Sadece ürünleri senkronize et
POST /api/sync/products

# Sadece siparişleri senkronize et
POST /api/sync/orders?days=30

# Senkronizasyon durumunu kontrol et
GET /api/sync/status
```

### Database'den Veri Okuma

Kod içinde database'den veri okumak için:

```python
from database.db import get_db
from database.repository import ProductRepository

# Dependency injection ile
def my_endpoint(db: Session = Depends(get_db)):
    products = ProductRepository.get_all(db)
    return products
```

## Performans

- **Database Okuma**: ~1-5ms (API çağrısı: ~200-500ms)
- **Senkronizasyon**: Arka planda çalışır, kullanıcıyı etkilemez
- **Cache**: Veriler database'de cache'lenir, API çağrıları minimize edilir

## Konfigürasyon

Senkronizasyon sıklığını değiştirmek için `main.py` dosyasındaki `background_sync_task` çağrısını düzenleyin:

```python
sync_task = asyncio.create_task(background_sync_task(interval_minutes=30))
```

## Database Dosyası

Database dosyası: `backend/trendyol_data.db`

**Not**: Bu dosya `.gitignore`'a eklenmelidir (zaten ekli olmalı).

## Sorun Giderme

### Database Sıfırlama

```python
from database.db import reset_db
reset_db()  # DİKKAT: Tüm veriler silinir!
```

### Database Yeniden Başlatma

```python
from database.db import init_db
init_db()
```

## Gelecek İyileştirmeler

- [ ] PostgreSQL desteği (production için)
- [ ] Database migration sistemi
- [ ] Daha gelişmiş cache stratejileri
- [ ] Real-time sync notifications


