"""
Trendyol AI Satıcı Asistanı - Backend API
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import math
import os
from dotenv import load_dotenv

from routers import barcode, pricing, orders, analytics, notifications, cargo, customers, customer_qa, inventory, products, reports, automation, financial, bulk_operations, competitor_analysis, sync, returns, campaigns, price_history, export_import, images, seo_optimization, customer_segmentation, product_images, size_chart, auth, settings as settings_router, dashboard, invoices
import asyncio
from contextlib import asynccontextmanager

load_dotenv()

# Database modülünü optional olarak yükle (ghost mode)
_db_available = False
_sync_task = None

try:
    from database.db import init_db
    from database.sync_service import background_sync_task, SyncService, sync_all_stores
    _db_available = True
except Exception as e:
    print(f"[App] Database module not available (ghost mode): {e}")
    print("[App] Application will continue without database features.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup ve shutdown işlemleri"""
    global _sync_task, _db_available
    
    # Startup
    if _db_available:
        try:
            print("[App] Initializing database...")
            init_db()
            
            # Background sync task'ı başlat (5 dakikada bir otomatik PER-STORE senkronizasyon).
            # background_sync_task döngü başında hemen ilk senkronu da yapar — ayrıca explicit
            # initial sync ÇAĞIRMIYORUZ (çift/eşzamanlı SQLite yazımı olmasın diye).
            print("[App] Starting background per-store sync service (every 5 minutes)...")
            _sync_task = asyncio.create_task(background_sync_task(interval_minutes=5))
        except Exception as e:
            print(f"[App] Database initialization failed (ghost mode): {e}")
            print("[App] Application will continue without database features.")
            _db_available = False
    else:
        print("[App] Database module disabled (ghost mode)")
    
    yield
    
    # Shutdown
    print("[App] Shutting down...")
    if _sync_task:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Trendyol AI Satıcı Asistanı",
    description="Yapay zeka destekli satış yönetim sistemi",
    version="1.0.0",
    lifespan=lifespan
)


def _sanitize_nonfinite(obj):
    """NaN/Infinity değerlerini JSON-uyumlu string'e çevirir (recursive)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_nonfinite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nonfinite(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """w3-thresholds-nan-fix: bir sayısal alana NaN/Infinity gönderilince Pydantic
    doğru şekilde 422 üretiyordu, AMA hata mesajı reddedilen ham değeri (`input`)
    GERİ YANSITTIĞI için Starlette'in JSONResponse'u (`allow_nan=False`, RFC-uyumlu
    JSON için bilinçli) bu NaN'ı serialize ederken 500'e düşüyordu — temiz bir
    doğrulama hatası, kendi hata yanıtını oluştururken çöküyordu. Bu, tek bir
    endpoint'e özgü değil, uygulamadaki HER sayısal alan için geçerli genel bir
    FastAPI/Starlette etkileşimi olduğundan burada (app-geneli) düzeltildi."""
    # jsonable_encoder ÖNCE (FastAPI'nin varsayılan handler'ının da yaptığı gibi —
    # errors() içindeki ham istisna nesnelerini (ctx.error) string'e çevirir),
    # NaN/Infinity temizliği SONRA (jsonable_encoder bunları OLDUĞU GİBİ float
    # bırakır, temizlemez).
    safe_errors = _sanitize_nonfinite(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# CORS ayarları - varsayılan olarak sadece yerel geliştirme origin'lerine izin verilir.
# Telefon/LAN üzerinden test için CORS_ORIGINS env değişkenine virgülle ayrılmış ek
# origin'ler eklenebilir (ör. CORS_ORIGINS=http://192.168.1.23:5173). Eskiden allow_origins=["*"]
# idi (auth eklenmeden önce risksizdi); artık JWT/oturum olduğu için daraltıldı.
_default_cors_origins = [
    "http://localhost:5173", "http://127.0.0.1:5173",  # Vite dev
    "http://localhost:3000", "http://127.0.0.1:3000",  # olası CRA/alternatif dev portu
]
_extra_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_cors_origins + _extra_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(barcode.router, prefix="/api/barcode", tags=["Barkod"])
app.include_router(pricing.router, prefix="/api/pricing", tags=["Fiyat Önerisi"])
app.include_router(orders.router, prefix="/api/orders", tags=["Siparişler"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analitik"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Bildirimler"])
app.include_router(cargo.router, prefix="/api/cargo", tags=["Kargo"])
app.include_router(customers.router, prefix="/api/customers", tags=["Müşteriler"])
app.include_router(customer_qa.router, prefix="/api/customer-qa", tags=["Müşteri Soru-Cevap"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Stok Yönetimi"])
app.include_router(products.router, prefix="/api/products", tags=["Ürün Yönetimi"])
app.include_router(reports.router, prefix="/api/reports", tags=["Raporlama"])
app.include_router(automation.router, prefix="/api/automation", tags=["Otomasyon"])
app.include_router(financial.router, prefix="/api/financial", tags=["Finansal Yönetim"])
app.include_router(bulk_operations.router, prefix="/api/bulk", tags=["Toplu İşlemler"])
# w3-competitor-route-close (2026-09-27, insan onayı): competitor_analysis.py'nin
# get_your_products() fonksiyonu (satır ~211) hiçbir store_id filtresi olmadan TÜM
# mağazaların ürünlerini dönüyordu — router'ın 4 endpoint'i de (products, analysis,
# market-trends, categories) bunu kullanıyor, yani sızıntı özelliğin TAMAMINDA.
# Özellik kullanılmadığı için DÜZELTİLEREK değil KAPATILARAK gideriliyor — kod
# SİLİNMEDİ, sadece mount edilmiyor. GERİ AÇMAK için: bu satırı yorumdan çıkar.
# app.include_router(competitor_analysis.router, prefix="/api/competitor", tags=["Rekabet Analizi"])
app.include_router(sync.router, prefix="/api/sync", tags=["Senkronizasyon"])
app.include_router(returns.router, prefix="/api/returns", tags=["İade ve İptal"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Kampanya ve İndirim"])
app.include_router(price_history.router, prefix="/api/price-history", tags=["Fiyat Geçmişi"])
app.include_router(export_import.router, prefix="/api/export-import", tags=["Export/Import"])
app.include_router(images.router, prefix="/api/images", tags=["Görsel Yönetimi"])
app.include_router(seo_optimization.router, prefix="/api/seo", tags=["SEO Optimizasyonu"])
app.include_router(customer_segmentation.router, prefix="/api/customer-segmentation", tags=["Müşteri Segmentasyonu"])
app.include_router(product_images.router, prefix="/api/product-images", tags=["Ürün Görsel Eşleştirmeleri"])
app.include_router(size_chart.router, prefix="/api/size-chart", tags=["Beden Tabloları"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Ayarlar"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["ikas Fatura"])


@app.get("/")
async def root():
    return {
        "message": "Trendyol AI Satıcı Asistanı API",
        "version": "1.0.0",
        "endpoints": {
            "barcode": "/api/barcode",
            "pricing": "/api/pricing",
            "orders": "/api/orders",
            "analytics": "/api/analytics",
            "notifications": "/api/notifications",
            "cargo": "/api/cargo",
            "customers": "/api/customers",
            "customer-qa": "/api/customer-qa",
            "inventory": "/api/inventory",
            "products": "/api/products",
            "reports": "/api/reports",
            "automation": "/api/automation",
            "financial": "/api/financial",
            "bulk": "/api/bulk",
            # "competitor": "/api/competitor",  # w3-competitor-route-close: kapatıldı, kod satır 138'de duruyor
            "sync": "/api/sync",
            "returns": "/api/returns",
            "campaigns": "/api/campaigns",
            "price-history": "/api/price-history",
            "export-import": "/api/export-import"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/health")
async def api_health_check():
    """Frontend proxy (/api) üzerinden erişim için."""
    return {"status": "healthy", "service": "trendyol-ai-backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


