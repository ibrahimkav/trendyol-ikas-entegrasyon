"""
Sync Router - Manuel senkronizasyon endpoint'leri
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.sync_service import SyncService
    from database.models import Store
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds
    _db_available = True
except Exception:
    _db_available = False
    # Dummy functions for ghost mode
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")
    SyncService = None

router = APIRouter()


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class SyncResponse(BaseModel):
    success: bool
    message: str
    products_synced: Optional[int] = None
    orders_synced: Optional[int] = None


def _store_sync_service(db, store):
    """Wave3 per-store: bu mağazanın Trendyol kimliğini çözüp store-scoped SyncService döner.
    Kimlik yoksa resolve_trendyol_creds 409 fırlatır."""
    creds = resolve_trendyol_creds(db, store)
    return SyncService(creds=creds, store_id=store.id)


@router.post("/products", response_model=SyncResponse)
async def sync_products(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Ürünleri manuel olarak senkronize et (Wave3: per-store)"""
    _check_db()
    try:
        service = _store_sync_service(db, store)
        count = await service.sync_products()
        return SyncResponse(
            success=True,
            message=f"{count} ürün senkronize edildi",
            products_synced=count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senkronizasyon hatası: {str(e)}")


@router.post("/orders", response_model=SyncResponse)
async def sync_orders(
    days: int = 30,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Siparişleri manuel olarak senkronize et (Wave3: per-store)"""
    _check_db()
    try:
        service = _store_sync_service(db, store)
        count = await service.sync_orders(days=days)
        return SyncResponse(
            success=True,
            message=f"{count} sipariş senkronize edildi",
            orders_synced=count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senkronizasyon hatası: {str(e)}")


@router.post("/all", response_model=SyncResponse)
async def sync_all(
    force: bool = False,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Tüm verileri manuel olarak senkronize et (Wave3: per-store — bu mağaza)."""
    _check_db()
    try:
        service = _store_sync_service(db, store)
        products_count = await service.sync_products()
        orders_count = await service.sync_orders()
        return SyncResponse(
            success=True,
            message=f"Senkronizasyon tamamlandı: {products_count} ürün, {orders_count} sipariş",
            products_synced=products_count,
            orders_synced=orders_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senkronizasyon hatası: {str(e)}")


@router.post("/now", response_model=SyncResponse)
async def sync_now(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """'Şimdi Senkronize Et' — bu mağazayı kendi Trendyol anahtarıyla hemen senkronize eder."""
    _check_db()
    try:
        service = _store_sync_service(db, store)
        products_count = await service.sync_products()
        orders_count = await service.sync_orders()
        return SyncResponse(
            success=True,
            message=f"Güncel veriler çekildi: {products_count} ürün, {orders_count} sipariş",
            products_synced=products_count,
            orders_synced=orders_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senkronizasyon hatası: {str(e)}")


@router.post("/force", response_model=SyncResponse)
async def force_sync_all(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Tüm verileri zorla senkronize et (Wave3: per-store)."""
    _check_db()
    try:
        service = _store_sync_service(db, store)
        print(f"[Sync] Force sync started (store_id={store.id}) - fetching latest data from API...")
        products_count = await service.sync_products()
        orders_count = await service.sync_orders()
        return SyncResponse(
            success=True,
            message=f"Güncel veriler çekildi: {products_count} ürün, {orders_count} sipariş",
            products_synced=products_count,
            orders_synced=orders_count
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senkronizasyon hatası: {str(e)}")


@router.get("/status")
async def get_sync_status(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Son senkronizasyon durumunu getir"""
    _check_db()
    from database.models import SyncLog
    from sqlalchemy import desc

    latest_logs = db.query(SyncLog).filter(SyncLog.store_id == store.id).order_by(desc(SyncLog.started_at)).limit(10).all()
    
    # Son başarılı senkronizasyonları bul
    last_successful = {}
    for log in latest_logs:
        if log.status == 'success' and log.sync_type not in last_successful:
            last_successful[log.sync_type] = {
                "records_synced": log.records_synced,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None
            }
    
    return {
        "last_successful": last_successful,
        "latest_syncs": [
            {
                "type": log.sync_type,
                "status": log.status,
                "records_synced": log.records_synced,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "error": log.error_message
            }
            for log in latest_logs
        ],
        "auto_sync_interval": "5 minutes",
        "manual_sync_available": True
    }

