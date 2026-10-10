"""
Database Models
SQLite database için SQLAlchemy modelleri
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class User(Base):
    """Kullanıcı hesabı (email-OTP ile şifresiz giriş)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_login_at = Column(DateTime)


class Store(Base):
    """Bir kullanıcının bağladığı satıcı hesabı (çok-kiracılı kök tablo)"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_name = Column(String, nullable=False, default="Mağazam")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_store_user', 'user_id'),
    )


class StoreCredential(Base):
    """Mağaza başına platform API kimlik bilgileri (Trendyol/Hepsiburada) - şifreli saklanır"""
    __tablename__ = "store_credentials"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)  # 'trendyol' | 'hepsiburada'
    supplier_id = Column(String)  # Trendyol supplier/satıcı ID (platforma göre opsiyonel)
    api_key_encrypted = Column(Text, nullable=False)
    api_secret_encrypted = Column(Text, nullable=False)
    extra_json = Column(Text)  # Platforma özel ek alanlar (JSON)
    is_connected = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('store_id', 'platform', name='uq_store_platform'),
    )


class OTPCode(Base):
    """Email-OTP giriş kodları (kısa ömürlü, hash olarak saklanır)"""
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    purpose = Column(String, default="login")
    attempts = Column(Integer, default=0)
    consumed_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_otp_email', 'email'),
    )


class Product(Base):
    """Ürün bilgileri"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Trendyol product ID (barcode/SKU)
    product_name = Column(String, nullable=False)
    category = Column(String, index=True)
    barcode = Column(String, index=True)
    current_price = Column(Float, default=0.0)
    default_cost = Column(Float, default=0.0)  # Ürün birim maliyeti (kâr analizi)
    desi = Column(Float, default=0.0)  # Desi (hacim/ağırlık) — kargo tahmini için, Trendyol API'de YOK, kullanıcı girer (Ürün Ayarları + Hakediş&Desi Kontrolü)
    content_id = Column(String, nullable=True, index=True)  # Trendyol contentId — ürün görseli için CDN URL üretiminde kullanılır (w3-product-image-backend)
    image_url = Column(String, nullable=True)  # Trendyol API'nin döndürdüğü GERÇEK görsel URL'i (images[0].url) — w3-image-url-store: contentId'den kalıpla ÜRETİLEMEZ (dosya adında geçmiyor), sadece API'den öğrenilir
    last_price_update = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Index'ler performans için
    __table_args__ = (
        Index('idx_product_id', 'product_id'),
        Index('idx_category', 'category'),
        UniqueConstraint('store_id', 'product_id', name='uq_store_product'),
    )


class ProductChangeHistory(Base):
    """w3-write-audit-trail: gerçek satıcı verisine (maliyet/desi/fiyat) yapılan
    HER yazmanın izi — 300 TL vakasının dersi buydu: KİM/NEREDEN yazdığını
    kanıtlayamadık, eski değeri geri getiremedik. `source` alanı en değerlisi
    (hangi uç: tekil/grup/toplu CSV/toplu fiyat) — o gün eksik olan tam buydu."""
    __tablename__ = "product_change_history"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)  # Trendyol product ID (barcode/SKU)
    field = Column(String, nullable=False)  # "default_cost" | "desi" | "current_price"
    old_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=True)
    source = Column(String, nullable=False)  # "single" | "group" | "bulk_csv" | "bulk_price_update"
    changed_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index('idx_pch_store_changed_at', 'store_id', 'changed_at'),
    )


class Order(Base):
    """Sipariş bilgileri"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    order_id = Column(String, index=True, nullable=False)  # Trendyol order ID
    order_number = Column(String, index=True)
    order_date = Column(DateTime, index=True)
    status = Column(String, index=True)
    total_amount = Column(Float, default=0.0)
    customer_name = Column(String)
    cargo_tracking_number = Column(String, index=True)
    raw_data = Column(Text)  # JSON olarak sakla
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_order_id', 'order_id'),
        Index('idx_order_date', 'order_date'),
        Index('idx_status', 'status'),
        UniqueConstraint('store_id', 'order_id', name='uq_store_order'),
    )


class OrderLine(Base):
    """Sipariş satırları (ürünler)"""
    __tablename__ = "order_lines"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    order_id = Column(String, index=True, nullable=False)  # Order.order_id'ye referans
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    product_name = Column(String)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0)  # Satır birim maliyeti (snapshot)
    category = Column(String)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_order_product', 'order_id', 'product_id'),
        # w3-dup-index-fix: Product de aynı 'idx_product_id' adını kullanıyordu —
        # SQLite'ta index adları tablo-bazlı değil GLOBAL, tertemiz bir DB'de
        # create_all() bu yüzden "index already exists" ile çöküyordu.
        Index('idx_orderline_product_id', 'product_id'),
    )


class CompetitorPrice(Base):
    """Rakip fiyat bilgileri"""
    __tablename__ = "competitor_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    competitor_name = Column(String)
    price = Column(Float, nullable=False)
    similarity_score = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_product_competitor', 'product_id', 'competitor_name'),
        Index('idx_last_updated', 'last_updated'),
    )


class SyncLog(Base):
    """Senkronizasyon logları"""
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    sync_type = Column(String, index=True)  # 'products', 'orders', 'competitors'
    status = Column(String, index=True)  # 'success', 'error', 'running'
    records_synced = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_sync_type_status', 'sync_type', 'status'),
        Index('idx_started_at', 'started_at'),
    )


class CacheMetadata(Base):
    """Cache metadata - verilerin ne zaman güncellendiğini takip eder"""
    __tablename__ = "cache_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    cache_key = Column(String, index=True, nullable=False)
    last_updated = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    data_hash = Column(String)  # Veri değişikliğini kontrol etmek için

    __table_args__ = (
        Index('idx_cache_key', 'cache_key'),
        Index('idx_expires_at', 'expires_at'),
        UniqueConstraint('store_id', 'cache_key', name='uq_store_cache_key'),
    )


class ReturnRefund(Base):
    """İade ve İptal Yönetimi"""
    __tablename__ = "return_refunds"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    return_id = Column(String, index=True, nullable=False)  # Trendyol return ID veya internal ID
    order_id = Column(String, index=True, nullable=False)  # Order.order_id'ye referans
    order_number = Column(String, index=True)
    return_type = Column(String, index=True, nullable=False)  # 'return' (iade), 'cancel' (iptal), 'refund' (para iadesi)
    status = Column(String, index=True, default='pending')  # 'pending', 'approved', 'rejected', 'completed', 'cancelled'
    reason = Column(String)  # İade/iptal nedeni
    reason_code = Column(String)  # Trendyol reason code
    customer_name = Column(String)
    customer_phone = Column(String)
    total_amount = Column(Float, default=0.0)
    refund_amount = Column(Float, default=0.0)
    items = Column(Text)  # JSON - iade edilen ürünler
    notes = Column(Text)  # Notlar
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime)  # İşlem tamamlanma tarihi
    raw_data = Column(Text)  # JSON - Trendyol'dan gelen ham veri
    
    __table_args__ = (
        Index('idx_return_order', 'order_id'),
        Index('idx_return_type_status', 'return_type', 'status'),
        Index('idx_created_at', 'created_at'),
        UniqueConstraint('store_id', 'return_id', name='uq_store_return'),
    )


class Campaign(Base):
    """Kampanya ve İndirim Yönetimi"""
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    campaign_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    campaign_type = Column(String, index=True, nullable=False)  # 'coupon', 'flash_sale', 'bulk_discount', 'category_discount'
    discount_type = Column(String, nullable=False)  # 'percentage', 'fixed_amount'
    discount_value = Column(Float, nullable=False)  # İndirim değeri (% veya tutar)
    min_purchase_amount = Column(Float, default=0.0)  # Minimum alışveriş tutarı
    max_discount_amount = Column(Float)  # Maksimum indirim tutarı (yüzde indirimlerde)
    coupon_code = Column(String, index=True)  # Kupon kodu (varsa)
    start_date = Column(DateTime, index=True, nullable=False)
    end_date = Column(DateTime, index=True, nullable=False)
    status = Column(String, index=True, default='draft')  # 'draft', 'active', 'paused', 'expired', 'cancelled'
    target_products = Column(Text)  # JSON - hedef ürün ID'leri (boşsa tüm ürünler)
    target_categories = Column(Text)  # JSON - hedef kategoriler
    usage_limit = Column(Integer)  # Kullanım limiti (null ise sınırsız)
    usage_count = Column(Integer, default=0)  # Kullanım sayısı
    max_usage_per_customer = Column(Integer, default=1)  # Müşteri başına maksimum kullanım
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    raw_data = Column(Text)  # JSON - Trendyol API'den gelen ham veri
    
    __table_args__ = (
        Index('idx_campaign_type_status', 'campaign_type', 'status'),
        Index('idx_campaign_dates', 'start_date', 'end_date'),
        Index('idx_coupon_code', 'coupon_code'),
        UniqueConstraint('store_id', 'campaign_id', name='uq_store_campaign'),
        UniqueConstraint('store_id', 'coupon_code', name='uq_store_coupon'),
    )


class CampaignPerformance(Base):
    """Kampanya performans metrikleri"""
    __tablename__ = "campaign_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    campaign_id = Column(String, index=True, nullable=False)  # Campaign.campaign_id'ye referans
    date = Column(DateTime, index=True, nullable=False)
    orders_count = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    new_customers = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_campaign_date', 'campaign_id', 'date'),
    )


class StockAlert(Base):
    """Stok Uyarıları"""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    product_name = Column(String, nullable=False)
    current_stock = Column(Integer, default=0)
    min_stock_level = Column(Integer, default=0)
    alert_type = Column(String, index=True, nullable=False)  # 'low_stock', 'out_of_stock', 'critical'
    alert_level = Column(Integer, default=0)  # 0: normal, 1: düşük, 2: kritik, 3: tükendi
    days_since_last_sale = Column(Integer)
    average_daily_sales = Column(Float, default=0.0)  # Günlük ortalama satış
    estimated_days_until_out = Column(Integer)  # Tahmini tükenme günü
    is_acknowledged = Column(Boolean, default=False)  # Uyarı görüldü mü?
    acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_product_alert', 'product_id', 'alert_type'),
        Index('idx_alert_level', 'alert_level'),
        Index('idx_acknowledged', 'is_acknowledged'),
    )


class StockRecommendation(Base):
    """Otomatik Stok Sipariş Önerileri"""
    __tablename__ = "stock_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    product_name = Column(String, nullable=False)
    current_stock = Column(Integer, default=0)
    recommended_quantity = Column(Integer, nullable=False)  # Önerilen sipariş miktarı
    recommendation_reason = Column(Text)  # Öneri nedeni
    urgency_level = Column(String, index=True)  # 'low', 'medium', 'high', 'critical'
    estimated_cost = Column(Float, default=0.0)  # Tahmini maliyet
    estimated_arrival_days = Column(Integer, default=7)  # Tahmini teslimat süresi
    is_ordered = Column(Boolean, default=False)  # Sipariş verildi mi?
    ordered_at = Column(DateTime)
    order_reference = Column(String)  # Sipariş referans numarası
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_product_recommendation', 'product_id'),
        Index('idx_urgency_level', 'urgency_level'),
        Index('idx_is_ordered', 'is_ordered'),
    )


class StockHistory(Base):
    """Stok Geçmişi - Stok değişimlerini takip eder"""
    __tablename__ = "stock_history"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    product_name = Column(String)
    previous_stock = Column(Integer, default=0)
    new_stock = Column(Integer, default=0)
    change_amount = Column(Integer, default=0)  # Pozitif: artış, Negatif: azalış
    change_type = Column(String, index=True)  # 'sale', 'restock', 'return', 'adjustment', 'damage'
    reference_id = Column(String)  # İlgili sipariş/ürün ID'si
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_product_date', 'product_id', 'created_at'),
        Index('idx_change_type', 'change_type'),
    )


class PriceHistory(Base):
    """Fiyat Geçmişi - Ürün fiyat değişikliklerini takip eder"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    product_name = Column(String)
    previous_price = Column(Float, default=0.0)
    new_price = Column(Float, nullable=False)
    price_change = Column(Float, default=0.0)  # Pozitif: artış, Negatif: azalış
    price_change_percent = Column(Float, default=0.0)  # Yüzde değişim
    change_reason = Column(String)  # 'manual', 'automation', 'competitor', 'campaign'
    competitor_price = Column(Float)  # Değişiklik sırasındaki rakip fiyatı
    sales_before = Column(Integer, default=0)  # Değişiklik öncesi satış sayısı
    sales_after = Column(Integer, default=0)  # Değişiklik sonrası satış sayısı
    created_at = Column(DateTime, default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_product_price_date', 'product_id', 'created_at'),
        Index('idx_price_change', 'price_change_percent'),
    )


class BarcodeHistory(Base):
    """Barkod Geçmişi - Oluşturulan barkodların kaydı"""
    __tablename__ = "barcode_history"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    order_id = Column(String, index=True, nullable=False)
    order_number = Column(String, index=True)
    barcode_data = Column(Text)  # JSON string olarak sakla
    barcode_type = Column(String, default="qr")  # 'qr', 'code128', 'both'
    template_id = Column(String, index=True)  # Kullanılan şablon ID'si (varsa)
    status = Column(String, index=True, default="created")  # 'created', 'printed', 'shipped', 'archived'
    printed_at = Column(DateTime)  # Yazdırılma tarihi
    shipped_at = Column(DateTime)  # Gönderilme tarihi
    archived_at = Column(DateTime)  # Arşivlenme tarihi
    total_items = Column(Integer, default=0)
    total_value = Column(Float, default=0.0)
    discount_code = Column(String)
    cargo_tracking_number = Column(String, index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        # w3-dup-index-fix-rest: bu 4 index adı Order/ReturnRefund/BarcodeTemplate ile
        # çakışıyordu (SQLite'ta index adları global) — tablo adıyla nitelendirildi.
        Index('idx_barcodehistory_order_id', 'order_id'),
        Index('idx_barcodehistory_status', 'status'),
        Index('idx_barcodehistory_created_at', 'created_at'),
        Index('idx_barcodehistory_template_id', 'template_id'),
    )


class BarcodeTemplate(Base):
    """Barkod Şablonları - Önceden tanımlı şablonlar"""
    __tablename__ = "barcode_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    template_id = Column(String, index=True, nullable=False)
    template_name = Column(String, nullable=False)
    description = Column(Text)
    template_config = Column(Text)  # JSON string olarak şablon ayarları
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)  # Kaç kez kullanıldı
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_template_id', 'template_id'),
        Index('idx_is_default', 'is_default'),
        Index('idx_is_active', 'is_active'),
        UniqueConstraint('store_id', 'template_id', name='uq_store_template'),
    )


class PriceTrend(Base):
    """Fiyat Trend Analizi - Günlük/haftalık trend verileri"""
    __tablename__ = "price_trends"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_id = Column(String, index=True, nullable=False)  # Product.product_id'ye referans
    date = Column(DateTime, index=True, nullable=False)
    period_type = Column(String, index=True, default='daily')  # 'daily', 'weekly', 'monthly'
    average_price = Column(Float, nullable=False)
    min_price = Column(Float)
    max_price = Column(Float)
    price_volatility = Column(Float, default=0.0)  # Fiyat oynaklığı
    sales_count = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    competitor_avg_price = Column(Float)  # Rakip ortalama fiyat
    market_position = Column(String)  # 'above', 'below', 'average' - piyasa pozisyonu
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_product_period', 'product_id', 'date', 'period_type'),
    )


class ProductImageMapping(Base):
    """Ürün Görsel Eşleştirmeleri - Manuel görsel URL mapping"""
    __tablename__ = "product_image_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_code = Column(String, index=True, nullable=False)  # ProductCode (öncelikli)
    barcode = Column(String, index=True)  # Barcode (alternatif)
    content_id = Column(String, index=True)  # ContentId (alternatif)
    product_name = Column(String)  # Ürün adı (opsiyonel, bilgi amaçlı)
    image_urls = Column(Text, nullable=False)  # JSON string - görsel URL'leri listesi
    primary_image_url = Column(String)  # Ana görsel URL (opsiyonel)
    is_active = Column(Boolean, default=True, index=True)
    notes = Column(Text)  # Notlar
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_product_code', 'product_code'),
        Index('idx_barcode', 'barcode'),
        Index('idx_content_id', 'content_id'),
        # w3-dup-index-fix-rest: BarcodeTemplate ile çakışıyordu (SQLite'ta index
        # adları global) — tablo adıyla nitelendirildi.
        Index('idx_productimagemapping_is_active', 'is_active'),
    )


class QARecord(Base):
    """Müşteri Soru-Cevap Kayıtları - Kalıcı soru-cevap deposu (AI öğrenme verisi)"""
    __tablename__ = "qa_records"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    qa_id = Column(String, index=True, nullable=False)   # Trendyol soru ID veya qa_*
    question = Column(Text, nullable=False)
    answer = Column(Text, default="")
    customer_id = Column(String, index=True)
    order_id = Column(String, index=True)
    status = Column(String, index=True, default="pending")            # pending / answered
    source = Column(String, default="manual")                         # trendyol / manual / ai
    ai_confidence = Column(Float)                                     # AI öneri güven skoru (0-1)
    user_feedback = Column(String)                                    # accepted / edited / rejected
    created_at = Column(DateTime, default=func.now(), index=True)
    answered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_qa_status', 'status'),
        Index('idx_qa_feedback', 'user_feedback'),
        UniqueConstraint('store_id', 'qa_id', name='uq_store_qa'),
    )


class SizeChart(Base):
    """Ürün Beden Tabloları - AI beden önerisi için ölçü verileri"""
    __tablename__ = "size_charts"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True, default=1)
    product_code = Column(String, index=True, nullable=False)  # Trendyol ProductCode
    product_name = Column(String)
    image_url = Column(String)                        # Beden tablosu görselinin URL'i (referans)
    sizes_json = Column(Text, nullable=False)         # JSON: [{"size":"M","bel_min":71,...}]
    notes = Column(Text)                              # Satıcı notları (kumaş, dar/bol kalıp vb.)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_size_product_code', 'product_code'),
        UniqueConstraint('store_id', 'product_code', name='uq_store_size_chart'),
    )


class StoreThreshold(Base):
    """Mağaza bazında ayarlanabilir uyarı eşikleri (w3-configurable-thresholds).
    NULL alan = ayarlanmamış, kod-gömülü varsayılan kullanılır (geriye dönük uyumlu).
    Bkz. hive/docs/thresholds-spec.md — utils/thresholds.py varsayılan/sınır değerleri tutar."""
    __tablename__ = "store_thresholds"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, unique=True, index=True)
    margin_warning_threshold = Column(Float, nullable=True)  # % — bu değerin ALTI "düşük marj"
    low_stock_floor = Column(Integer, nullable=True)  # minimum stok tabanı (adet)
    low_stock_sales_ratio = Column(Float, nullable=True)  # satış sayısının bu kesri kadar
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AutomationRuleRecord(Base):
    """Otomasyon kuralları — w3-automation-persist. ÖNCEDEN salt bellekte
    (routers/automation.py'nin module-level dict'i) tutuluyordu, her restart'ta
    kayboluyordu. `id` Trendyol'dan bağımsız, uygulamanın kendi ürettiği UUID
    string (router zaten öyle üretiyordu, korunuyor). conditions/actions
    serbest-şekilli JSON olduğu için Text'te ham JSON string olarak saklanır
    (QARecord/SizeChart'ın sizes_json'ıyla AYNI desen)."""
    __tablename__ = "automation_rules"

    id = Column(String, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    conditions_json = Column(Text, nullable=False)
    actions_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())




class IkasOrder(Base):
    """ikas'tan Excel/CSV ile içe aktarılan sipariş — Trendyol E-Faturam üzerinden
    fatura kesmek için. ikas Start paketinde API olmadığından siparişler panelden
    dışa aktarılan dosyayla gelir (bkz. utils/ikas_import.py).

    data_json: dosyadan ayrıştırılan sipariş (müşteri/fatura bilgileri + satırlar).
               Aynı sipariş tekrar yüklenirse YENİLENİR.
    overrides_json: kullanıcının panelden elle düzelttiği fatura alanları (ör. eksik
               TC/adres). Tekrar yüklemede KORUNUR, data_json'ın üzerine uygulanır.
    status: 'pending' (fatura kesilmedi) | 'invoiced' | 'error'. Faturalanan sipariş
            tekrar yüklemede değiştirilmez ve silinemez."""
    __tablename__ = "ikas_orders"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    order_number = Column(String, nullable=False)
    order_date = Column(String)  # dosyadaki ham tarih metni (formatı ikas'a bağlı)
    data_json = Column(Text, nullable=False)
    overrides_json = Column(Text)
    status = Column(String, nullable=False, default="pending")
    invoice_number = Column(String)
    invoice_uuid = Column(String)
    invoice_date = Column(DateTime)
    invoice_error = Column(Text)
    imported_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('store_id', 'order_number', name='uq_store_ikas_order'),
        Index('idx_ikas_order_store_status', 'store_id', 'status'),
    )


class InvoiceSettings(Base):
    """Mağaza bazında fatura ayarları (ikas → E-Faturam). KDV oranları muhasebeciyle
    teyit edilmeli; varsayılanlar hazır giyim (%10) ve kargo hizmeti (%20)."""
    __tablename__ = "invoice_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, unique=True, index=True)
    product_vat_rate = Column(Float, nullable=False, default=10.0)
    shipping_vat_rate = Column(Float, nullable=False, default=20.0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class StoreSettings(Base):
    """Mağaza bazında genel ayarlar (Ayarlar sayfası: Kâr Hesaplama + Etiket & Barkod).
    NULL alan = ayarlanmamış → utils/store_settings.py'deki varsayılan kullanılır
    (StoreThreshold ile aynı desen). Daha önce bu değerler global/bellek-içi ya da
    koda gömülüydü (kargo maliyeti, komisyon %10, etiket indirim kodu vb.)."""
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, unique=True, index=True)
    # Kâr hesaplama
    cargo_cost = Column(Float, nullable=True)  # ₺ / ürün
    default_commission_rate = Column(Float, nullable=True)  # %
    category_commissions_json = Column(Text, nullable=True)  # {"Jean": 21.5, ...}
    # Kargo etiketi altı sticker
    label_discount_code = Column(String, nullable=True)
    label_discount_percent = Column(Integer, nullable=True)
    label_website_url = Column(String, nullable=True)
    label_website_text = Column(String, nullable=True)
    label_brand_text = Column(String, nullable=True)
    label_brand_ribbon_enabled = Column(Boolean, nullable=True)
    label_group_by_product = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
