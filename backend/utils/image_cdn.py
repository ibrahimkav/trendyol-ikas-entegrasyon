"""
Trendyol ürün görseli URL yardımcısı — w3-product-image-backend, güncellendi w3-image-url-store.

w3-image-url-store (Jim'in kanıtı, hive/docs/image-url-truth.md): contentId'den
`mnresize/{w}/{h}/ty{contentId}.jpg` kalıbıyla URL ÜRETMEK yanlıştı (HTTP 403) —
gerçek Trendyol CDN URL'i (`ty{sayı}/prod/.../{uuid}/1_org_zoom.jpg`) contentId'yi
dosya adında HİÇ içermiyor, sadece API'nin `images[0].url` alanından öğrenilebilir
(database/sync_service.py bunu artık Product.image_url'e yazıyor).

Bu fonksiyon artık HİÇBİR ŞEY ÜRETMİYOR — sadece senkronda saklanan ham URL'i
geçirir. Tek yerden yönetim değeri hâlâ var: null/boş-string normalizasyonu tek
yerde (çağıranlar `is not None` yerine bu fonksiyonu çağırmaya devam eder), ve
ileride CDN URL'i post-process etmek gerekirse (ör. boyut parametresi eklemek)
tek dosya güncellenir.
"""
from typing import Optional


def trendyol_thumbnail_url(image_url: Optional[str]) -> Optional[str]:
    """Saklanan gerçek görsel URL'ini döner. Senkron henüz bu ürünü görmediyse
    (image_url=None/boş) None döner — UYDURMA URL ÜRETİLMEZ."""
    return image_url or None
