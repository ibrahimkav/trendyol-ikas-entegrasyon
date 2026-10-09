"""
Müşteri Yönetimi Router
Müşteri profilleri, sipariş geçmişi, segmentasyon
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
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


class Customer(BaseModel):
    """Müşteri modeli"""
    customer_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    total_orders: int
    total_spent: float
    average_order_value: float
    last_order_date: Optional[str] = None
    customer_segment: str  # "new", "returning", "loyal", "vip"
    order_history: List[Dict[str, Any]] = []


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
async def get_customers(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm müşterileri listeler. w3-hardening: per-store credential.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "customers": [],
            "total_count": 0
        }
    
    # Müşterileri grupla
    customers_dict = defaultdict(lambda: {
        "orders": [],
        "total_spent": 0.0,
        "customer_id": "",
        "name": "",
        "email": "",
        "phone": ""
    })
    
    for order in orders:
        try:
            customer_id = str(order.get("customerId") or order.get("customer_id") or order.get("id", ""))
            if not customer_id:
                continue
            
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or 0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_price = float(total_price) if total_price else 0.0
            
            customers_dict[customer_id]["customer_id"] = customer_id
            customers_dict[customer_id]["orders"].append(order)
            customers_dict[customer_id]["total_spent"] += total_price
            
            # İlk siparişten müşteri bilgilerini al
            if not customers_dict[customer_id]["name"]:
                first_name = order.get("customerFirstName", "")
                last_name = order.get("customerLastName", "")
                customers_dict[customer_id]["name"] = f"{first_name} {last_name}".strip()
                customers_dict[customer_id]["email"] = order.get("customerEmail", "")
                customers_dict[customer_id]["phone"] = order.get("customerPhone", "")
        except Exception:
            continue
    
    # Müşteri listesini oluştur
    customers = []
    for customer_id, data in customers_dict.items():
        order_count = len(data["orders"])
        avg_order_value = data["total_spent"] / order_count if order_count > 0 else 0
        
        # Son sipariş tarihi
        last_order_date = None
        if data["orders"]:
            try:
                last_order = max(
                    data["orders"],
                    key=lambda o: o.get("orderDate") or o.get("order_date") or ""
                )
                last_order_date = last_order.get("orderDate") or last_order.get("order_date")
            except:
                pass
        
        # Müşteri segmentasyonu
        if order_count == 1:
            segment = "new"
        elif order_count <= 4:
            segment = "returning"
        elif order_count <= 10:
            segment = "loyal"
        else:
            segment = "vip"
        
        customers.append({
            "customer_id": customer_id,
            "name": data["name"] or "Bilinmeyen Müşteri",
            "email": data["email"],
            "phone": data["phone"],
            "total_orders": order_count,
            "total_spent": round(data["total_spent"], 2),
            "average_order_value": round(avg_order_value, 2),
            "last_order_date": _format_trendyol_date(last_order_date),
            "customer_segment": segment
        })
    
    # Toplam harcamaya göre sırala
    customers.sort(key=lambda x: x["total_spent"], reverse=True)
    
    return {
        "customers": customers,
        "total_count": len(customers),
        "segments": {
            "new": len([c for c in customers if c["customer_segment"] == "new"]),
            "returning": len([c for c in customers if c["customer_segment"] == "returning"]),
            "loyal": len([c for c in customers if c["customer_segment"] == "loyal"]),
            "vip": len([c for c in customers if c["customer_segment"] == "vip"])
        }
    }


@router.get("/{customer_id}")
async def get_customer_detail(
    customer_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Belirli bir müşterinin detaylı bilgilerini döner. w3-hardening: per-store credential.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    customer_orders = []
    customer_info = {}
    
    for order in orders:
        current_customer_id = str(order.get("customerId") or order.get("customer_id") or "")
        if current_customer_id == customer_id:
            customer_orders.append(order)
            
            if not customer_info:
                customer_info = {
                    "customer_id": customer_id,
                    "name": f"{order.get('customerFirstName', '')} {order.get('customerLastName', '')}".strip(),
                    "email": order.get("customerEmail", ""),
                    "phone": order.get("customerPhone", ""),
                    "address": order.get("shipmentAddress", {})
                }
    
    if not customer_orders:
        raise HTTPException(status_code=404, detail="Müşteri bulunamadı")
    
    # Sipariş istatistikleri
    total_spent = sum(
        float(str(o.get("totalPrice") or o.get("totalPriceValue") or 0).replace(",", "."))
        for o in customer_orders
    )
    
    return {
        **customer_info,
        "total_orders": len(customer_orders),
        "total_spent": round(total_spent, 2),
        "average_order_value": round(total_spent / len(customer_orders), 2) if customer_orders else 0,
        "order_history": [
            {
                "order_id": o.get("orderNumber") or o.get("id", ""),
                "order_date": _format_trendyol_date(o.get("orderDate") or o.get("order_date", "")),
                "status": o.get("status") or o.get("orderStatus", ""),
                "total_amount": o.get("totalPrice") or o.get("totalPriceValue") or 0,
                "items": o.get("lines", [])
            }
            for o in customer_orders
        ]
    }

