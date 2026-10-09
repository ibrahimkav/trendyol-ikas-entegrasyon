"""
Kargo Takip Router
Kargo durumu takibi ve analizi
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

router = APIRouter()

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Store
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders as _fetch_store_orders
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


def _format_trendyol_date(raw) -> str:
    """Ham Trendyol tarih değerini (epoch-ms int veya ISO string) okunabilir formata çevirir.
    w3-backend-cleanup Madde 3: önceden ham epoch-ms int JSON'a olduğu gibi yazılıyordu."""
    if not raw:
        return ""
    try:
        if isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 1e12:
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts)
        elif isinstance(raw, str):
            if 'T' in raw:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
            else:
                dt = datetime.strptime(raw, "%Y-%m-%d")
        else:
            return str(raw)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(raw)


class CargoTracking(BaseModel):
    """Kargo takip modeli"""
    order_id: str
    cargo_company: str
    tracking_number: str
    status: str
    current_location: Optional[str] = None
    estimated_delivery: Optional[str] = None
    history: List[Dict[str, Any]] = []


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3 kalıbı: per-store, env DEĞİL).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        return _fetch_store_orders(creds, max_pages=100, size=200)
    except Exception:
        return []


@router.get("/")
async def get_cargo_tracking(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm kargo takip bilgilerini döner. w3-hardening: per-store credential.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    cargo_list = []
    
    for order in orders:
        try:
            order_id = order.get("orderNumber") or order.get("id", "")
            
            # Kargo bilgilerini al
            cargo_tracking = order.get("cargoTrackingNumber") or order.get("trackingNumber") or ""
            cargo_company = (
                order.get("cargoProviderName") or
                order.get("cargoCompany") or
                order.get("shipmentCompany") or
                "Bilinmeyen"
            )
            
            if not cargo_tracking:
                shipment = order.get("shipment", {})
                cargo_tracking = (
                    shipment.get("cargoTrackingNumber") or
                    shipment.get("trackingNumber") or
                    shipment.get("barcode") or
                    ""
                )
            
            if cargo_tracking:
                status = order.get("status") or order.get("orderStatus") or "Unknown"
                
                # Durum çevirisi
                status_map = {
                    "Created": "Hazırlanıyor",
                    "Picking": "Toplanıyor",
                    "Invoiced": "Faturalandı",
                    "Shipped": "Kargoda",
                    "Delivered": "Teslim Edildi",
                    "Completed": "Tamamlandı"
                }
                status_tr = status_map.get(status, status)
                
                cargo_list.append({
                    "order_id": order_id,
                    "cargo_company": cargo_company,
                    "tracking_number": cargo_tracking,
                    "status": status_tr,
                    "status_code": status,
                    "order_date": _format_trendyol_date(order.get("orderDate") or order.get("order_date", "")),
                    "total_amount": order.get("totalPrice") or order.get("totalPriceValue") or 0
                })
        except Exception:
            continue
    
    return {
        "cargo_list": cargo_list,
        "total_count": len(cargo_list),
        "by_status": {
            "hazirlaniyor": len([c for c in cargo_list if c["status_code"] in ["Created", "Picking"]]),
            "kargoda": len([c for c in cargo_list if c["status_code"] == "Shipped"]),
            "teslim_edildi": len([c for c in cargo_list if c["status_code"] in ["Delivered", "Completed"]])
        }
    }


@router.get("/{order_id}")
async def get_cargo_by_order(
    order_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Belirli bir siparişin kargo takip bilgilerini döner. w3-hardening: per-store credential.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    for order in orders:
        current_order_id = order.get("orderNumber") or order.get("id", "")
        if current_order_id == order_id:
            cargo_tracking = order.get("cargoTrackingNumber") or order.get("trackingNumber") or ""
            cargo_company = (
                order.get("cargoProviderName") or
                order.get("cargoCompany") or
                order.get("shipmentCompany") or
                "Bilinmeyen"
            )
            
            if not cargo_tracking:
                shipment = order.get("shipment", {})
                cargo_tracking = (
                    shipment.get("cargoTrackingNumber") or
                    shipment.get("trackingNumber") or
                    shipment.get("barcode") or
                    ""
                )
            
            status = order.get("status") or order.get("orderStatus") or "Unknown"
            status_map = {
                "Created": "Hazırlanıyor",
                "Picking": "Toplanıyor",
                "Invoiced": "Faturalandı",
                "Shipped": "Kargoda",
                "Delivered": "Teslim Edildi",
                "Completed": "Tamamlandı"
            }
            
            return {
                "order_id": order_id,
                "cargo_company": cargo_company,
                "tracking_number": cargo_tracking,
                "status": status_map.get(status, status),
                "status_code": status,
                "order_date": _format_trendyol_date(order.get("orderDate") or order.get("order_date", "")),
                "customer_name": order.get("customerFirstName", "") + " " + order.get("customerLastName", ""),
                "delivery_address": order.get("shipmentAddress", {})
            }
    
    raise HTTPException(status_code=404, detail="Sipariş bulunamadı")

